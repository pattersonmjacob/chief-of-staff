# chief-of-staff

Version 1 of a free, keyword-based jobs pipeline.

## What it does

- Pulls jobs from **Greenhouse**, **Lever**, and **Ashby** job boards.
- Filters jobs with keyword include/exclude matching (no AI/ranking yet).
- Writes output files:
  - `jobs.json`
  - `jobs.csv`
  - `docs/index.html` (for GitHub Pages)
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
       - `max_sources` (for example `1000`)

   - **Manual source list:**
     - Keep `sources_csv` empty or remove it.
     - Add known company slugs under `sources`.

3. Configure keyword filters:
   - `keywords_include`: terms to keep.
   - `keywords_exclude`: terms to drop after include matching.
   - `fallback_to_unfiltered_if_empty` (default `true`): if filters return zero but scraping found jobs, publish unfiltered results for that run.

4. Run locally:

   ```bash
   python src/main.py
   ```

## Source CSV format

The CSV should include (at minimum):
- `slug` (or `company_slug`)
- `vendor` (or `platform`/`source`) with values containing `Ashby`, `Greenhouse`, or `Lever`
- `open_jobs` (or `job_count`)

Only supported vendors are loaded. Duplicate `(vendor, slug)` pairs are deduplicated.

## GitHub Actions

Workflow is in `.github/workflows/daily.yml` and runs:
- Daily via cron
- On manual trigger (`workflow_dispatch`)

It can optionally download a source list first when repo variable `SOURCES_CSV_URL` is set.

### Required repo settings

1. **Actions write permissions**
   - Settings → Actions → General → Workflow permissions → **Read and write permissions**.

2. **Branch rules**
   - If branch protection is on, ensure workflow commits are allowed or switch to PR-based updates.

3. **Pages**
   - Settings → Pages → Source: **Deploy from branch**
   - Branch: `main`
   - Folder: `/docs`

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

- If workflow fails to push updated artifacts:
  - Recheck Actions write permissions and branch protection settings.
