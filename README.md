# chief-of-staff

Version 1 of a free, keyword-based jobs pipeline.

## What it does

## Latest Chief of Staff roles

<!-- START_COS_ROLES -->
_Chief-of-Staff matches: 18 · Snapshot timestamp: 2026-03-14 13:29 UTC_
- [Chief of Staff](https://job-boards.greenhouse.io/blankstreet/jobs/7621264003) — blankstreet · greenhouse · New York City — new since last run · summary team:New York | dept:Business Operations & S… | mode:hybrid_or_onsite
- [Chief of Staff](https://job-boards.greenhouse.io/arine/jobs/5737836004) — arine · greenhouse · San Francisco, CA (Hybrid) — new since last run · summary team:Arine HQ | dept:Office of the CEO | mode:hybrid
- [Chief of Staff, Product & Operations](https://job-boards.greenhouse.io/mavenclinic/jobs/8451225002) — mavenclinic · greenhouse · New York, New York, United States — new since last run · summary team:New York | dept:Product Management | mode:hybrid
- [Chief of Staff - Samlino Group](https://job-boards.greenhouse.io/ceg/jobs/7649099003) — ceg · greenhouse · Copenhagen, Denmark; Lisbon, Portugal | Lisbon, Portugal — new since last run · summary team:Samlino Group | dept:Management | Operations | mode:onsite
- [Chief of Staff](https://job-boards.greenhouse.io/mobentertainment/jobs/5066064007) — mobentertainment · greenhouse · Remote — new since last run · summary dept:Business | mode:remote
- [Chief of Staff](https://jobs.lever.co/arraylabs.io/035e4848-e32a-4b54-a3f6-e87bca54c180) — arraylabs.io · lever · Palo Alto, CA — opened in last 24h · summary team:Management | mode:onsite
- [Chief of Staff, Sales](https://stripe.com/jobs/search?gh_jid=7600099) — stripe · greenhouse · SF — opened 2026-03-12 · summary team:US | dept:1170 GEO Sales HQ (NA) | mode:hybrid_or_onsite
- [Chief of Staff](https://job-boards.greenhouse.io/interfaceai/jobs/4608965006) — interfaceai · greenhouse · Palo-Alto (In-office) — opened 2026-03-12 · summary team:interface USA | dept:Office of the CEO | mode:hybrid_or_onsite
- [Chief of Staff](https://job-boards.greenhouse.io/mochihealth/jobs/5119052008) — mochihealth · greenhouse · San Francisco, CA — opened 2026-03-12 · summary team:Mochi HQ | dept:People | mode:onsite
- [Chief of Staff to CFO/COO](https://job-boards.greenhouse.io/babylist/jobs/5690329004) — babylist · greenhouse · Emeryville, CA — opened 2026-03-12 · summary team:Remote | dept:General & Administrative | mode:remote
- [Chief of Staff, Tactical Recon & Strike](https://boards.greenhouse.io/andurilindustries/jobs/5068434007?gh_jid=5068434007) — andurilindustries · greenhouse · Costa Mesa, California, United States — opened 2026-03-12 · summary team:Costa Mesa, CA (HQ) | dept:Tactical Recon & Strike | mode:hybrid_or_onsite
- [Chief of Staff, Design](https://boards.greenhouse.io/andurilindustries/jobs/4740150007?gh_jid=4740150007) — andurilindustries · greenhouse · Costa Mesa, California, United States — opened 2026-03-12 · summary team:Costa Mesa, CA (HQ) | dept:Sales and Marketing : D… | mode:onsite
- [Chief of Staff, Air Dominance & Strike](https://boards.greenhouse.io/andurilindustries/jobs/4841348007?gh_jid=4841348007) — andurilindustries · greenhouse · Costa Mesa, California, United States — opened 2026-03-12 · summary team:Costa Mesa, CA (HQ) | dept:Air Dominance & Strike… | mode:hybrid_or_onsite
- [Executive Leadership Programme - Chief of Staff (Europe)](https://job-boards.greenhouse.io/banyansoftware/jobs/5012912007) — banyansoftware · greenhouse · Denmark; Netherlands; Sweden — opened 2026-03-12 · summary team:Amsterdam, Netherlands | dept:Executive Team | mode:hybrid_or_onsite
- [Executive Leadership Program - Chief of Staff](https://job-boards.greenhouse.io/banyansoftware/jobs/4980694007) — banyansoftware · greenhouse · United States — opened 2026-03-12 · summary team:Remote - USA | dept:Operating Partners | mode:hybrid_or_onsite
- [Technical Chief of Staff for ASIC Engineering](https://job-boards.greenhouse.io/asteralabs/jobs/4632063005) — asteralabs · greenhouse · San Jose, CA — opened 2026-03-12 · summary team:San Jose, CA | dept:ASIC Engineering | mode:hybrid_or_onsite
- [Chief of Staff - R&D](https://job-boards.greenhouse.io/addepar1/jobs/8120254002) — addepar1 · greenhouse · New York, NY — opened 2026-03-12 · summary team:New York, NY | dept:Engineering Executive S… | mode:remote
- [Chief of Staff to CEO of BridgeBio and GondolaBio](https://job-boards.greenhouse.io/bridgebio/jobs/5067375007) — bridgebio · greenhouse · Palo Alto - 3160 Porter — opened 2026-03-12 · summary team:Palo Alto - 3160 Porter | dept:Management | mode:hybrid
<!-- END_COS_ROLES -->

- Pulls jobs from **Greenhouse** and **Lever** job boards.
- Computes a strict Chief-of-Staff subset using title regex + include/exclude keyword matching.
- Computes a broader adjacent strategy/operations subset using include/exclude keyword matching.
- Flags learning-and-development roles inside the focused published feed.
- Writes output files:
  - `jobs.json` (focused published feed: Chief of Staff + adjacent matches)
  - `jobs.csv` (focused published feed: Chief of Staff + adjacent matches)
  - `jobs_chief_of_staff.json` (strict Chief-of-Staff subset)
  - `jobs_chief_of_staff.csv` (strict Chief-of-Staff subset)
  - `jobs_strategy_ops.json` (adjacent strategy/operations subset)
  - `jobs_strategy_ops.csv` (adjacent strategy/operations subset)
  - `data/run_meta.json` (latest published run totals and timestamp)
  - `data/aggregate_summary.json` (chunk aggregation diagnostics from GitHub Actions)
  - `docs/data/*.json` (mirrored dashboard data used by GitHub Pages)
  - Tracks `first_seen_at` / `last_seen_at` and marks `is_new` for jobs newly seen since the prior run.
- Automatically tracks repeated HTTP 404 sources in `data/do_not_check.json` and skips them on future runs (after 3+ 404s and a healthy non-404 streak guard).
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
       - `max_sources_per_platform` (optional; leave empty, `null`, or `0` for no per-platform cap)
       - `scrape_concurrency` (default `1`; set to `1` for no in-process concurrency)
       - `validate_job_links` (default `true`; verifies job URLs before publishing and removes unavailable postings)
       - `link_check_delay_seconds` (default `0.8`; delay between URL checks to avoid rate limits)
       - `max_job_age_days` (default `13`; keeps only roles posted/updated within the last N days)
       - `keep_missing_dates` (default `true`; preserves jobs with missing/invalid dates during age filtering)
      - `strict_chief_title_required` (default `true`; requires `chief ... staff` in title for `jobs_chief_of_staff.*`)
      - `include_adjacent_roles` (default `true`; enables the broader `jobs_strategy_ops.*` subset)
      - `verbose_sources` (default `false`; when true logs every source result)

   - **Manual source list:**
     - Keep `sources_csv` empty or remove it.
     - Add known company slugs under `sources`.

3. Configure keyword filters:
   - `keywords_include`: terms to keep. The default fallback config already includes Chief of Staff, strategy/business ops, program-management, and learning-design/L&D phrases.
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
- `vendor` (`Greenhouse`, `Lever`)
- `open_jobs` (or `job_count`)

Optional but recommended:
- `url` (the hosted jobs page or board URL for fallback parsing)

Only supported vendors are loaded. Duplicate `(vendor, slug)` pairs are deduplicated.

## GitHub Actions

There are two workflows:

1. **Daily jobs digest** (`.github/workflows/daily.yml`)
   - Runs daily via cron (`15 12 * * *`) and on manual trigger.
   - Resolves runtime settings once, then fans them out to split Greenhouse / Lever chunk jobs.
   - Chunk jobs use `src/fetch_chunk.py` to publish raw platform-specific `jobs_*.json` artifacts only; the final aggregate job rebuilds all public outputs from those raw chunks.
   - Weekly Sunday run (`30 12 * * 0`) enables link validation in the aggregate job; the normal daily run skips link validation for speed.
   - Uses `SOURCES_CSV=data/company_slugs.csv` so daily scraping reads the repo-pinned source list.

2. **Refresh company source list** (`.github/workflows/refresh-sources-weekly.yml`)
   - Runs weekly on Mondays (`0 9 * * 1`) and on manual trigger.
   - Pulls and merges these upstream lists into `data/company_slugs.csv` and commits the updated file:
     - `https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/lever/lever_companies.csv`
     - `https://raw.githubusercontent.com/stapply-ai/ats-scrapers/main/greenhouse/greenhouse_companies.csv`

This gives you a stable, versioned source list in-repo that is refreshed weekly and consumed daily.

## Multi-agent setup

This repo now includes a lightweight multi-agent operating model for Codex:
- [AGENTS.md](/Users/jacobpatterson/VSCode/chief-of-staff/AGENTS.md) defines the shared workflow and agent boundaries.
- [.codex/config.toml](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/config.toml) now uses the docs-aligned native Codex multi-agent format with `[agents.<name>]` entries and `config_file` pointers.
- Human role briefs live in [.codex/agents/orchestrator.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/orchestrator.md), [.codex/agents/workflow-optimizer.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/workflow-optimizer.md), [.codex/agents/workflow-ops.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/workflow-ops.md), [.codex/agents/scraper-accuracy.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/scraper-accuracy.md), [.codex/agents/board-scout.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/board-scout.md), [.codex/agents/pages-designer.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/pages-designer.md), [.codex/agents/pages-ui.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/pages-ui.md), and [.codex/agents/qa-review.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/agents/qa-review.md).
- Native per-role Codex config files live alongside them as `.toml` files in `.codex/agents/`.
- [scripts/setup_multi_agent_worktrees.sh](/Users/jacobpatterson/VSCode/chief-of-staff/scripts/setup_multi_agent_worktrees.sh) creates isolated sibling worktrees for parallel agents.
- [.codex/backlog.md](/Users/jacobpatterson/VSCode/chief-of-staff/.codex/backlog.md) is the shared cleanup list.

Recommended flow:
1. Run `bash scripts/setup_multi_agent_worktrees.sh`
2. Start one Codex session per worktree
3. Assign one role brief per session
4. Merge scraper/workflow changes before Pages polish when possible

Shortcut launchers:
- `bash scripts/launch_codex_agents.sh single`
  - starts one orchestrator Codex session in the current repo with native `multi_agent` enabled and a stronger Pages/workflow/discovery mission
- `bash scripts/launch_codex_agents.sh multi`
  - creates worktrees and opens one Terminal-backed Codex session per role
- `bash scripts/launch_codex_agents.sh pages`
  - launches orchestrator + pages-designer + pages-ui + qa-review
- `bash scripts/launch_codex_agents.sh ops`
  - launches orchestrator + workflow-ops + qa-review
- `bash scripts/launch_codex_agents.sh discovery`
  - launches orchestrator + board-scout + scraper-accuracy

### Required repo settings

1. **Actions write permissions**
   - Settings → Actions → General → Workflow permissions → **Read and write permissions**.

2. **Branch rules**
   - If branch protection is on, ensure workflow commits are allowed or switch to PR-based updates.

## Avoiding rate limits

- Lower parallelism in your runtime config if you see HTTP 429s:
  - Set `"scrape_concurrency": 1` in `config.json`, or run with `SCRAPE_CONCURRENCY=1` for fully sequential requests.
- Add per-request pacing for big source lists:
  - Set `MIN_REQUEST_INTERVAL_SECONDS=0.35` to add a small cross-thread gap between requests per host.
- Keep chunk jobs from overloading providers:
  - The daily workflow defaults to uncapped source limits (`MAX_SOURCES` and `MAX_SOURCES_PER_PLATFORM` unset). Use manual dispatch inputs to add temporary caps when needed.
- Retries are built in for temporary provider limits/errors:
  - Scraper requests now back off and retry for `429/5xx` responses.
- Source-identifier fallback is enabled:
  - If a slug fails (for example malformed/stale slug), the scraper retries using the parsed `url` identifier when available.
- Publish-time link checks are enabled:
  - Jobs whose URLs return errors or “no longer active / page not found” pages are removed before writing outputs.

### Large-list tuning playbook (fast + fewer rate limits)

- Start with conservative throttle settings: `SCRAPE_CONCURRENCY=1` and `MIN_REQUEST_INTERVAL_SECONDS=0.35`.
- If you see sustained `429` responses, keep concurrency low and increase interval (`0.5` to `1.0`).
- If runtime is too slow and `429`s are rare, raise concurrency gradually (`2`, `4`, `6`) while keeping an interval in place.
- Keep chunking enabled (`SOURCE_OFFSET` with optional `MAX_SOURCES`) so failures are isolated and retries are cheaper.
- For manual `workflow_dispatch` runs, use `max_sources` / `max_sources_per_platform` inputs as temporary throttles instead of editing workflow code.

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
  - Confirm vendor names map to supported platforms (`Greenhouse`, `Lever`).
  - Check keyword filters are not overly restrictive.

- If the run fails with `JSONDecodeError`:
  - Open `config.json` (or `config.example.json` if using fallback).
  - Fix JSON syntax near the reported line/column (missing comma/trailing quote are common).
  - You can validate locally with: `python -m json.tool config.json`.

- If you hit frequent merge conflicts on generated artifacts (`jobs.json`, `jobs.csv`):
  - Pull latest `main`, rerun `python src/main.py`, then commit only the regenerated outputs.
  - Keep feature/code changes separate from generated-output update commits.
  - This repo marks generated outputs in `.gitattributes` to reduce repeated conflicts during merges.
  - CI aggregation logic is centralized in `src/aggregate_chunks.py` (instead of a long inline workflow script) to reduce workflow-file merge conflicts.

- If workflow fails to push updated artifacts:
  - Recheck Actions write permissions and branch protection settings.
- If the aggregate step fails after scraper chunks succeed:
  - Check `data/aggregate_summary.json` in the workflow workspace/logs for invalid chunk files and per-platform artifact counts.
  - Verify `src/main.py` and `src/aggregate_chunks.py` still share the same post-processing/output contract.


## Filtering behavior

- Published feed (`jobs.json` / `jobs.csv`) keeps only the focused roles that match the Chief-of-Staff/adjacent keyword logic after dedupe + age filter (`max_job_age_days`, default 13) + optional link validation.
- Published artifacts intentionally omit the raw `description` body to keep file sizes below GitHub push limits (the description is only used during filtering in-memory).
- Chief-of-Staff subset (`jobs_chief_of_staff.*`) defaults to requiring title match `chief ... staff` (case-insensitive) plus include/exclude checks against title, department, team, location, and description text (controlled by `strict_chief_title_required`).
- Adjacent-role subset (`jobs_strategy_ops.*`) uses include/exclude checks without requiring the chief-title regex (enabled by `include_adjacent_roles`).
- Learning-and-development roles are flagged in the published feed via `is_learning_and_development`.
- Age filtering keeps undated records by default (`keep_missing_dates=true`), while still excluding dated roles older than `max_job_age_days`.
- Duplicate jobs from the same platform/company/title are merged into one record, collating differences like locations/teams/departments/URLs.

## Security checklist

- Do **not** commit `config.json` if it contains private values. Keep secrets in GitHub Actions secrets.
- SMTP credentials are read from environment variables (`SMTP_*`) and are not written to artifacts.
- Use HTTPS-only upstream endpoints (Greenhouse/Lever APIs) and avoid adding arbitrary untrusted URLs.
