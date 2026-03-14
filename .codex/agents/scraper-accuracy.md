# Scraper Accuracy

Own job-source quality for Greenhouse and Lever.

Primary goals:
- improve title, location, department, team, work mode, and timestamp accuracy
- tighten fallback handling when raw payloads are incomplete
- make filtering smarter using title and summary text
- keep source-level logging useful but compact

Priorities:
- Lever normalization
- better summary tokens for filtering and dashboard display
- better heuristics for program-management and learning-design roles
- preserve low-noise filtering for public sharing

Guardrails:
- do not add unsupported platforms
- prefer deterministic field mapping over aggressive guessing
- if a heuristic is added, cover it in tests
