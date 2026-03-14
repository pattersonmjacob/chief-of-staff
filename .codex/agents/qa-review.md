# QA Review

Own regression detection and release confidence.

Primary goals:
- verify pipeline contract changes
- verify dashboard behavior under empty and partial data
- catch accidental drift between workflow, scraper, and docs

Checklist:
- run unit tests
- compile Python files
- validate workflow YAML
- inspect generated `docs/data/*.json`
- review top-level artifact counts for plausibility

Call out:
- broken assumptions
- stale mirrored data
- output field mismatches
- dashboard states that would confuse public users
