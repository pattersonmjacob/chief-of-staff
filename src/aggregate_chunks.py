from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

from main import (  # noqa: E402
    RUN_META_JSON,
    apply_runtime_overrides,
    load_previous_jobs,
    load_config,
    process_jobs_pipeline,
    write_outputs,
    write_run_meta,
)
from update_readme_roles import update_readme  # noqa: E402

AGGREGATE_SUMMARY_JSON = ROOT / "data" / "aggregate_summary.json"


def _detect_platform_from_name(path: Path) -> str:
    name = path.stem.lower()
    for platform in ("greenhouse", "lever"):
        if f"_{platform}_" in name or name.endswith(f"_{platform}"):
            return platform
    return "unknown"


def _load_chunk_jobs(chunks_dir: Path) -> tuple[list[dict], dict[str, int], dict[str, int], list[str]]:
    chunk_files = sorted(chunks_dir.glob("jobs_*.json"))
    all_jobs: list[dict] = []
    platform_jobs: dict[str, int] = {"greenhouse": 0, "lever": 0, "unknown": 0}
    platform_files: dict[str, int] = {"greenhouse": 0, "lever": 0, "unknown": 0}
    invalid_files: list[str] = []

    for path in chunk_files:
        platform = _detect_platform_from_name(path)
        platform_files[platform] = platform_files.get(platform, 0) + 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                all_jobs.extend(data)
                platform_jobs[platform] = platform_jobs.get(platform, 0) + len(data)
            else:
                invalid_files.append(path.name)
                print(f"[warn] Skipping non-list chunk file {path}")
        except Exception as exc:
            invalid_files.append(path.name)
            print(f"[warn] Skipping invalid chunk file {path}: {exc}")

    print(f"[info] Loaded {len(all_jobs)} raw jobs from {len(chunk_files)} chunk files")
    print(
        "[info] Raw chunk files by platform: "
        + ", ".join(f"{p}={platform_files.get(p, 0)}" for p in ["greenhouse", "lever", "unknown"])
    )
    print(
        "[info] Raw jobs by platform (from artifact names): "
        + ", ".join(f"{p}={platform_jobs.get(p, 0)}" for p in ["greenhouse", "lever", "unknown"])
    )
    return all_jobs, platform_jobs, platform_files, invalid_files


def _build_runtime_cfg(args: argparse.Namespace) -> dict[str, object]:
    cfg = apply_runtime_overrides(load_config())
    cfg["validate_job_links"] = not args.disable_link_validation
    cfg["link_check_delay_seconds"] = max(0.0, args.link_check_delay_seconds)
    cfg["max_job_age_days"] = max(0, args.max_job_age_days)
    return cfg


def _write_aggregate_summary(
    result_jobs: int,
    chief_jobs: int,
    strategy_ops_jobs: int,
    raw_platform_jobs: dict[str, int],
    raw_platform_files: dict[str, int],
    invalid_files: list[str],
    validate_links: bool,
    repository: str,
) -> None:
    AGGREGATE_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    generated_at = ""
    if RUN_META_JSON.exists():
        try:
            generated_at = str(json.loads(RUN_META_JSON.read_text(encoding="utf-8")).get("last_run_at", ""))
        except Exception:
            generated_at = ""
    summary = {
        "repository": repository,
        "generated_at": generated_at,
        "validate_job_links": validate_links,
        "raw_platform_jobs": raw_platform_jobs,
        "raw_platform_files": raw_platform_files,
        "invalid_chunk_files": invalid_files,
        "total_jobs": result_jobs,
        "chief_of_staff_jobs": chief_jobs,
        "strategy_ops_jobs": strategy_ops_jobs,
    }
    AGGREGATE_SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    docs_data_dir = ROOT / "docs" / "data"
    docs_data_dir.mkdir(parents=True, exist_ok=True)
    (docs_data_dir / "aggregate_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate chunked job artifacts and rebuild outputs")
    parser.add_argument("--chunks-dir", default="chunk-artifacts")
    parser.add_argument("--repository", default="")
    parser.add_argument("--link-check-delay-seconds", type=float, default=0.8)
    parser.add_argument("--max-job-age-days", type=int, default=7)
    parser.add_argument("--disable-link-validation", action="store_true")
    args = parser.parse_args()

    chunks_dir = ROOT / args.chunks_dir
    raw_jobs, raw_platform_jobs, raw_platform_files, invalid_files = _load_chunk_jobs(chunks_dir)
    raw_platform_counts: dict[str, int] = {"greenhouse": 0, "lever": 0, "unknown": 0}
    for job in raw_jobs:
        platform = str(job.get("platform", "")).strip().lower()
        if platform not in raw_platform_counts:
            platform = "unknown"
        raw_platform_counts[platform] += 1
    print(
        "[info] Raw merged jobs by platform: "
        + ", ".join(f"{p}={raw_platform_counts.get(p, 0)}" for p in ["greenhouse", "lever", "unknown"])
    )
    cfg = _build_runtime_cfg(args)
    previous_jobs = load_previous_jobs()
    result = process_jobs_pipeline(raw_jobs, cfg, previous_jobs=previous_jobs)
    write_outputs(
        result.focused_jobs,
        result.chief_jobs,
        result.strategy_ops_jobs,
    )
    update_readme()
    write_run_meta(
        result.run_at,
        total_jobs=len(result.focused_jobs),
        chief_of_staff_jobs=len(result.chief_jobs),
        new_jobs=result.run_stats["new_count"],
    )
    _write_aggregate_summary(
        result_jobs=len(result.focused_jobs),
        chief_jobs=len(result.chief_jobs),
        strategy_ops_jobs=len(result.strategy_ops_jobs),
        raw_platform_jobs=raw_platform_jobs,
        raw_platform_files=raw_platform_files,
        invalid_files=invalid_files,
        validate_links=result.validate_links,
        repository=args.repository,
    )
    print(
        f"[info] Aggregated {len(result.focused_jobs)} focused jobs "
        f"(chief_of_staff={len(result.chief_jobs)}, strategy_ops={len(result.strategy_ops_jobs)})"
    )


if __name__ == "__main__":
    main()
