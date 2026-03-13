# chief-of-staff

Version 1 of a free, keyword-based jobs pipeline.

## What it does

## Latest Chief of Staff roles

<!-- START_COS_ROLES -->
_Chief-of-Staff matches: 15 · Snapshot timestamp: 2026-03-12 23:25 UTC_
- Chief of Defence Staff or equivalent to the Affected Nation — spektrum (greenhouse) — Stavanger, Norway — 2026-03-12T11:27:09-04:00 — [Link](https://spektrum-group.com/jobs?gh_jid=4371968101)
- Chief of Staff, Sales  — stripe (greenhouse) — SF — 2026-03-06T18:52:06-05:00 — [Link](https://stripe.com/jobs/search?gh_jid=7600099)
- Chief of Staff — mochihealth (greenhouse) — San Francisco, CA — 2026-03-11T01:01:02-04:00 — [Link](https://job-boards.greenhouse.io/mochihealth/jobs/5119052008)
- Chief of Staff — interfaceai (greenhouse) — San Francisco / Palo Alto (In-Office) — 2026-03-09T13:03:07-04:00 — [Link](https://job-boards.greenhouse.io/interfaceai/jobs/4608965006)
- Chief of Staff, Tactical Recon & Strike — andurilindustries (greenhouse) — Costa Mesa, California, United States — 2026-03-12T19:25:18-04:00 — [Link](https://boards.greenhouse.io/andurilindustries/jobs/5068434007?gh_jid=5068434007)
- Chief of Staff, Design — andurilindustries (greenhouse) — Costa Mesa, California, United States — 2026-03-12T19:25:18-04:00 — [Link](https://boards.greenhouse.io/andurilindustries/jobs/4740150007?gh_jid=4740150007)
- Chief of Staff, Air Dominance & Strike  — andurilindustries (greenhouse) — Costa Mesa, California, United States — 2026-03-12T19:25:18-04:00 — [Link](https://boards.greenhouse.io/andurilindustries/jobs/4841348007?gh_jid=4841348007)
- Chief of Staff to CFO/COO — babylist (greenhouse) — Emeryville, CA — 2026-03-12T08:00:47-04:00 — [Link](https://job-boards.greenhouse.io/babylist/jobs/5690329004)
- Executive Leadership Programme - Chief of Staff (Europe) — banyansoftware (greenhouse) — Denmark; Netherlands; Sweden — 2026-03-12T05:12:58-04:00 — [Link](https://job-boards.greenhouse.io/banyansoftware/jobs/5012912007)
- Executive Leadership Program - Chief of Staff — banyansoftware (greenhouse) — United States — 2026-03-12T05:12:58-04:00 — [Link](https://job-boards.greenhouse.io/banyansoftware/jobs/4980694007)
- Technical Chief of Staff for ASIC Engineering — asteralabs (greenhouse) — San Jose, CA — 2026-03-11T16:45:21-04:00 — [Link](https://job-boards.greenhouse.io/asteralabs/jobs/4632063005)
- Chief of Staff - R&D — addepar1 (greenhouse) — New York, NY — 2026-03-11T14:22:13-04:00 — [Link](https://job-boards.greenhouse.io/addepar1/jobs/8120254002)
- Chief of Staff to CEO of BridgeBio and GondolaBio — bridgebio (greenhouse) — Palo Alto - 3160 Porter — 2026-03-10T16:48:30-04:00 — [Link](https://job-boards.greenhouse.io/bridgebio/jobs/5067375007)
- Chief of Staff — blankstreet (greenhouse) — New York City — 2026-03-06T12:44:49-05:00 — [Link](https://job-boards.greenhouse.io/blankstreet/jobs/7621264003)
- Chief of Staff — arine (greenhouse) — San Francisco, CA (Hybrid) — 2026-03-05T21:29:40-05:00 — [Link](https://job-boards.greenhouse.io/arine/jobs/5737836004)
<!-- END_COS_ROLES -->

- Pulls jobs from **Greenhouse**, **Lever**, and **Ashby** job boards.
- Stores the full ATS job feed across Greenhouse / Lever / Ashby.
- Computes a Chief-of-Staff subset using title + include/exclude keyword matching.
- Writes output files:
  - `jobs.json` (full feed)
  - `jobs.csv` (full feed)
  - `jobs_chief_of_staff.json` (Chief-of-Staff subset)
  - `jobs_chief_of_staff.csv` (Chief-of-Staff subset)
  - `docs/index.html` (GitHub Pages UI with a default **Chief of Staff only** filter toggle)
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
       - `max_job_age_days` (default `7`; keeps only roles posted/updated within the last N days)
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
   MIN_REQUEST_INTERVAL_SECONDS=0.25 SCRAPE_CONCURRENCY=8 python src/main.py
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
  - Set `"scrape_concurrency": 8` (or lower) in `config.json`, or run with `SCRAPE_CONCURRENCY=8`.
- Add per-request pacing for big source lists:
  - Set `MIN_REQUEST_INTERVAL_SECONDS=0.2` to add a small cross-thread gap between requests per host.
- Keep chunk jobs from overloading providers:
  - The daily workflow limits chunk fan-out (`max-parallel: 2`) and defaults to `SCRAPE_CONCURRENCY=8`.
- Retries are built in for temporary provider limits/errors:
  - Scraper requests now back off and retry for `429/5xx` responses.

### Large-list tuning playbook (fast + fewer rate limits)

- Start with `SCRAPE_CONCURRENCY=8` and `MIN_REQUEST_INTERVAL_SECONDS=0.2`.
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

- Full feed (`jobs.json` / `jobs.csv`) keeps all fetched roles after dedupe + age filter (`max_job_age_days`, default 7) + optional link validation.
- Published artifacts intentionally omit the raw `description` body to keep file sizes below GitHub push limits (the description is only used during filtering in-memory).
- Chief-of-Staff subset (`jobs_chief_of_staff.*`) requires title to match `chief ... staff` (case-insensitive) and then applies include/exclude checks against title, department, team, location, and description text.
- GitHub Pages shows the full feed but enables **Chief of Staff only** by default via a UI toggle.
- Duplicate jobs from the same platform/company/title are merged into one record, collating differences like locations/teams/departments/URLs.

## Security checklist

- Do **not** commit `config.json` if it contains private values. Keep secrets in GitHub Actions secrets.
- SMTP credentials are read from environment variables (`SMTP_*`) and are not written to artifacts.
- Use HTTPS-only upstream endpoints (Greenhouse/Lever/Ashby APIs) and avoid adding arbitrary untrusted URLs.
