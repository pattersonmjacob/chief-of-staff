from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def _badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{escape(text)}</span>'


def render_html(jobs: list[dict], github_pages_url: str = "") -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for job in jobs:
        flags = [
            _badge("Technical" if job.get("is_technical") else "Non-technical", "tech" if job.get("is_technical") else "non-tech"),
            _badge(str(job.get("job_function", "other")), "function"),
        ]
        if job.get("is_new"):
            flags.append(_badge("NEW", "new"))

        posted = escape(str(job.get("posted_at", "") or "")) or "—"
        first_seen = escape(str(job.get("first_seen_at", "") or "")) or "—"

        rows.append(
            "<tr "
            f"data-title=\"{escape(str(job.get('title', '')).lower())}\" "
            f"data-company=\"{escape(str(job.get('company', '')).lower())}\" "
            f"data-platform=\"{escape(str(job.get('platform', '')).lower())}\" "
            f"data-technical=\"{'yes' if job.get('is_technical') else 'no'}\" "
            f"data-function=\"{escape(str(job.get('job_function', 'other')).lower())}\" "
            f"data-new=\"{'yes' if job.get('is_new') else 'no'}\" "
            f"data-first-seen=\"{escape(str(job.get('first_seen_at', '')))}\""
            ">"
            f"<td>{escape(job.get('title', ''))}</td>"
            f"<td>{escape(job.get('company', ''))}</td>"
            f"<td>{escape(job.get('platform', ''))}</td>"
            f"<td>{escape(job.get('location', ''))}</td>"
            f"<td>{posted}</td>"
            f"<td>{first_seen}</td>"
            f"<td>{''.join(flags)}</td>"
            f"<td><a href=\"{escape(job.get('url', ''))}\" target=\"_blank\" rel=\"noopener noreferrer\">Apply</a></td>"
            "</tr>"
        )

    pages_link = ""
    if github_pages_url:
        safe_link = escape(github_pages_url)
        pages_link = f"<a class=\"pages-link\" href=\"{safe_link}\" target=\"_blank\" rel=\"noopener noreferrer\">Open GitHub Pages ↗</a>"

    table_rows = "\n".join(rows) if rows else "<tr><td colspan='8'>No matching jobs found.</td></tr>"

    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Chief of Staff Jobs</title>
  <style>
    body { font-family: Inter, system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #111827; }
    .container { max-width: 1240px; margin: 0 auto; padding: 1.25rem 1rem 2.5rem; }
    .header { display: flex; gap: 1rem; justify-content: space-between; align-items: end; flex-wrap: wrap; margin-bottom: 1rem; }
    h1 { margin: 0; font-size: clamp(1.4rem, 2.4vw, 2.1rem); }
    .meta { color: #4b5563; margin: .4rem 0 0; }
    .pages-link { text-decoration: none; font-weight: 600; background: #111827; color: white; padding: 0.5rem 0.75rem; border-radius: 0.5rem; }
    .toolbar { display:grid; grid-template-columns: 2fr repeat(4, 1fr); gap:.5rem; margin: .8rem 0 1rem; }
    .toolbar input,.toolbar select { padding:.55rem; border:1px solid #d1d5db; border-radius:.45rem; background:white; }
    .table-wrap { background:white; border:1px solid #e5e7eb; border-radius:.75rem; overflow:auto; }
    table { border-collapse: collapse; width: 100%; min-width: 1050px; }
    th,td { border-bottom:1px solid #e5e7eb; text-align:left; padding:.6rem; vertical-align: top; }
    th { background:#f9fafb; position: sticky; top:0; z-index:1; }
    .badge { display:inline-block; padding:.1rem .45rem; border-radius:999px; font-size:.74rem; margin:0 .25rem .25rem 0; }
    .tech { background:#dbeafe; color:#1e40af; } .non-tech { background:#e5e7eb; color:#374151; }
    .function { background:#dcfce7; color:#166534; } .new { background:#fee2e2; color:#991b1b; }
    .summary { margin:.3rem 0 .8rem; color:#374151; }
  </style>
</head>
<body>
  <main class=\"container\">
    <header class=\"header\">
      <div>
        <h1>Chief of Staff Jobs</h1>
        <p class=\"meta\">__TOTAL__ jobs · Generated __GENERATED__</p>
      </div>
      __PAGES_LINK__
    </header>

    <div class=\"toolbar\">
      <input id=\"search\" type=\"search\" placeholder=\"Search title/company/location\" />
      <select id=\"platform\"><option value=\"\">All platforms</option><option>greenhouse</option><option>lever</option><option>ashby</option></select>
      <select id=\"technical\"><option value=\"\">All technicality</option><option value=\"yes\">Technical</option><option value=\"no\">Non-technical</option></select>
      <select id=\"function\"><option value=\"\">All functions</option><option>business-operations</option><option>program-management</option><option>engineering</option><option>product</option><option>finance</option><option>people-hr</option><option>other</option></select>
      <select id=\"freshness\"><option value=\"\">All time</option><option value=\"new\">New since last run</option><option value=\"12h\">First seen ≤12h</option><option value=\"24h\">First seen ≤24h</option></select>
    </div>
    <p class=\"summary\" id=\"summary\">Showing __TOTAL__ of __TOTAL__ jobs.</p>

    <section class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>Title</th><th>Company</th><th>Platform</th><th>Location</th><th>Posted</th><th>First Seen</th><th>Flags</th><th>Link</th></tr>
        </thead>
        <tbody id=\"jobs-body\">__ROWS__</tbody>
      </table>
    </section>
  </main>

  <script>
    const q = (id) => document.getElementById(id);
    const rows = Array.from(document.querySelectorAll('#jobs-body tr'));
    const controls = ['search','platform','technical','function','freshness'].map(q);

    const inHours = (iso, hours) => {
      const t = Date.parse(iso || '');
      if (!t) return false;
      return (Date.now() - t) <= (hours * 3600 * 1000);
    };

    function applyFilters() {
      const search = q('search').value.trim().toLowerCase();
      const platform = q('platform').value.toLowerCase();
      const technical = q('technical').value;
      const func = q('function').value.toLowerCase();
      const freshness = q('freshness').value;
      let shown = 0;

      rows.forEach((row) => {
        const locationText = (row.children[3]?.innerText || '').toLowerCase();
        const text = [row.dataset.title || '', row.dataset.company || '', locationText].join(' ');
        let visible = true;
        if (search && !text.includes(search)) visible = false;
        if (platform && row.dataset.platform !== platform) visible = false;
        if (technical && row.dataset.technical !== technical) visible = false;
        if (func && row.dataset.function !== func) visible = false;
        if (freshness === 'new' && row.dataset.new !== 'yes') visible = false;
        if (freshness === '12h' && !inHours(row.dataset.firstSeen, 12)) visible = false;
        if (freshness === '24h' && !inHours(row.dataset.firstSeen, 24)) visible = false;

        row.style.display = visible ? '' : 'none';
        if (visible) shown += 1;
      });

      q('summary').innerText = `Showing ${shown} of ${rows.length} jobs.`;
    }

    controls.forEach((el) => el.addEventListener('input', applyFilters));
    controls.forEach((el) => el.addEventListener('change', applyFilters));
  </script>
</body>
</html>
"""

    return (
        html.replace("__TOTAL__", str(len(jobs)))
        .replace("__GENERATED__", generated_at)
        .replace("__PAGES_LINK__", pages_link)
        .replace("__ROWS__", table_rows)
    )
