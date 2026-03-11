from __future__ import annotations

import json
import os
import random
import re
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 20
USER_AGENT = "chief-of-staff-jobs-bot/1.0"
MAX_RETRIES = 3
BACKOFF_SECONDS = 1.5
DEFAULT_MIN_REQUEST_INTERVAL = 0.2
_REQUEST_TIMES_LOCK = threading.Lock()
_NEXT_ALLOWED_REQUEST_AT: dict[str, float] = {}


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _min_request_interval_seconds() -> float:
    return max(0.0, _to_float(os.getenv("MIN_REQUEST_INTERVAL_SECONDS", ""), DEFAULT_MIN_REQUEST_INTERVAL))


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


def _fetch_json(url: str) -> Any:
    host_key = urlparse(url).netloc.lower() or "default"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    for attempt in range(MAX_RETRIES + 1):
        try:
            _respect_request_interval(host_key)
            with urlopen(request, timeout=DEFAULT_TIMEOUT, context=context) as response:  # nosec B310
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= MAX_RETRIES:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
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
    url = f"https://boards-api.greenhouse.io/v1/boards/{quote(company_slug)}/jobs?content=true"
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
    url = f"https://api.lever.co/v0/postings/{quote(company_slug)}?mode=json"
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
    return jobs


def fetch_ashby(company_slug: str) -> list[dict[str, Any]]:
    url = f"https://jobs.ashbyhq.com/api/non-user-graphql?company={quote(company_slug)}"
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
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    context = ssl.create_default_context()
    data = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            _respect_request_interval("jobs.ashbyhq.com")
            with urlopen(request, timeout=DEFAULT_TIMEOUT, context=context) as response:  # nosec B310
                data = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= MAX_RETRIES:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            else:
                delay = BACKOFF_SECONDS * (2**attempt) + random.uniform(0.0, 0.5)
            time.sleep(delay)

    if data is None:
        return []

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
    if normalized_company != source.company:
        print(f"[info] Normalized {source.platform} source: {source.company} -> {normalized_company}")

    try:
        if source.platform == "greenhouse":
            jobs = fetch_greenhouse(normalized_company)
        elif source.platform == "lever":
            jobs = fetch_lever(normalized_company)
        elif source.platform == "ashby":
            jobs = fetch_ashby(normalized_company)
        else:
            raise ValueError(f"Unsupported platform: {source.platform}")
        return FetchResult(source=source, normalized_company=normalized_company, jobs=jobs)
    except HTTPError as exc:
        details = ""
        try:
            error_body = exc.read().decode("utf-8", errors="ignore").strip()
            if error_body:
                details = f" body={error_body[:240]}"
        except Exception:
            pass
        print(f"[warn] {source.platform}:{source.company} failed: HTTP {exc.code} {exc.reason}{details}")
        return FetchResult(source=source, normalized_company=normalized_company, jobs=[], http_status=exc.code, error=f"HTTP {exc.code}")
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"[warn] {source.platform}:{source.company} failed: {exc}")
        return FetchResult(source=source, normalized_company=normalized_company, jobs=[], error=str(exc))


def fetch_jobs_for_source(source: CompanySource) -> list[dict[str, Any]]:
    return fetch_jobs_for_source_status(source).jobs
