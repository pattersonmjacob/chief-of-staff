from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _normalize_vendor(value: str) -> str | None:
    normalized = (value or "").strip().lower()
    if "ashby" in normalized:
        return "ashby"
    if "greenhouse" in normalized:
        return "greenhouse"
    if "lever" in normalized:
        return "lever"
    return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value).strip().replace(",", "")
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _pick(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key in row and row[key] is not None and str(row[key]).strip() != "":
            return str(row[key])
    return ""


def load_sources_from_csv(path: str | Path, min_open_jobs: int = 1, max_sources: int | None = None) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"sources CSV not found: {csv_path}")

    sources: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendor_raw = _pick(row, ["vendor", "platform", "source", "ats", "Vendor", "Platform"])
            slug_raw = _pick(row, ["slug", "company_slug", "Slug", "company", "Company"])
            jobs_raw = _pick(row, ["open_jobs", "job_count", "open job count", "Open Jobs", "Job count"])

            vendor = _normalize_vendor(vendor_raw)
            slug = slug_raw.strip().lower().strip("/")
            open_jobs = _to_int(jobs_raw, default=0)

            if not vendor or not slug:
                continue
            if open_jobs < min_open_jobs:
                continue

            key = (vendor, slug)
            if key in seen:
                continue
            seen.add(key)

            sources.append({"platform": vendor, "company": slug})

            if max_sources is not None and len(sources) >= max_sources:
                break

    return sources
