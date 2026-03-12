# chief-of-staff

Version 1 of a free, keyword-based jobs pipeline.

## What it does

- Pulls jobs from **Greenhouse**, **Lever**, and **Ashby** job boards.
- Filters jobs with keyword include/exclude matching (no AI/ranking yet).
- Hard-requires job title to match `chief ... staff` (case-insensitive wildcard) before other include/exclude filtering.
- Filters jobs with simple keyword matching (no AI/ranking yet).
- Writes output files:
  - `jobs.json`
  - `jobs.csv`
  - `docs/index.html` (for GitHub Pages)
  - Tracks `first_seen_at` / `last_seen_at` and marks `is_new` for jobs newly seen since the prior run.
- Automatically tracks repeated HTTP 404 sources in `data/do_not_check.json` and skips them on future runs (after 3+ 404s and a healthy non-404 streak guard).
  - Optional GitHub Pages link banner in output (set `github_pages_url` or let Actions auto-detect).
- Can optionally send an email digest through SMTP (using GitHub Actions secrets).

## Setup

1. Copy config template:

   ```bash
   cp config.example.json config.json
   ```

2. Choose source mode in `config.json`:

   - **Automatic source list (recommended):**
     - Set `sources_csv` to a local CSV path (for example `data/company_slugs.csv`).
     - Optionally set `sources_csv_url` and the script will download the CSV before reading it.
     - Optional controls:
       - `min_open_jobs` (default `1`)
       - `max_sources` (optional; leave empty or `null` for no cap)
       - `max_sources_per_platform` (default `500`; cap applied independently to Greenhouse/Lever/Ashby)
       - `scrape_concurrency` (default `1`; set to `1` for no in-process concurrency)
       - `validate_job_links` (default `true`; verifies job URLs before publishing and removes unavailable postings)
       - `link_check_delay_seconds` (default `0.8`; delay between URL checks to avoid rate limits)
       - `verbose_sources` (default `false`; when true logs every source result)

   - **Manual source list:**
     - Keep `sources_csv` empty or remove it.
     - Add known company slugs under `sources`.

3. Configure keyword filters:
   - `keywords_include`: terms to keep.
   - `keywords_exclude`: terms to drop after include matching.

4. Run locally:

   ```bash
   python src/main.py
   ```

   Optional fast-run override:

   ```bash
   SCRAPE_CONCURRENCY=32 python src/main.py
   ```

   Optional request pacing override (useful for very large lists):

   ```bash
   MIN_REQUEST_INTERVAL_SECONDS=0.35 SCRAPE_CONCURRENCY=6 python src/main.py
   ```

## Source CSV format

The CSV should include (at minimum):
- `slug`
- `vendor` (`Ashby`, `Greenhouse`, `Lever`)
- `open_jobs` (or `job_count`)

Optional but recommended:
- `url` (the hosted jobs page or board URL for fallback parsing)

Only supported vendors are loaded. Duplicate `(vendor, slug)` pairs are deduplicated.

## GitHub Actions

There are two workflows:

1. **Daily jobs digest** (`.github/workflows/daily.yml`)
   - Runs daily via cron (`15 12 * * *`) and on manual trigger.
   - Uses `SOURCES_CSV=data/company_slugs.csv` so daily scraping reads the repo-pinned source list.

2. **Refresh company source list** (`.github/workflows/refresh-sources-weekly.yml`)
   - Runs weekly on Mondays (`0 9 * * 1`) and on manual trigger.
   - Pulls and merges these upstream lists into `data/company_slugs.csv` and commits the updated file:
     - `https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/lever/lever_companies.csv`
     - `https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/greenhouse/greenhouse_companies.csv`
     - `https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/ashby/companies.csv`

This gives you a stable, versioned source list in-repo that is refreshed weekly and consumed daily.

### Required repo settings

1. **Actions write permissions**
   - Settings → Actions → General → Workflow permissions → **Read and write permissions**.

2. **Branch rules**
   - If branch protection is on, ensure workflow commits are allowed or switch to PR-based updates.

3. **Pages**
   - Settings → Pages → Source: **Deploy from branch**
   - Branch: `main`
   - Folder: `/docs`
   - If your site still shows the README, switch the Pages folder to `/docs` and save again. This repo also includes a root `index.html` redirect to `/docs/` as a fallback.

## Avoiding rate limits

- Lower parallelism in your runtime config if you see HTTP 429s:
  - Set `"scrape_concurrency": 1` in `config.json`, or run with `SCRAPE_CONCURRENCY=1` for fully sequential requests.
- Add per-request pacing for big source lists:
  - Set `MIN_REQUEST_INTERVAL_SECONDS=0.35` to add a small cross-thread gap between requests per host.
- Keep chunk jobs from overloading providers:
  - The daily workflow runs a single sequential digest job (`SCRAPE_CONCURRENCY=1`) and caps sources at `MAX_SOURCES_PER_PLATFORM=500`.
- Retries are built in for temporary provider limits/errors:
  - Scraper requests now back off and retry for `429/5xx` responses.
- Source-identifier fallback is enabled:
  - If a slug fails (for example malformed/stale slug), the scraper retries using the parsed `url` identifier when available.
- Publish-time link checks are enabled:
  - Jobs whose URLs return errors or “no longer active / page not found” pages are removed before writing outputs.

### Large-list tuning playbook (fast + fewer rate limits)

- Start with `SCRAPE_CONCURRENCY=1`, `MAX_SOURCES_PER_PLATFORM=500`, and `MIN_REQUEST_INTERVAL_SECONDS=0.35`.
- If you still see many 429s, lower concurrency to `6` then `4` before increasing the interval.
- If 429s are low and runtime is too slow, increase concurrency gradually (`10`, `12`) while keeping interval in place.
- Keep chunking enabled (`MAX_SOURCES` + `SOURCE_OFFSET`) so failures are isolated and retries are cheaper.

## Optional SMTP email

If `"email": {"enabled": true}` in `config.json`, set these repository secrets:

- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_HOST`
- `SMTP_PORT` (optional, defaults to `587`)
- `SMTP_USER`
- `SMTP_PASS`

If secrets are missing, the script logs a warning and skips sending.

## Troubleshooting

- If workflow runs but returns zero jobs:
  - Verify `sources_csv` exists and has valid `slug` + `vendor` values.
  - Confirm vendor names map to supported platforms (`Ashby`, `Greenhouse`, `Lever`).
  - Check keyword filters are not overly restrictive.

- If the run fails with `JSONDecodeError`:
  - Open `config.json` (or `config.example.json` if using fallback).
  - Fix JSON syntax near the reported line/column (missing comma/trailing quote are common).
  - You can validate locally with: `python -m json.tool config.json`.

- If you hit frequent merge conflicts on generated artifacts (`jobs.json`, `jobs.csv`, `docs/index.html`):
  - Pull latest `main`, rerun `python src/main.py`, then commit only the regenerated outputs.
  - Keep feature/code changes separate from generated-output update commits.
  - This repo marks generated outputs in `.gitattributes` to reduce repeated conflicts during merges.
  - CI aggregation logic is centralized in `src/aggregate_chunks.py` (instead of a long inline workflow script) to reduce workflow-file merge conflicts.

- If workflow fails to push updated artifacts:
  - Recheck Actions write permissions and branch protection settings.


## Filtering behavior

- Hard requirement: title must match `chief ... staff` (case-insensitive).
- Keyword include/exclude checks run against: title, department, team, location, and description text (when available from the source API).
- Duplicate jobs from the same platform/company/title are merged into one record, collating differences like locations/teams/departments/URLs.

## Security checklist

- Do **not** commit `config.json` if it contains private values. Keep secrets in GitHub Actions secrets.
- SMTP credentials are read from environment variables (`SMTP_*`) and are not written to artifacts.
- Use HTTPS-only upstream endpoints (Greenhouse/Lever/Ashby APIs) and avoid adding arbitrary untrusted URLs.
