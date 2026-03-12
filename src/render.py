from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def _badge(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{escape(text)}</span>'


def render_html(jobs: list[dict], github_pages_url: str = "") -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    chief_count = sum(1 for job in jobs if job.get("is_chief_of_staff"))

    rows = []
    for job in jobs:
        flags = [
            _badge("Technical" if job.get("is_technical") else "Non-technical", "tech" if job.get("is_technical") else "non-tech"),
            _badge(str(job.get("job_function", "other")), "function"),
        ]
        if job.get("is_chief_of_staff"):
            flags.append(_badge("Chief of Staff", "chief"))
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
            f"data-chief=\"{'yes' if job.get('is_chief_of_staff') else 'no'}\" "
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

    table_rows = "\n".join(rows) if rows else "<tr><td colspan='8'>No jobs found.</td></tr>"

    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>ATS Jobs Tracker</title>
  <style>
    :root { --bg:#070b1a; --card:#0f172aee; --line:#334155; --text:#e2e8f0; --muted:#94a3b8; --accent:#22d3ee; --accent2:#a78bfa; }
    * { box-sizing: border-box; }
    body { font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: var(--text); background: radial-gradient(1000px 500px at 10% -10%, #155e75 0%, transparent 50%), radial-gradient(800px 400px at 100% 0%, #4c1d95 0%, transparent 45%), var(--bg); }
    .container { max-width: 1260px; margin: 0 auto; padding: 1.2rem 1rem 2rem; }
    .header { display:flex; justify-content:space-between; align-items:end; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; background:linear-gradient(130deg,#0f172a,#111827); border:1px solid #33415599; border-radius:18px; padding:1rem 1.1rem; box-shadow: 0 20px 60px #02061780; }
    h1 { margin: 0; font-size: clamp(1.6rem, 2.8vw, 2.4rem); letter-spacing: .2px; }
    .meta { color: var(--muted); margin:.35rem 0 0; }
    .pages-link { text-decoration:none; color:#04111d; background:linear-gradient(135deg,var(--accent),#67e8f9); padding:.58rem .85rem; border-radius:12px; font-weight:700; box-shadow:0 8px 24px #22d3ee3d; }
    .toolbar { display:grid; grid-template-columns: 1.6fr repeat(4, 1fr); gap:.55rem; margin:.9rem 0 1rem; background: var(--card); border:1px solid #334155aa; border-radius:16px; padding:.7rem; backdrop-filter: blur(6px); }
    .toolbar input,.toolbar select { padding:.62rem; border:1px solid #334155; border-radius:12px; background:#020617a8; color:var(--text); }
    .toolbar .toggle { display:flex; align-items:center; gap:.4rem; padding:.62rem; border:1px solid #334155; border-radius:12px; background:#020617a8; }
    .summary { margin:.2rem 0 .75rem; color:var(--muted); }
    .table-wrap { background:var(--card); border:1px solid #334155aa; border-radius:18px; overflow:auto; box-shadow:0 18px 50px #02061766; }
    table { border-collapse:collapse; width:100%; min-width:1080px; }
    th,td { border-bottom:1px solid #33415566; text-align:left; padding:.7rem; vertical-align:top; }
    th { background:#0b1226; color:#cbd5e1; position:sticky; top:0; z-index:1; }
    tbody tr:hover { background:#1e293b66; }
    .badge { display:inline-block; padding:.14rem .5rem; border-radius:999px; font-size:.74rem; margin:0 .25rem .25rem 0; border:1px solid transparent; }
    .tech { background:#083344; color:#67e8f9; border-color:#155e75; }
    .non-tech { background:#1e293b; color:#cbd5e1; border-color:#334155; }
    .function { background:#2e1065; color:#c4b5fd; border-color:#5b21b6; }
    .chief { background:#082f49; color:#bae6fd; border-color:#0c4a6e; }
    .new { background:#3f1d2e; color:#f9a8d4; border-color:#9d174d; }
    a { color:#67e8f9; }
    @media (max-width: 980px) { .toolbar { grid-template-columns: 1fr 1fr; } }
  </style>
</head>
<body>
  <main class=\"container\">
    <header class=\"header\">
      <div>
        <h1>ATS Jobs Tracker</h1>
        <p class=\"meta\">__TOTAL__ total jobs · __CHIEF_TOTAL__ Chief of Staff matches · Generated __GENERATED__</p>
      </div>
      __PAGES_LINK__
    </header>

    <div class=\"toolbar\">
      <input id=\"search\" type=\"search\" placeholder=\"Search title/company/location\" />
      <select id=\"platform\"><option value=\"\">All platforms</option><option>greenhouse</option><option>lever</option><option>ashby</option></select>
      <select id=\"technical\"><option value=\"\">All technicality</option><option value=\"yes\">Technical</option><option value=\"no\">Non-technical</option></select>
      <select id=\"function\"><option value=\"\">All functions</option><option>business-operations</option><option>program-management</option><option>product</option><option>engineering</option><option>finance</option><option>people-hr</option><option>other</option></select>
      <select id=\"freshness\"><option value=\"\">All time</option><option value=\"new\">New since last run</option><option value=\"12h\">First seen ≤12h</option><option value=\"24h\">First seen ≤24h</option></select>
      <label class=\"toggle\"><input id=\"chiefOnly\" type=\"checkbox\" checked /> Chief of Staff only</label>
    </div>
    <p class=\"summary\" id=\"summary\">Showing __CHIEF_TOTAL__ of __TOTAL__ jobs.</p>

    <section class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>Title</th><th>Company</th><th>Platform</th><th>Location</th><th>Posted</th><th>First seen</th><th>Flags</th><th>Link</th></tr>
        </thead>
        <tbody id=\"jobs-body\">__ROWS__</tbody>
      </table>
    </section>
  </main>

  <script>
    const q = (id) => document.getElementById(id);
    const rows = Array.from(document.querySelectorAll('#jobs-body tr'));
    const controls = ['search','platform','technical','function','freshness','chiefOnly'].map(q);

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
      const chiefOnly = q('chiefOnly').checked;
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
        if (chiefOnly && row.dataset.chief !== 'yes') visible = false;

        row.style.display = visible ? '' : 'none';
        if (visible) shown += 1;
      });

      q('summary').innerText = `Showing ${shown} of ${rows.length} jobs.`;
    }

    controls.forEach((el) => el.addEventListener('input', applyFilters));
    controls.forEach((el) => el.addEventListener('change', applyFilters));
    applyFilters();
  </script>
</body>
</html>
"""

    return (
        html.replace("__TOTAL__", str(len(jobs)))
        .replace("__CHIEF_TOTAL__", str(chief_count))
        .replace("__GENERATED__", generated_at)
        .replace("__ROWS__", table_rows)
        .replace("__PAGES_LINK__", pages_link)
    )
