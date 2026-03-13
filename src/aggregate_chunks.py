from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

from main import _dedupe_and_collate_jobs, filter_jobs_by_max_age_days, validate_and_filter_jobs_by_link, write_outputs  # noqa: E402


def _detect_platform_from_name(path: Path) -> str:
    name = path.stem.lower()
    for platform in ("greenhouse", "lever", "ashby"):
        if f"_{platform}_" in name or name.endswith(f"_{platform}"):
            return platform
    return "unknown"


def _load_chunk_jobs(chunks_dir: Path) -> tuple[list[dict], dict[str, int], dict[str, int]]:
    chunk_files = sorted(chunks_dir.glob("jobs_*.json"))
    all_jobs: list[dict] = []
    platform_jobs: dict[str, int] = {"greenhouse": 0, "lever": 0, "ashby": 0, "unknown": 0}
    platform_files: dict[str, int] = {"greenhouse": 0, "lever": 0, "ashby": 0, "unknown": 0}

    for path in chunk_files:
        platform = _detect_platform_from_name(path)
        platform_files[platform] = platform_files.get(platform, 0) + 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                all_jobs.extend(data)
                platform_jobs[platform] = platform_jobs.get(platform, 0) + len(data)
        except Exception as exc:
            print(f"[warn] Skipping invalid chunk file {path}: {exc}")

    print(f"[info] Loaded {len(all_jobs)} raw jobs from {len(chunk_files)} chunk files")
    print(
        "[info] Raw chunk files by platform: "
        + ", ".join(f"{p}={platform_files.get(p, 0)}" for p in ["greenhouse", "lever", "ashby", "unknown"])
    )
    print(
        "[info] Raw jobs by platform (from artifact names): "
        + ", ".join(f"{p}={platform_jobs.get(p, 0)}" for p in ["greenhouse", "lever", "ashby", "unknown"])
    )
    return all_jobs, platform_jobs, platform_files


def _github_pages_url(repository: str) -> str:
    repository = repository.strip()
    if repository and "/" in repository:
        owner, repo = repository.split("/", 1)
        return f"https://{owner}.github.io/{quote(repo)}/"
    return ""


def _is_chief_of_staff(job: dict) -> bool:
    title = str(job.get("title", ""))
    return bool(re.search(r"\bchief\b.*\bstaff\b", title, flags=re.IGNORECASE))


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate chunked job artifacts and rebuild outputs")
    parser.add_argument("--chunks-dir", default="chunk-artifacts")
    parser.add_argument("--repository", default="")
    parser.add_argument("--link-check-delay-seconds", type=float, default=0.8)
    parser.add_argument("--max-job-age-days", type=int, default=7)
    parser.add_argument("--disable-link-validation", action="store_true")
    args = parser.parse_args()

    chunks_dir = ROOT / args.chunks_dir
    jobs, _raw_platform_jobs, _raw_platform_files = _load_chunk_jobs(chunks_dir)
    jobs = _dedupe_and_collate_jobs(jobs)
    deduped_platform_counts: dict[str, int] = {"greenhouse": 0, "lever": 0, "ashby": 0, "unknown": 0}
    for job in jobs:
        platform = str(job.get("platform", "")).strip().lower()
        if platform not in deduped_platform_counts:
            platform = "unknown"
        deduped_platform_counts[platform] += 1
    print(
        "[info] Post-dedupe jobs by platform: "
        + ", ".join(f"{p}={deduped_platform_counts.get(p, 0)}" for p in ["greenhouse", "lever", "ashby", "unknown"])
    )
    jobs, age_filter_stats = filter_jobs_by_max_age_days(jobs, max_age_days=max(0, args.max_job_age_days))
    print(f"[info] Age filter stats ({max(0, args.max_job_age_days)}d): input={age_filter_stats['input']}, missing_or_invalid_date={age_filter_stats['excluded_missing_or_invalid_date']}, too_old={age_filter_stats['excluded_too_old']}, output={age_filter_stats['output']}")

    aged_platform_counts: dict[str, int] = {"greenhouse": 0, "lever": 0, "ashby": 0, "unknown": 0}
    for job in jobs:
        platform = str(job.get("platform", "")).strip().lower()
        if platform not in aged_platform_counts:
            platform = "unknown"
        aged_platform_counts[platform] += 1
    print(
        "[info] Post-age-filter jobs by platform: "
        + ", ".join(f"{p}={aged_platform_counts.get(p, 0)}" for p in ["greenhouse", "lever", "ashby", "unknown"])
    )
    jobs = validate_and_filter_jobs_by_link(
        jobs,
        enabled=not args.disable_link_validation,
        delay_seconds=max(0.0, args.link_check_delay_seconds),
    )

    validated_platform_counts: dict[str, int] = {"greenhouse": 0, "lever": 0, "ashby": 0, "unknown": 0}
    for job in jobs:
        platform = str(job.get("platform", "")).strip().lower()
        if platform not in validated_platform_counts:
            platform = "unknown"
        validated_platform_counts[platform] += 1
    print(
        "[info] Post-link-validation jobs by platform: "
        + ", ".join(f"{p}={validated_platform_counts.get(p, 0)}" for p in ["greenhouse", "lever", "ashby", "unknown"])
    )
    chief_jobs = [job for job in jobs if _is_chief_of_staff(job)]
    for job in jobs:
        job["is_chief_of_staff"] = _is_chief_of_staff(job)

    pages_url = _github_pages_url(args.repository)
    write_outputs(jobs, chief_jobs, github_pages_url=pages_url)
    print(f"[info] Aggregated {len(jobs)} unique jobs (chief_of_staff={len(chief_jobs)})")


if __name__ == "__main__":
    main()
