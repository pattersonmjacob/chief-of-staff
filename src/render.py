from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def render_html(jobs: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for job in jobs:
        rows.append(
            "<tr>"
            f"<td>{escape(job.get('title', ''))}</td>"
            f"<td>{escape(job.get('company', ''))}</td>"
            f"<td>{escape(job.get('platform', ''))}</td>"
            f"<td>{escape(job.get('location', ''))}</td>"
            f"<td><a href=\"{escape(job.get('url', ''))}\" target=\"_blank\" rel=\"noopener noreferrer\">Apply</a></td>"
            "</tr>"
        )

    table_rows = "\n".join(rows) if rows else "<tr><td colspan='5'>No matching jobs found.</td></tr>"
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Chief of Staff Jobs</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; text-align: left; padding: 0.6rem; }}
    th {{ background: #f8f8f8; }}
    .meta {{ color: #666; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <h1>Chief of Staff Jobs</h1>
  <p class=\"meta\">{len(jobs)} jobs · Generated {generated_at}</p>
  <table>
    <thead>
      <tr><th>Title</th><th>Company</th><th>Platform</th><th>Location</th><th>Link</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</body>
</html>
"""
