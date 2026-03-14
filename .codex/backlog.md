# Multi-Agent Backlog

## Pages

- Make the dashboard feel more like a real job board and less like an artifact browser.
- Add clearer sort controls: newest, company, title.
- Add quick filters for `Chief of Staff`, `Adjacent`, `Learning`, `New`.
- Improve card density on desktop without hurting mobile readability.
- Add a friendly stale-data warning when mirrored docs data lags behind root artifacts.

## Scraper

- Verify Lever timestamps and fallback title extraction on more real boards.
- Improve summary generation so filtering has better text to match on.
- Review false positives from generic `operations` matches.
- Consider lightweight company-name normalization for display.

## Board Scout

- Investigate new ATS vendors worth supporting.
- Collect candidate custom public boards that expose stable job payloads.
- Capture field-shape notes and whether each board exposes title, team, location, mode, timestamps, and compensation.
- Rank discoveries by integration value and implementation complexity.

## Workflow

- Reduce duplicated JSON committed under both root and `docs/data` if a cleaner publish path is possible.
- Consider compressing or trimming fields for dashboard-only payloads.
- Add a lightweight size budget check for `docs/data/jobs.json`.
- Make aggregate summaries easier to compare across runs.

## Workflow Ops

- Inspect failed or flaky runs and leave diagnosis handoffs.
- Track slow steps and candidates for reruns or optimizations.
- Watch for stale root-vs-docs artifact mismatches.
- Review schedule vs manual-dispatch behavior when outputs differ.

## QA

- Add tests for dashboard-facing summary fields.
- Add tests for broader learning-role coverage.
- Add a script to compare root artifacts against mirrored docs data.
