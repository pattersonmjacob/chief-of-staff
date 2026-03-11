from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from json import JSONDecodeError
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from render import render_html
from scrapers import CompanySource, fetch_jobs_for_source
from sources import load_sources_from_csv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config.example.json"
JOBS_JSON = ROOT / "jobs.json"
JOBS_CSV = ROOT / "jobs.csv"
DOCS_HTML = ROOT / "docs" / "index.html"
RUN_META_JSON = ROOT / "data" / "run_meta.json"




def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _job_key(job: dict[str, Any]) -> str:
    return str(job.get("url") or f"{job.get('platform')}:{job.get('company')}:{job.get('title')}")


def classify_job_function(job: dict[str, Any]) -> str:
    text = " ".join([str(job.get("title", "")), str(job.get("department", "")), str(job.get("team", ""))]).lower()
    mapping = [
        ("program-management", ["program manager", "program management", "pm" ]),
        ("business-operations", ["business operations", "bizops", "strategy", "strategic operations", "operations"]),
        ("product", ["product", "gtm"]),
        ("engineering", ["engineering", "software", "technical", "data", "platform", "infrastructure"]),
        ("finance", ["finance", "cfo", "fp&a"]),
        ("people-hr", ["people", "hr", "talent"]),
    ]
    for tag, terms in mapping:
        if any(term in text for term in terms):
            return tag
    return "other"


def classify_is_technical(job: dict[str, Any]) -> bool:
    text = " ".join([str(job.get("title", "")), str(job.get("department", "")), str(job.get("team", ""))]).lower()
    technical_terms = ["engineering", "technical", "software", "data", "platform", "infrastructure", "asic", "security"]
    return any(term in text for term in technical_terms)


def enrich_jobs_with_history_and_flags(jobs: list[dict[str, Any]], previous_jobs: list[dict[str, Any]], run_at: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    prev_by_key = {_job_key(job): job for job in previous_jobs}
    enriched: list[dict[str, Any]] = []
    new_count = 0

    for job in jobs:
        key = _job_key(job)
        previous = prev_by_key.get(key, {})
        first_seen = str(previous.get("first_seen_at") or run_at)
        is_new = not bool(previous)
        if is_new:
            new_count += 1

        enriched_job = dict(job)
        enriched_job["first_seen_at"] = first_seen
        enriched_job["last_seen_at"] = run_at
        enriched_job["is_new"] = is_new
        enriched_job["is_technical"] = classify_is_technical(enriched_job)
        enriched_job["job_function"] = classify_job_function(enriched_job)
        enriched.append(enriched_job)

    return enriched, {"new_count": new_count, "total": len(enriched)}


def load_previous_jobs() -> list[dict[str, Any]]:
    if not JOBS_JSON.exists():
        return []
    try:
        data = json.loads(JOBS_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_run_meta(run_at: str, total_jobs: int, new_jobs: int) -> None:
    RUN_META_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_run_at": run_at,
        "total_jobs": total_jobs,
        "new_jobs": new_jobs,
    }
    RUN_META_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path.name} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return _load_json_file(CONFIG_PATH)
    if CONFIG_EXAMPLE_PATH.exists():
        print("[warn] config.json not found, using config.example.json")
        return _load_json_file(CONFIG_EXAMPLE_PATH)
    raise FileNotFoundError("No config.json or config.example.json found.")


def apply_runtime_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    updated = dict(cfg)

    env_sources_csv = os.getenv("SOURCES_CSV", "").strip()
    env_sources_csv_url = os.getenv("SOURCES_CSV_URL", "").strip()

    if env_sources_csv:
        updated["sources_csv"] = env_sources_csv
        print(f"[info] Using SOURCES_CSV override: {env_sources_csv}")

    if env_sources_csv_url:
        updated["sources_csv_url"] = env_sources_csv_url
        print("[info] Using SOURCES_CSV_URL override")

    if not updated.get("sources_csv"):
        default_sources_csv = ROOT / "data" / "company_slugs.csv"
        if default_sources_csv.exists():
            updated["sources_csv"] = str(default_sources_csv.relative_to(ROOT))
            print(f"[info] Auto-detected source list at {updated['sources_csv']}")

    return updated


def maybe_download_sources_csv(cfg: dict[str, Any]) -> None:
    url = cfg.get("sources_csv_url")
    path_value = cfg.get("sources_csv")
    if not url or not path_value:
        return

    target = ROOT / path_value
    target.parent.mkdir(parents=True, exist_ok=True)

    request = Request(url, headers={"User-Agent": "chief-of-staff-jobs-bot/1.0"})
    context = ssl.create_default_context()
    with urlopen(request, timeout=30, context=context) as response:  # nosec B310
        target.write_bytes(response.read())

    print(f"[info] Downloaded sources CSV to {target}")


def get_sources(cfg: dict[str, Any]) -> list[CompanySource]:
    source_rows = cfg.get("sources", [])

    sources_csv = cfg.get("sources_csv")
    if sources_csv:
        min_open_jobs = int(cfg.get("min_open_jobs", 1))
        max_sources = cfg.get("max_sources")
        max_sources_int = int(max_sources) if max_sources is not None else None
        try:
            source_rows = load_sources_from_csv(ROOT / sources_csv, min_open_jobs=min_open_jobs, max_sources=max_sources_int)
            print(f"[info] Loaded {len(source_rows)} sources from {sources_csv}")
        except FileNotFoundError:
            print(f"[warn] sources_csv not found at {sources_csv}; falling back to config.sources")

    return [CompanySource(**item) for item in source_rows]


def filter_jobs(
    jobs: list[dict[str, Any]],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    includes = [k.strip().lower() for k in include_keywords if k.strip()]
    excludes = [k.strip().lower() for k in exclude_keywords if k.strip()]
    chief_of_staff_pattern = re.compile(r"\bchief\b.*\bstaff\b", re.IGNORECASE)

    filtered = []
    stats = {
        "input": len(jobs),
        "excluded_missing_chief_of_staff_title": 0,
        "excluded_missing_include": 0,
        "excluded_by_exclude": 0,
        "output": 0,
    }
    for job in jobs:
        title = str(job.get("title", ""))
        if not chief_of_staff_pattern.search(title):
            stats["excluded_missing_chief_of_staff_title"] += 1
            continue

        haystack = " ".join(
            [
                title,
                str(job.get("department", "")),
                str(job.get("team", "")),
                str(job.get("location", "")),
                str(job.get("description", "")),
            ]
        ).lower()

        include_match = True if not includes else any(keyword in haystack for keyword in includes)
        if not include_match:
            stats["excluded_missing_include"] += 1
            continue

        exclude_match = any(keyword in haystack for keyword in excludes)
        if exclude_match:
            stats["excluded_by_exclude"] += 1
            continue

        filtered.append(job)

    stats["output"] = len(filtered)
    return filtered, stats




def resolve_github_pages_url(cfg: dict[str, Any]) -> str:
    configured_url = str(cfg.get("github_pages_url", "")).strip()
    if configured_url:
        return configured_url

    env_url = os.getenv("GITHUB_PAGES_URL", "").strip()
    if env_url:
        return env_url

    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if repository and "/" in repository:
        owner, repo = repository.split("/", 1)
        return f"https://{owner}.github.io/{quote(repo)}/"

    return ""

def write_outputs(jobs: list[dict[str, Any]], github_pages_url: str = "") -> None:
    JOBS_JSON.write_text(json.dumps(jobs, indent=2))

    with JOBS_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "title",
            "company",
            "platform",
            "location",
            "department",
            "team",
            "employment_type",
            "job_function",
            "is_technical",
            "posted_at",
            "updated_at",
            "first_seen_at",
            "last_seen_at",
            "is_new",
            "url",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow({name: job.get(name, "") for name in fieldnames})

    DOCS_HTML.parent.mkdir(parents=True, exist_ok=True)
    DOCS_HTML.write_text(render_html(jobs, github_pages_url=github_pages_url), encoding="utf-8")


def maybe_send_email(jobs: list[dict[str, Any]], email_cfg: dict[str, Any]) -> None:
    if not email_cfg.get("enabled"):
        print("[info] Email disabled.")
        return

    sender = os.getenv("SMTP_FROM")
    recipient = os.getenv("SMTP_TO")
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    port = int(os.getenv("SMTP_PORT", "587"))

    missing = [name for name, value in {
        "SMTP_FROM": sender,
        "SMTP_TO": recipient,
        "SMTP_HOST": host,
        "SMTP_USER": user,
        "SMTP_PASS": password,
    }.items() if not value]
    if missing:
        print(f"[warn] Email enabled but missing secrets: {', '.join(missing)}")
        return

    message = EmailMessage()
    message["Subject"] = f"Chief of Staff jobs digest ({len(jobs)})"
    message["From"] = sender
    message["To"] = recipient
    lines = [f"{job['title']} — {job['company']} ({job['platform']})\n{job['url']}" for job in jobs[:100]]
    if not lines:
        lines = ["No matching jobs found today."]
    message.set_content("\n\n".join(lines))

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(message)

    print("[info] Email sent.")


def main() -> None:
    cfg = apply_runtime_overrides(load_config())
    maybe_download_sources_csv(cfg)

    sources = get_sources(cfg)
    print(f"[info] Using {len(sources)} sources")

    all_jobs = []
    for source in sources:
        source_jobs = fetch_jobs_for_source(source)
        print(f"[info] {source.platform}:{source.company} returned {len(source_jobs)} jobs")
        all_jobs.extend(source_jobs)

    print(f"[info] Total fetched jobs before filtering: {len(all_jobs)}")

    previous_jobs = load_previous_jobs()

    include_keywords = cfg.get("keywords_include", cfg.get("keywords", []))
    exclude_keywords = cfg.get("keywords_exclude", [])
    filtered_jobs, filter_stats = filter_jobs(all_jobs, include_keywords, exclude_keywords)

    print(f"[info] Filter stats: input={filter_stats['input']}, missing_chief_of_staff_title={filter_stats['excluded_missing_chief_of_staff_title']}, missing_include={filter_stats['excluded_missing_include']}, excluded={filter_stats['excluded_by_exclude']}, output={filter_stats['output']}")

    unique_jobs = {job.get("url") or f"{job.get('company')}:{job.get('title')}": job for job in filtered_jobs}
    jobs = sorted(unique_jobs.values(), key=lambda j: (j.get("company", ""), j.get("title", "")))

    run_at = utc_now_iso()
    jobs, run_stats = enrich_jobs_with_history_and_flags(jobs, previous_jobs, run_at)

    github_pages_url = resolve_github_pages_url(cfg)
    write_outputs(jobs, github_pages_url=github_pages_url)
    write_run_meta(run_at, total_jobs=len(jobs), new_jobs=run_stats["new_count"])
    maybe_send_email(jobs, cfg.get("email", {}))
    print(f"[info] Wrote {len(jobs)} jobs to jobs.json, jobs.csv, and docs/index.html")
    print(f"[info] New since last run: {run_stats['new_count']}")
    if github_pages_url:
        print(f"[info] GitHub Pages URL: {github_pages_url}")


if __name__ == "__main__":
    main()
