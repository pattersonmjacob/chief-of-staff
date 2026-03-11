from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 20
USER_AGENT = "chief-of-staff-jobs-bot/1.0"


@dataclass
class CompanySource:
    platform: str
    company: str


def _fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    with urlopen(request, timeout=DEFAULT_TIMEOUT, context=context) as response:  # nosec B310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


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
    }


def fetch_greenhouse(company_slug: str) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{quote(company_slug)}/jobs?content=true"
    data = _fetch_json(url)
    jobs = []
    for raw_job in data.get("jobs", []):
        fields = {
            "department": (raw_job.get("departments") or [{}])[0].get("name", "") if raw_job.get("departments") else "",
            "team": (raw_job.get("offices") or [{}])[0].get("name", "") if raw_job.get("offices") else "",
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
    with urlopen(request, timeout=DEFAULT_TIMEOUT, context=context) as response:  # nosec B310
        data = json.loads(response.read().decode("utf-8"))

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
            }
            jobs.append(_normalize_job("ashby", company_slug, job, fields))
    return jobs


def fetch_jobs_for_source(source: CompanySource) -> list[dict[str, Any]]:
    try:
        if source.platform == "greenhouse":
            return fetch_greenhouse(source.company)
        if source.platform == "lever":
            return fetch_lever(source.company)
        if source.platform == "ashby":
            return fetch_ashby(source.company)
        raise ValueError(f"Unsupported platform: {source.platform}")
    except HTTPError as exc:
        details = ""
        try:
            error_body = exc.read().decode("utf-8", errors="ignore").strip()
            if error_body:
                details = f" body={error_body[:240]}"
        except (OSError, UnicodeDecodeError):
            pass
        print(f"[warn] {source.platform}:{source.company} failed: HTTP {exc.code} {exc.reason}{details}")
        return []
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"[warn] {source.platform}:{source.company} failed: {exc}")
        return []
