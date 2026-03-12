from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from json import JSONDecodeError
import os
import re
import smtplib
import time
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from render import render_html
from scrapers import CompanySource, FetchResult, fetch_jobs_for_source_status
from sources import load_sources_from_csv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config.example.json"
JOBS_JSON = ROOT / "jobs.json"
JOBS_CSV = ROOT / "jobs.csv"
DOCS_HTML = ROOT / "docs" / "index.html"
RUN_META_JSON = ROOT / "data" / "run_meta.json"
DO_NOT_CHECK_JSON = ROOT / "data" / "do_not_check.json"




def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _job_key(job: dict[str, Any]) -> str:
    return str(job.get("url") or f"{job.get('platform')}:{job.get('company')}:{job.get('title')}")


def _merge_pipe_values(*values: Any) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        for part in [piece.strip() for piece in raw.split("|")]:
            lowered = part.lower()
            if part and lowered not in seen:
                parts.append(part)
                seen.add(lowered)
    return " | ".join(parts)


def _split_pipe_values(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def _select_primary_url(*values: Any) -> str:
    for value in values:
        for candidate in _split_pipe_values(value):
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
    return ""


def _dedupe_and_collate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for job in jobs:
        key = f"{str(job.get('platform', '')).lower()}::{str(job.get('company', '')).lower()}::{str(job.get('title', '')).strip().lower()}"
        current = merged.get(key)
        if current is None:
            merged[key] = dict(job)
            continue

        for field in ["location", "department", "team", "employment_type"]:
            current[field] = _merge_pipe_values(current.get(field, ""), job.get(field, ""))
        current["url"] = _select_primary_url(current.get("url", ""), job.get("url", ""))

        current_description = str(current.get("description") or "")
        incoming_description = str(job.get("description") or "")
        if len(incoming_description) > len(current_description):
            current["description"] = incoming_description

        posted_values = [str(v) for v in [current.get("posted_at", ""), job.get("posted_at", "")] if str(v or "").strip()]
        if posted_values:
            current["posted_at"] = min(posted_values)

        updated_values = [str(v) for v in [current.get("updated_at", ""), job.get("updated_at", "")] if str(v or "").strip()]
        if updated_values:
            current["updated_at"] = max(updated_values)

    return sorted(merged.values(), key=lambda j: (str(j.get("company", "")), str(j.get("title", ""))))


def validate_and_filter_jobs_by_link(
    jobs: list[dict[str, Any]],
    enabled: bool = True,
    delay_seconds: float = 0.8,
    timeout_seconds: int = 15,
) -> list[dict[str, Any]]:
    if not enabled:
        return jobs

    blocked_markers = [
        "job board you were viewing is no longer active",
        "page not found",
        "job not available",
        "job is no longer available",
        "no longer accepting applications",
    ]

    checked: list[dict[str, Any]] = []
    dropped = 0
    for idx, job in enumerate(jobs, start=1):
        url = str(job.get("url", "")).strip()
        print(f"[info] URL check {idx}/{len(jobs)}: {url or '<empty>'}")
        if not url:
            dropped += 1
            print(f"[warn] Dropping job with empty URL: {job.get('company')} | {job.get('title')}")
            continue

        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ChiefOfStaffJobsBot/1.1; +https://github.com/)"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                status = int(getattr(response, "status", 200) or 200)
                body = response.read(220_000).decode("utf-8", errors="ignore").lower()
            print(f"[info] URL check result {status}: {url}")
            if status >= 400 or any(marker in body for marker in blocked_markers):
                dropped += 1
                print(f"[warn] Dropping unavailable job link ({status}): {url}")
            else:
                checked.append(job)
        except Exception as exc:
            checked.append(job)
            print(f"[warn] URL check skipped for {url}: {exc}")

        if idx < len(jobs) and delay_seconds > 0:
            time.sleep(delay_seconds)

    if dropped:
        print(f"[info] Link validation removed {dropped} jobs; {len(checked)} remain")
    return checked


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




def load_do_not_check_state() -> dict[str, Any]:
    if not DO_NOT_CHECK_JSON.exists():
        return {"counts": {}, "blocked": {}}
    try:
        data = json.loads(DO_NOT_CHECK_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"counts": {}, "blocked": {}}
        counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
        blocked = data.get("blocked") if isinstance(data.get("blocked"), dict) else {}
        return {"counts": counts, "blocked": blocked}
    except Exception:
        return {"counts": {}, "blocked": {}}


def write_do_not_check_state(state: dict[str, Any]) -> None:
    DO_NOT_CHECK_JSON.parent.mkdir(parents=True, exist_ok=True)
    DO_NOT_CHECK_JSON.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def source_key(platform: str, slug: str) -> str:
    return f"{platform}:{slug}"


def apply_do_not_check_filter(sources: list[CompanySource], state: dict[str, Any]) -> list[CompanySource]:
    blocked = state.get("blocked", {})
    filtered: list[CompanySource] = []
    skipped = 0
    for source in sources:
        key = source_key(source.platform, source.company)
        if key in blocked:
            skipped += 1
            continue
        filtered.append(source)

    if skipped:
        print(f"[info] Skipped {skipped} sources from do-not-check list")
    return filtered


def update_404_block_state(
    state: dict[str, Any],
    result: FetchResult,
    non_404_streak: int,
    health_ready: bool,
    min_non_404_streak: int = 25,
) -> tuple[dict[str, Any], int, bool]:
    counts = state.setdefault("counts", {})
    blocked = state.setdefault("blocked", {})

    key = source_key(result.source.platform, result.normalized_company or result.source.company)

    if result.http_status == 404:
        new_count = int(counts.get(key, 0)) + 1
        counts[key] = new_count
        if new_count > 2 and health_ready and key not in blocked:
            blocked[key] = {
                "blocked_at": utc_now_iso(),
                "reason": f"HTTP 404 repeated {new_count} times after healthy non-404 streak gate",
            }
            print(f"[warn] Added to do-not-check list: {key}")
        return state, 0, health_ready

    # Any non-404 outcome increments health streak and can unlock 404 blocking.
    next_streak = non_404_streak + 1
    return state, next_streak, (health_ready or next_streak > min_non_404_streak)


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path.name} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc




def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_scrape_concurrency(cfg: dict[str, Any], source_count: int) -> int:
    env_value = os.getenv("SCRAPE_CONCURRENCY", "").strip()
    if env_value:
        return max(1, _to_int(env_value, 4))

    configured = cfg.get("scrape_concurrency", 4)
    workers = max(1, _to_int(configured, 4))
    return min(workers, max(1, source_count))


def fetch_all_jobs(
    sources: list[CompanySource],
    max_workers: int,
    do_not_check_state: dict[str, Any],
    verbose: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not sources:
        return [], do_not_check_state

    all_jobs: list[dict[str, Any]] = []
    completed = 0
    non_404_streak = 0
    health_ready = False
    failed_sources = 0
    rate_limited_sources = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(fetch_jobs_for_source_status, source): source for source in sources}
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            result = FetchResult(source=source, normalized_company=source.company, jobs=[], error="future_failed")
            try:
                result = future.result()
            except Exception as exc:  # defensive: fetcher normally swallows network errors
                print(f"[warn] {source.platform}:{source.company} failed unexpectedly: {exc}")

            all_jobs.extend(result.jobs)
            if result.error:
                failed_sources += 1
            if result.http_status == 429 or "429" in str(result.error):
                rate_limited_sources += 1
            do_not_check_state, non_404_streak, health_ready = update_404_block_state(
                state=do_not_check_state,
                result=result,
                non_404_streak=non_404_streak,
                health_ready=health_ready,
                min_non_404_streak=25,
            )

            completed += 1
            if verbose or completed % 100 == 0 or completed == len(sources):
                status = result.http_status if result.http_status is not None else "ok"
                print(
                    f"[info] Progress {completed}/{len(sources)} · "
                    f"{source.platform}:{source.company} status={status} jobs={len(result.jobs)}"
                )

    print(f"[info] Source fetch summary: total={len(sources)} failed={failed_sources} rate_limited={rate_limited_sources} jobs={len(all_jobs)}")
    return all_jobs, do_not_check_state


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
    env_max_sources = os.getenv("MAX_SOURCES", "").strip()
    env_source_offset = os.getenv("SOURCE_OFFSET", "").strip()
    env_max_sources_per_platform = os.getenv("MAX_SOURCES_PER_PLATFORM", "").strip()
    env_validate_job_links = os.getenv("VALIDATE_JOB_LINKS", "").strip().lower()
    env_link_check_delay_seconds = os.getenv("LINK_CHECK_DELAY_SECONDS", "").strip()

    if env_sources_csv:
        updated["sources_csv"] = env_sources_csv
        print(f"[info] Using SOURCES_CSV override: {env_sources_csv}")

    if env_sources_csv_url:
        updated["sources_csv_url"] = env_sources_csv_url
        print("[info] Using SOURCES_CSV_URL override")

    if env_max_sources:
        updated["max_sources"] = int(env_max_sources)
        print(f"[info] Using MAX_SOURCES override: {env_max_sources}")

    if env_source_offset:
        updated["source_offset"] = int(env_source_offset)
        print(f"[info] Using SOURCE_OFFSET override: {env_source_offset}")

    if env_max_sources_per_platform:
        updated["max_sources_per_platform"] = int(env_max_sources_per_platform)
        print(f"[info] Using MAX_SOURCES_PER_PLATFORM override: {env_max_sources_per_platform}")

    if env_validate_job_links in {"true", "false", "1", "0", "yes", "no"}:
        updated["validate_job_links"] = env_validate_job_links in {"true", "1", "yes"}
        print(f"[info] Using VALIDATE_JOB_LINKS override: {updated['validate_job_links']}")

    if env_link_check_delay_seconds:
        updated["link_check_delay_seconds"] = float(env_link_check_delay_seconds)
        print(f"[info] Using LINK_CHECK_DELAY_SECONDS override: {env_link_check_delay_seconds}")

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

    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ChiefOfStaffJobsBot/1.1; +https://github.com/)"})
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
        source_offset = int(cfg.get("source_offset", 0))
        try:
            source_rows = load_sources_from_csv(
                ROOT / sources_csv,
                min_open_jobs=min_open_jobs,
                max_sources=max_sources_int,
                source_offset=source_offset,
            )
            print(f"[info] Loaded {len(source_rows)} sources from {sources_csv} (offset={source_offset}, max={max_sources_int})")
        except FileNotFoundError:
            print(f"[warn] sources_csv not found at {sources_csv}; falling back to config.sources")

    max_per_platform = int(cfg.get("max_sources_per_platform", 0) or 0)
    if max_per_platform > 0:
        platform_counts: dict[str, int] = {}
        limited_rows: list[dict[str, Any]] = []
        for item in source_rows:
            platform = str(item.get("platform", "")).lower().strip()
            if platform not in {"greenhouse", "lever", "ashby"}:
                continue
            count = platform_counts.get(platform, 0)
            if count >= max_per_platform:
                continue
            limited_rows.append(item)
            platform_counts[platform] = count + 1
        source_rows = limited_rows
        print(
            "[info] Applied per-platform cap: "
            + ", ".join(f"{p}={platform_counts.get(p, 0)}" for p in ["greenhouse", "lever", "ashby"])
        )

    return [CompanySource(**item) for item in source_rows]




def dedupe_sources(sources: list[CompanySource]) -> list[CompanySource]:
    seen: set[str] = set()
    deduped: list[CompanySource] = []
    skipped = 0
    for source in sources:
        key = source_key(source.platform, source.company.strip().lower())
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        deduped.append(source)

    if skipped:
        print(f"[info] Removed {skipped} duplicate sources before scraping")
    return deduped


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
    do_not_check_state = load_do_not_check_state()
    sources = apply_do_not_check_filter(sources, do_not_check_state)
    sources = dedupe_sources(sources)
    print(f"[info] Using {len(sources)} sources")

    scrape_concurrency = get_scrape_concurrency(cfg, len(sources))
    verbose_sources = bool(cfg.get("verbose_sources", False))
    print(f"[info] Scrape concurrency: {scrape_concurrency}")

    all_jobs, do_not_check_state = fetch_all_jobs(
        sources,
        max_workers=scrape_concurrency,
        do_not_check_state=do_not_check_state,
        verbose=verbose_sources,
    )

    print(f"[info] Total fetched jobs before filtering: {len(all_jobs)}")

    previous_jobs = load_previous_jobs()

    include_keywords = cfg.get("keywords_include", cfg.get("keywords", []))
    exclude_keywords = cfg.get("keywords_exclude", [])
    filtered_jobs, filter_stats = filter_jobs(all_jobs, include_keywords, exclude_keywords)

    print(f"[info] Filter stats: input={filter_stats['input']}, missing_chief_of_staff_title={filter_stats['excluded_missing_chief_of_staff_title']}, missing_include={filter_stats['excluded_missing_include']}, excluded={filter_stats['excluded_by_exclude']}, output={filter_stats['output']}")

    jobs = _dedupe_and_collate_jobs(filtered_jobs)
    validate_links = bool(cfg.get("validate_job_links", True))
    link_check_delay_seconds = float(cfg.get("link_check_delay_seconds", 0.8) or 0.8)
    jobs = validate_and_filter_jobs_by_link(jobs, enabled=validate_links, delay_seconds=link_check_delay_seconds)

    run_at = utc_now_iso()
    jobs, run_stats = enrich_jobs_with_history_and_flags(jobs, previous_jobs, run_at)

    github_pages_url = resolve_github_pages_url(cfg)
    write_outputs(jobs, github_pages_url=github_pages_url)
    write_run_meta(run_at, total_jobs=len(jobs), new_jobs=run_stats["new_count"])
    write_do_not_check_state(do_not_check_state)
    maybe_send_email(jobs, cfg.get("email", {}))
    print(f"[info] Wrote {len(jobs)} jobs to jobs.json, jobs.csv, and docs/index.html")
    print(f"[info] New since last run: {run_stats['new_count']}")
    if github_pages_url:
        print(f"[info] GitHub Pages URL: {github_pages_url}")


if __name__ == "__main__":
    main()
