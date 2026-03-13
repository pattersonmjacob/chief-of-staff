from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

from main import (  # noqa: E402
    JOBS_JSON,
    apply_do_not_check_filter,
    apply_runtime_overrides,
    dedupe_sources,
    fetch_all_jobs,
    get_scrape_concurrency,
    get_sources,
    load_config,
    load_do_not_check_state,
    maybe_download_sources_csv,
)


def main() -> None:
    cfg = apply_runtime_overrides(load_config())
    maybe_download_sources_csv(cfg)

    sources = get_sources(cfg)
    do_not_check_state = load_do_not_check_state()
    sources = apply_do_not_check_filter(sources, do_not_check_state)
    sources = dedupe_sources(sources)
    print(f"[info] Using {len(sources)} sources for raw chunk fetch")

    scrape_concurrency = get_scrape_concurrency(cfg, len(sources))
    print(f"[info] Scrape concurrency: {scrape_concurrency}")

    raw_jobs, _ = fetch_all_jobs(
        sources,
        max_workers=scrape_concurrency,
        do_not_check_state=do_not_check_state,
        verbose=bool(cfg.get("verbose_sources", False)),
    )
    print(f"[info] Total fetched raw jobs: {len(raw_jobs)}")
    JOBS_JSON.write_text(json.dumps(raw_jobs, indent=2), encoding="utf-8")
    print(f"[info] Wrote raw chunk jobs to {JOBS_JSON}")


if __name__ == "__main__":
    main()
