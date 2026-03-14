from __future__ import annotations

import argparse
import csv
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


DEFAULT_GREENHOUSE_URL = "https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/greenhouse/greenhouse_companies.csv"
DEFAULT_LEVER_URL = "https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/lever/lever_companies.csv"


def _download_csv_rows(url: str) -> list[dict[str, str]]:
    with urlopen(url, timeout=30) as response:  # nosec B310
        text = response.read().decode("utf-8", errors="replace")
    return list(csv.DictReader(StringIO(text)))


def _pick(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key in row and row[key] and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def _normalize_slug(vendor: str, raw_slug: str) -> str:
    value = (raw_slug or "").strip().lower().strip("/")
    if not value:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        host = (parsed.netloc or "").lower()
        path_parts = [part for part in parsed.path.split("/") if part]

        if vendor == "Greenhouse":
            if "greenhouse.io" in host and path_parts:
                return path_parts[-1].lower()
        elif vendor == "Lever":
            if "lever.co" in host and path_parts:
                return path_parts[-1].lower()
        if path_parts:
            return path_parts[-1].lower()
        return ""

    return value


def _build_board_url(vendor: str, slug: str) -> str:
    if vendor == "Greenhouse":
        return f"https://job-boards.greenhouse.io/{slug}"
    if vendor == "Lever":
        return f"https://jobs.lever.co/{slug}"
    return ""


def merge_source_rows(
    greenhouse_rows: list[dict[str, str]],
    lever_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_rows(rows: list[dict[str, str]], vendor: str) -> None:
        for row in rows:
            raw_slug = _pick(row, ["slug", "company_slug", "board_token", "path", "hostedJobsUrl", "url"])
            slug = _normalize_slug(vendor, raw_slug)
            company = _pick(row, ["company", "name", "title", "organization", "company_name"])
            source_url = _pick(row, ["hostedJobsUrl", "url", "jobs_url", "careers_url"])

            if not slug:
                continue
            key = (vendor, slug)
            if key in seen:
                continue
            seen.add(key)

            board_url = _build_board_url(vendor, slug)
            merged.append(
                {
                    "slug": slug,
                    "vendor": vendor,
                    "company": company or slug,
                    "url": source_url,
                    "board_url": board_url,
                    "open_jobs": "1",
                }
            )

    add_rows(greenhouse_rows, "Greenhouse")
    add_rows(lever_rows, "Lever")
    return merged


def write_sources_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["slug", "vendor", "company", "url", "board_url", "open_jobs"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge ATS company source lists into one CSV")
    parser.add_argument("--output", default="data/company_slugs.csv")
    parser.add_argument("--greenhouse-url", default=DEFAULT_GREENHOUSE_URL)
    parser.add_argument("--lever-url", default=DEFAULT_LEVER_URL)
    args = parser.parse_args()

    greenhouse_rows = _download_csv_rows(args.greenhouse_url)
    lever_rows = _download_csv_rows(args.lever_url)

    merged = merge_source_rows(greenhouse_rows, lever_rows)
    write_sources_csv(merged, Path(args.output))
    print(f"[info] Wrote {len(merged)} merged sources to {args.output}")


if __name__ == "__main__":
    main()
