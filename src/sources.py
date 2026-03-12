from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

VENDOR_MAP = {
    "ashby": "ashby",
    "greenhouse": "greenhouse",
    "lever": "lever",
}


def _normalize_vendor(value: str) -> str | None:
    normalized = (value or "").strip().lower()
    return VENDOR_MAP.get(normalized)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def load_sources_from_csv(
    path: str | Path,
    min_open_jobs: int = 1,
    max_sources: int | None = None,
    source_offset: int = 0,
) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"sources CSV not found: {csv_path}")

    sources: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_offset = max(0, source_offset)
    skipped = 0

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor = _normalize_vendor(row.get("vendor", ""))
            slug = (row.get("slug", "") or "").strip().lower()
            source_url = (row.get("url") or row.get("hostedJobsUrl") or row.get("hosted_jobs_url") or "").strip()
            board_url = (row.get("board_url") or "").strip()
            open_jobs = _to_int(row.get("open_jobs") or row.get("job_count"), default=0)

            if not vendor or not slug:
                continue
            if open_jobs < min_open_jobs:
                continue

            key = (vendor, slug)
            if key in seen:
                continue
            seen.add(key)

            if skipped < source_offset:
                skipped += 1
                continue

            source_item: dict[str, str] = {"platform": vendor, "company": slug}
            if board_url or source_url:
                source_item["url"] = board_url or source_url
            if source_url:
                source_item["source_url"] = source_url
            if board_url:
                source_item["board_url"] = board_url
            sources.append(source_item)

            if max_sources is not None and len(sources) >= max_sources:
                break

    return sources
