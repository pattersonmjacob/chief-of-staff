from __future__ import annotations

from datetime import datetime, timezone
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
    return path_parts[-1]


def _board_url(platform: str, company_slug: str) -> str:
    if platform == "greenhouse":
        return f"https://job-boards.greenhouse.io/{quote(company_slug)}"
    if platform == "lever":
        return f"https://jobs.lever.co/{quote(company_slug)}"
    return ""


def _api_url(platform: str, company_slug: str) -> str:
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{quote(company_slug)}/jobs?content=true"
    if platform == "lever":
        return f"https://api.lever.co/v0/postings/{quote(company_slug)}?mode=json"
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


_CURRENCY_SYMBOL_TO_CODE = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "¥": "JPY",
    "₹": "INR",
    "C$": "CAD",
    "A$": "AUD",
}


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    normalized = re.sub(r"[^0-9.,]", "", raw).replace(",", "")
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _normalize_interval(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    mapping = {
        "year": "year",
        "annual": "year",
        "annually": "year",
        "yr": "year",
        "month": "month",
        "monthly": "month",
        "mo": "month",
        "hour": "hour",
        "hourly": "hour",
        "hr": "hour",
        "week": "week",
        "weekly": "week",
        "day": "day",
        "daily": "day",
    }
    for key, normalized in mapping.items():
        if key in text:
            return normalized
    return text


def _normalize_timestamp(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
    else:
        raw = str(value).strip()
        if not raw:
            return ""
        if raw.isdigit():
            timestamp = float(raw)
        else:
            return raw

    if timestamp > 1_000_000_000_000:
        timestamp /= 1000.0
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return str(value)


def _detect_currency(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        upper = text.upper()
        code_match = re.search(r"\b(USD|EUR|GBP|CAD|AUD|JPY|INR)\b", upper)
        if code_match:
            return code_match.group(1)
        for symbol, code in _CURRENCY_SYMBOL_TO_CODE.items():
            if symbol in text:
                return code
    return ""


def _extract_comp_from_text(text: Any) -> dict[str, Any]:
    description = str(text or "")
    if not description:
        return {}

    patterns = [
        r"(?P<currency>USD|EUR|GBP|CAD|AUD|JPY|INR|\$|£|€)\s?(?P<min>\d{2,3}(?:[\d,]{0,6})(?:\.\d+)?)\s?(?:-|to|–)\s?(?P<max>\d{2,3}(?:[\d,]{0,6})(?:\.\d+)?)\s?(?:USD|EUR|GBP|CAD|AUD|JPY|INR|\$|£|€)?(?:\s*(?:per|/)\s*(?P<intv>year|yr|annual|month|mo|hour|hr|week|day))?",
        r"(?P<currency>USD|EUR|GBP|CAD|AUD|JPY|INR|\$|£|€)\s?(?P<single>\d{2,3}(?:[\d,]{0,6})(?:\.\d+)?)\s?(?:per|/)\s*(?P<intv>year|yr|annual|month|mo|hour|hr|week|day)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if not match:
            continue
        groups = match.groupdict()
        comp_min = _to_number(groups.get("min") or groups.get("single"))
        comp_max = _to_number(groups.get("max") or groups.get("single"))
        currency = _detect_currency(groups.get("currency"), match.group(0))
        interval = _normalize_interval(groups.get("intv"))
        return {
            "comp_min": comp_min if comp_min is not None else "",
            "comp_max": comp_max if comp_max is not None else "",
            "comp_currency": currency,
            "comp_interval": interval,
            "comp_text": match.group(0).strip(),
        }
    return {}


def infer_work_mode(location: Any, description: Any, explicit_work_mode: Any = "") -> str:
    explicit = str(explicit_work_mode or "").strip().lower()
    if explicit in {"remote", "hybrid", "onsite", "on-site"}:
        return "onsite" if explicit == "on-site" else explicit

    text = " ".join([str(location or ""), str(description or "")]).lower()
    if "hybrid" in text:
        return "hybrid"
    if "remote" in text or "work from home" in text or "wfh" in text:
        return "remote"
    if "on-site" in text or "onsite" in text or "on site" in text:
        return "onsite"
    if str(location or "").strip() and "remote" not in text:
        return "hybrid_or_onsite"
    return ""


def _parse_compensation(raw_job: dict[str, Any], fields: dict[str, Any], description: str = "") -> dict[str, Any]:
    comp_sources = [
        fields.get("compensation"),
        raw_job.get("compensation"),
        raw_job.get("salary"),
        raw_job.get("pay"),
        raw_job.get("salaryRange"),
        raw_job.get("compensationRange"),
        raw_job.get("payRange"),
    ]

    for source in comp_sources:
        if isinstance(source, dict):
            comp_min = _to_number(source.get("min") or source.get("minimum") or source.get("minAmount"))
            comp_max = _to_number(source.get("max") or source.get("maximum") or source.get("maxAmount"))
            currency = _detect_currency(source.get("currency"), source.get("currencyCode"), source.get("symbol"))
            interval = _normalize_interval(source.get("interval") or source.get("period") or source.get("unit"))
            comp_text = str(source.get("text") or source.get("description") or "").strip()
            if any([comp_min is not None, comp_max is not None, currency, interval, comp_text]):
                return {
                    "comp_min": comp_min if comp_min is not None else "",
                    "comp_max": comp_max if comp_max is not None else "",
                    "comp_currency": currency,
                    "comp_interval": interval,
                    "comp_text": comp_text,
                }
        elif isinstance(source, list):
            for item in source:
                parsed = _parse_compensation({"compensation": item}, {}, description)
                if any(parsed.values()):
                    return parsed
        elif source:
            parsed = _extract_comp_from_text(source)
            if parsed:
                return parsed

    for key in [
        "salaryRange",
        "compensation",
        "compensationText",
        "salary",
        "payRange",
        "payTransparency",
    ]:
        value = fields.get(key)
        if value:
            parsed = _extract_comp_from_text(value)
            if parsed:
                return parsed

    return _extract_comp_from_text(description)


def _normalize_job(platform: str, company: str, raw_job: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    location = raw_job.get("location") or raw_job.get("offices") or fields.get("location") or ""
    if isinstance(location, dict):
        location = location.get("name") or ""
    elif isinstance(location, list):
        location = ", ".join(str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in location)

    description = _strip_html(
        fields.get("description")
        or raw_job.get("content")
        or raw_job.get("openingPlain")
        or raw_job.get("descriptionBodyPlain")
        or raw_job.get("additionalPlain")
        or raw_job.get("descriptionPlain")
        or raw_job.get("description")
        or ""
    )
    compensation = _parse_compensation(raw_job, fields, description)
    title = str(
        raw_job.get("title")
        or raw_job.get("text")
        or fields.get("title")
        or raw_job.get("name")
        or raw_job.get("position")
        or ""
    ).strip()

    if not title:
        title_match = re.search(
            r"(?:we(?:'re| are) looking for|hiring|role:?|position:?|job title:?)[^A-Za-z0-9]*(?P<title>[A-Z][A-Za-z0-9/&+,\-() ]{2,80}?)(?=\s+to\b|[.!:\n]|$)",
            description,
            re.IGNORECASE,
        )
        if title_match:
            title = title_match.group("title").strip(" :-\u00a0")
            title = re.sub(r"^(?:a|an|the)\s+", "", title, flags=re.IGNORECASE)

    work_mode = infer_work_mode(location, description, explicit_work_mode=fields.get("work_mode") or raw_job.get("workplaceType"))

    return {
        "id": raw_job.get("id") or fields.get("id") or "",
        "platform": platform,
        "company": company,
        "title": title,
        "location": str(location),
        "work_mode": work_mode,
        "url": raw_job.get("absolute_url")
        or raw_job.get("hostedUrl")
        or raw_job.get("applyUrl")
        or raw_job.get("apply_url")
        or raw_job.get("url")
        or "",
        "department": fields.get("department") or raw_job.get("department") or "",
        "team": fields.get("team") or "",
        "employment_type": fields.get("employment_type") or raw_job.get("commitment") or "",
        "description": description,
        "comp_min": compensation.get("comp_min", ""),
        "comp_max": compensation.get("comp_max", ""),
        "comp_currency": compensation.get("comp_currency", ""),
        "comp_interval": compensation.get("comp_interval", ""),
        "comp_text": compensation.get("comp_text", ""),
        "posted_at": _normalize_timestamp(fields.get("posted_at") or raw_job.get("createdAt") or raw_job.get("created_at") or raw_job.get("updated_at")),
        "updated_at": _normalize_timestamp(fields.get("updated_at") or raw_job.get("updatedAt") or raw_job.get("updated_at") or raw_job.get("createdAt") or raw_job.get("created_at")),
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
            "compensation": raw_job.get("salary_range")
            or raw_job.get("pay_input_ranges")
            or (raw_job.get("metadata", {}).get("compensation") if isinstance(raw_job.get("metadata"), dict) else ""),
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
                categories = raw_job.get("categories", {}) if isinstance(raw_job.get("categories"), dict) else {}
                all_locations = categories.get("allLocations") if isinstance(categories.get("allLocations"), list) else []
                location = categories.get("location") or ", ".join(str(item) for item in all_locations if item)
                description_parts = [
                    raw_job.get("openingPlain"),
                    raw_job.get("descriptionBodyPlain"),
                    raw_job.get("additionalPlain"),
                    raw_job.get("descriptionPlain"),
                    raw_job.get("description"),
                ]
                description = "\n\n".join(str(part).strip() for part in description_parts if str(part or "").strip())
                fields = {
                    "id": raw_job.get("id") or "",
                    "title": raw_job.get("text") or "",
                    "department": categories.get("department", ""),
                    "team": categories.get("team", ""),
                    "employment_type": categories.get("commitment", "") or raw_job.get("commitment") or "",
                    "location": location,
                    "work_mode": raw_job.get("workplaceType") or "",
                    "description": description,
                    "posted_at": raw_job.get("createdAt") or "",
                    "updated_at": raw_job.get("updatedAt") or "",
                    "compensation": raw_job.get("salaryRange") or raw_job.get("salaryDescription") or raw_job.get("compensation") or categories.get("compensation", ""),
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
