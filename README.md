# chief-of-staff

Version 1 of a free, keyword-based jobs pipeline.

## What it does

- Pulls jobs from **Greenhouse**, **Lever**, and **Ashby** job boards.
- Filters jobs with simple keyword matching (no AI/ranking yet).
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

2. Edit `config.json`:
   - Add your desired keyword list.
   - Add known company slugs under `sources`.

3. Run locally:

   ```bash
   python src/main.py
   ```

## GitHub Actions

Workflow is in `.github/workflows/daily.yml` and runs:
- Daily via cron
- On manual trigger (`workflow_dispatch`)

It commits generated `jobs.json`, `jobs.csv`, and `docs/index.html` back to the default branch.

## GitHub Pages

Set GitHub Pages source to:
- Branch: `main`
- Folder: `/docs`

Then your digest page is served from `docs/index.html`.

## Optional SMTP email

If `"email": {"enabled": true}` in `config.json`, set these repository secrets:

- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_HOST`
- `SMTP_PORT` (optional, defaults to `587`)
- `SMTP_USER`
- `SMTP_PASS`

If secrets are missing, the script logs a warning and skips sending.

## Notes

- ATS slugs are manually maintained in v1.
- Deduplication is per-run only.
- Filtering is keyword-only.
