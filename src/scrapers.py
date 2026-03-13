from __future__ import annotations

import json
import os
import random
import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; ChiefOfStaffJobsBot/1.1; +https://github.com/)"
MAX_RETRIES = 3
BACKOFF_SECONDS = 1.5
DEFAULT_MIN_REQUEST_INTERVAL = 0.5
_REQUEST_TIMES_LOCK = threading.Lock()
_NEXT_ALLOWED_REQUEST_AT: dict[str, float] = {}
_REQUEST_CACHE_LOCK = threading.Lock()
_REQUEST_CACHE: dict[str, Any] = {}


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _min_request_interval_seconds() -> float:
    return max(0.0, _to_float(os.getenv("MIN_REQUEST_INTERVAL_SECONDS", ""), DEFAULT_MIN_REQUEST_INTERVAL))


def _request_timeout_seconds(platform: str = "") -> float:
    platform_key = platform.strip().upper()
    if platform_key:
        value = os.getenv(f"{platform_key}_TIMEOUT_SECONDS", "")
        if value:
            return max(1.0, _to_float(value, DEFAULT_TIMEOUT))
    return max(1.0, _to_float(os.getenv("REQUEST_TIMEOUT_SECONDS", ""), DEFAULT_TIMEOUT))


def _respect_request_interval(host_key: str) -> None:
    min_interval = _min_request_interval_seconds()
    now = time.monotonic()
    with _REQUEST_TIMES_LOCK:
        next_allowed = _NEXT_ALLOWED_REQUEST_AT.get(host_key, 0.0)
        wait_seconds = max(0.0, next_allowed - now)
        _NEXT_ALLOWED_REQUEST_AT[host_key] = max(now, next_allowed) + min_interval

    if wait_seconds > 0:
        time.sleep(wait_seconds)


@dataclass
class CompanySource:
    platform: str
    company: str
    url: str = ""
    source_url: str = ""
    board_url: str = ""


@dataclass
class FetchResult:
    source: CompanySource
    normalized_company: str
    jobs: list[dict[str, Any]]
    http_status: int | None = None
    error: str = ""


def _normalize_company_slug(platform: str, company: str) -> str:
    value = (company or "").strip().lower().strip("/")
    if not value:
        return ""

    if not (value.startswith("http://") or value.startswith("https://")):
        return value

    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return ""

    if platform == "greenhouse":
        if "greenhouse.io" in host and path_parts[-1] == "jobs" and len(path_parts) > 1:
            return path_parts[-2]
        if "greenhouse.io" in host and path_parts[:2] == ["v1", "boards"] and len(path_parts) > 2:
            return path_parts[2]
    elif platform == "lever":
        if "lever.co" in host and path_parts[0] == "postings" and len(path_parts) > 1:
            return path_parts[1]
    elif platform == "ashby":
        if "ashbyhq.com" in host and path_parts[-1] == "jobs" and len(path_parts) > 1:
            return path_parts[-2]

    return path_parts[-1]


def _board_url(platform: str, company_slug: str) -> str:
    if platform == "greenhouse":
        return f"https://job-boards.greenhouse.io/{quote(company_slug)}"
    if platform == "lever":
        return f"https://jobs.lever.co/{quote(company_slug)}"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/{quote(company_slug)}"
    return ""


def _api_url(platform: str, company_slug: str) -> str:
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{quote(company_slug)}/jobs?content=true"
    if platform == "lever":
        return f"https://api.lever.co/v0/postings/{quote(company_slug)}?mode=json"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/api/non-user-graphql?company={quote(company_slug)}"
    return ""


def _fetch_json(url: str, timeout_seconds: float | None = None) -> Any:
    cache_key = f"GET::{url}"
    with _REQUEST_CACHE_LOCK:
        if cache_key in _REQUEST_CACHE:
            return _REQUEST_CACHE[cache_key]

    host_key = urlparse(url).netloc.lower() or "default"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    timeout = timeout_seconds if timeout_seconds is not None else _request_timeout_seconds()
    for attempt in range(MAX_RETRIES + 1):
        try:
            _respect_request_interval(host_key)
            with urlopen(request, timeout=timeout, context=context) as response:  # nosec B310
                payload = response.read().decode("utf-8")
            data = json.loads(payload)
            with _REQUEST_CACHE_LOCK:
                _REQUEST_CACHE[cache_key] = data
            return data
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= MAX_RETRIES:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
            if exc.code == 429:
                print(f"[warn] Rate limited on {host_key}; backing off {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES + 1})")
            time.sleep(delay)
        except (URLError, TimeoutError, socket.timeout) as exc:
            if attempt >= MAX_RETRIES:
                raise
            delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
            print(f"[warn] Network error on {host_key}: {exc}; retrying in {delay:.2f}s")
            time.sleep(delay)


def _strip_html(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"<[^>]+>", " ", text).strip()


def _normalize_job(platform: str, company: str, raw_job: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    location = raw_job.get("location") or raw_job.get("offices") or fields.get("location") or ""
    if isinstance(location, dict):
        location = location.get("name") or ""
    elif isinstance(location, list):
        location = ", ".join(str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in location)

    return {
        "platform": platform,
        "company": company,
        "title": raw_job.get("title") or fields.get("title") or "",
        "location": str(location),
        "url": raw_job.get("absolute_url")
        or raw_job.get("hostedUrl")
        or raw_job.get("apply_url")
        or raw_job.get("url")
        or "",
        "department": fields.get("department") or raw_job.get("department") or "",
        "team": fields.get("team") or "",
        "employment_type": fields.get("employment_type") or raw_job.get("commitment") or "",
        "description": _strip_html(
            fields.get("description")
            or raw_job.get("content")
            or raw_job.get("descriptionPlain")
            or raw_job.get("description")
            or ""
        ),
        "posted_at": fields.get("posted_at") or raw_job.get("updated_at") or raw_job.get("createdAt") or raw_job.get("created_at") or "",
        "updated_at": fields.get("updated_at") or raw_job.get("updatedAt") or raw_job.get("updated_at") or "",
    }


def fetch_greenhouse(company_slug: str) -> list[dict[str, Any]]:
    url = _api_url("greenhouse", company_slug)
    data = _fetch_json(url)
    jobs = []
    for raw_job in data.get("jobs", []):
        fields = {
            "department": (raw_job.get("departments") or [{}])[0].get("name", "") if raw_job.get("departments") else "",
            "team": (raw_job.get("offices") or [{}])[0].get("name", "") if raw_job.get("offices") else "",
            "posted_at": raw_job.get("updated_at") or "",
        }
        jobs.append(_normalize_job("greenhouse", company_slug, raw_job, fields))
    return jobs


def fetch_lever(company_slug: str) -> list[dict[str, Any]]:
    candidate_urls = [
        _api_url("lever", company_slug),
        f"https://jobs.lever.co/{quote(company_slug)}?mode=json",
    ]
    last_error: Exception | None = None
    for idx, url in enumerate(candidate_urls):
        try:
            data = _fetch_json(url)
            jobs = []
            for raw_job in data:
                fields = {
                    "department": raw_job.get("categories", {}).get("team", ""),
                    "team": raw_job.get("categories", {}).get("department", ""),
                    "employment_type": raw_job.get("categories", {}).get("commitment", ""),
                    "location": raw_job.get("categories", {}).get("location", ""),
                    "description": raw_job.get("descriptionPlain") or raw_job.get("description") or "",
                    "posted_at": raw_job.get("createdAt") or "",
                    "updated_at": raw_job.get("updatedAt") or "",
                }
                jobs.append(_normalize_job("lever", company_slug, raw_job, fields))
            if idx > 0:
                print(f"[info] Lever fallback endpoint succeeded for {company_slug}: {url}")
            return jobs
        except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError) as exc:
            last_error = exc
            if idx < len(candidate_urls) - 1:
                print(f"[warn] Lever endpoint failed for {company_slug}: {url} ({exc}); trying fallback")
                continue
            raise

    if last_error:
        raise last_error
    return []


def fetch_ashby(company_slug: str) -> list[dict[str, Any]]:
    url = _api_url("ashby", company_slug)
    fallback_url = "https://jobs.ashbyhq.com/api/non-user-graphql"
    payload = {
        "operationName": "ApiJobBoard",
        "variables": {"organizationHostedJobsPageName": company_slug},
        "query": "query ApiJobBoard($organizationHostedJobsPageName: String!) {\n"
        "  jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {\n"
        "    teams {\n"
        "      id\n"
        "      name\n"
        "      jobs {\n"
        "        id\n"
        "        title\n"
        "        location { name }\n"
        "        employmentType\n"
        "        applyUrl\n"
        "        publishedDate\n"
        "        updatedAt\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n",
    }
    cache_key = f"POST::{url}::{company_slug}"
    with _REQUEST_CACHE_LOCK:
        if cache_key in _REQUEST_CACHE:
            data = _REQUEST_CACHE[cache_key]
            return _ashby_jobs_from_data(company_slug, data)

    context = ssl.create_default_context()
    timeout_seconds = _request_timeout_seconds("ashby")
    data = None
    graphql_urls = [url]
    if fallback_url not in graphql_urls:
        graphql_urls.append(fallback_url)

    for graphql_url in graphql_urls:
        request = Request(
            graphql_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                "Origin": f"https://jobs.ashbyhq.com/{quote(company_slug)}",
                "Referer": f"https://jobs.ashbyhq.com/{quote(company_slug)}",
            },
            method="POST",
        )
        for attempt in range(MAX_RETRIES + 1):
            try:
                _respect_request_interval("jobs.ashbyhq.com")
                with urlopen(request, timeout=timeout_seconds, context=context) as response:  # nosec B310
                    data = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                if exc.code not in {404, 429, 500, 502, 503, 504} or attempt >= MAX_RETRIES:
                    if exc.code == 404:
                        print(f"[warn] Ashby GraphQL endpoint not found ({graphql_url}); trying fallback")
                        break
                    raise
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                else:
                    delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
                if exc.code == 429:
                    print(f"[warn] Rate limited on jobs.ashbyhq.com; backing off {delay:.2f}s (attempt {attempt + 1}/{MAX_RETRIES + 1})")
                time.sleep(delay)
            except (URLError, TimeoutError, socket.timeout) as exc:
                if attempt >= MAX_RETRIES:
                    raise
                delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
                print(f"[warn] Network error on jobs.ashbyhq.com: {exc}; retrying in {delay:.2f}s")
                time.sleep(delay)
        if data is not None:
            break

    if data is None:
        print(f"[warn] Ashby GraphQL failed for {company_slug}; trying board HTML fallback")
        return _fetch_ashby_jobs_from_board_page(company_slug)

    with _REQUEST_CACHE_LOCK:
        _REQUEST_CACHE[cache_key] = data

    jobs = _ashby_jobs_from_data(company_slug, data)
    if jobs:
        return jobs

    print(f"[warn] Ashby GraphQL returned zero jobs for {company_slug}; trying board HTML fallback")
    return _fetch_ashby_jobs_from_board_page(company_slug)


def _fetch_ashby_jobs_from_board_page(company_slug: str) -> list[dict[str, Any]]:
    board_url = _board_url("ashby", company_slug)
    request = Request(board_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    context = ssl.create_default_context()
    timeout_seconds = _request_timeout_seconds("ashby")

    _respect_request_interval("jobs.ashbyhq.com")
    with urlopen(request, timeout=timeout_seconds, context=context) as response:  # nosec B310
        html = response.read().decode("utf-8", errors="ignore")

    next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not next_data_match:
        return []

    try:
        next_data = json.loads(next_data_match.group(1))
    except ValueError:
        return []

    team_names: dict[str, str] = {}
    jobs: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if {"id", "title"}.issubset(node.keys()) and any(k in node for k in ["applyUrl", "jobUrl"]):
                job = {
                    "title": node.get("title", ""),
                    "location": (node.get("location", {}) or {}).get("name", "") if isinstance(node.get("location"), dict) else str(node.get("location", "")),
                    "hostedUrl": node.get("applyUrl") or node.get("jobUrl") or "",
                }
                team_id = str(node.get("teamId") or "")
                fields = {
                    "team": team_names.get(team_id, ""),
                    "employment_type": node.get("employmentType", ""),
                    "posted_at": node.get("publishedDate") or node.get("createdAt") or "",
                    "updated_at": node.get("updatedAt") or "",
                }
                jobs.append(_normalize_job("ashby", company_slug, job, fields))

            if {"id", "name"}.issubset(node.keys()) and "jobs" in node and isinstance(node.get("jobs"), list):
                team_names[str(node.get("id", ""))] = str(node.get("name", ""))

            for value in node.values():
                walk(value)
            return

        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(next_data)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for job in jobs:
        key = f"{job.get('title','')}::{job.get('url','')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def _ashby_jobs_from_data(company_slug: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    teams = data.get("data", {}).get("jobBoardWithTeams", {}).get("teams", [])
    jobs: list[dict[str, Any]] = []
    for team in teams:
        team_name = team.get("name", "")
        for raw_job in team.get("jobs", []):
            job = {
                "title": raw_job.get("title", ""),
                "location": raw_job.get("location", {}).get("name", ""),
                "hostedUrl": raw_job.get("applyUrl", ""),
            }
            fields = {
                "team": team_name,
                "employment_type": raw_job.get("employmentType", ""),
                "posted_at": raw_job.get("publishedDate") or "",
                "updated_at": raw_job.get("updatedAt") or "",
            }
            jobs.append(_normalize_job("ashby", company_slug, job, fields))
    return jobs


def fetch_jobs_for_source_status(source: CompanySource) -> FetchResult:
    normalized_company = _normalize_company_slug(source.platform, source.company)
    fallback_company = _normalize_company_slug(source.platform, source.url) if source.url else ""
    if normalized_company != source.company:
        print(f"[info] Normalized {source.platform} source: {source.company} -> {normalized_company}")

    candidates = [normalized_company]
    if fallback_company and fallback_company not in candidates:
        candidates.append(fallback_company)

    for idx, company_candidate in enumerate(candidates):
        api_url = _api_url(source.platform, company_candidate)
        board_url = source.board_url or _board_url(source.platform, company_candidate)
        print(
            f"[info] Fetch attempt {idx + 1}/{len(candidates)} for {source.platform}:{source.company} "
            f"candidate={company_candidate} api_url={api_url} board_url={board_url} source_url={source.source_url or source.url or '<none>'}"
        )
        try:
            if source.platform == "greenhouse":
                jobs = fetch_greenhouse(company_candidate)
            elif source.platform == "lever":
                jobs = fetch_lever(company_candidate)
            elif source.platform == "ashby":
                jobs = fetch_ashby(company_candidate)
            else:
                raise ValueError(f"Unsupported platform: {source.platform}")

            print(f"[info] {source.platform}:{company_candidate} returned {len(jobs)} jobs ({api_url})")
            if idx > 0:
                print(f"[info] Recovered via URL fallback for {source.platform}:{source.company} -> {company_candidate}")
            return FetchResult(source=source, normalized_company=company_candidate, jobs=jobs)
        except HTTPError as exc:
            details = ""
            try:
                error_body = exc.read().decode("utf-8", errors="ignore").strip()
                if error_body:
                    details = f" body={error_body[:240]}"
            except Exception:
                pass
            can_retry_with_fallback = idx < len(candidates) - 1 and exc.code in {400, 404}
            if can_retry_with_fallback:
                print(f"[warn] {source.platform}:{company_candidate} failed HTTP {exc.code}; retrying with fallback identifier")
                continue
            print(f"[warn] {source.platform}:{source.company} failed: HTTP {exc.code} {exc.reason} api_url={api_url}{details}")
            return FetchResult(source=source, normalized_company=company_candidate, jobs=[], http_status=exc.code, error=f"HTTP {exc.code}")
        except (URLError, TimeoutError, ValueError) as exc:
            if idx < len(candidates) - 1:
                print(f"[warn] {source.platform}:{company_candidate} failed: {exc}; trying URL fallback")
                continue
            print(f"[warn] {source.platform}:{source.company} failed: {exc} api_url={api_url}")
            return FetchResult(source=source, normalized_company=company_candidate, jobs=[], error=str(exc))

    return FetchResult(source=source, normalized_company=normalized_company, jobs=[], error="all_candidates_failed")


def fetch_jobs_for_source(source: CompanySource) -> list[dict[str, Any]]:
    return fetch_jobs_for_source_status(source).jobs
