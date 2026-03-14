# Pages UI

Own the dashboard implementation in `docs/index.html`.

Primary goals:
- zero runtime errors
- fast initial render
- resilient data loading from `docs/data/*.json`
- accessible controls and readable cards

Focus on:
- fetch error handling
- stale/missing data states
- filter logic correctness
- URL-safe external links
- mobile layout stability
- keeping the page simple enough for GitHub Pages

Guardrails:
- no build step
- no external dependencies
- keep everything static and cache-friendly
