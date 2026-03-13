from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
ROLES_PATH = ROOT / "jobs_chief_of_staff.json"
START_MARKER = "<!-- START_COS_ROLES -->"
END_MARKER = "<!-- END_COS_ROLES -->"
MAX_ROLES = 50


def _parse_iso8601(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _sort_key(role: dict) -> tuple[datetime, datetime, str]:
    first_seen = _parse_iso8601(role.get("first_seen_at"))
    posted = _parse_iso8601(role.get("posted_at"))
    tie_breaker = "|".join(
        [
            str(role.get("title", "")),
            str(role.get("company", "")),
            str(role.get("platform", "")),
            str(role.get("location", "")),
            str(role.get("url", "")),
        ]
    ).lower()
    return (first_seen, posted, tie_breaker)


def _format_role_line(role: dict) -> str:
    title = role.get("title") or "Untitled role"
    company = role.get("company") or "Unknown company"
    platform = role.get("platform") or "Unknown platform"
    location = role.get("location") or "Unknown location"
    posted = role.get("posted_at") or "Unknown"
    url = role.get("url") or ""

    return f"- {title} — {company} ({platform}) — {location} — {posted} — [Link]({url})"


def _deterministic_timestamp(roles: list[dict]) -> str:
    latest = datetime.min.replace(tzinfo=timezone.utc)
    for role in roles:
        latest = max(latest, _parse_iso8601(role.get("first_seen_at")), _parse_iso8601(role.get("posted_at")))

    if latest == datetime.min.replace(tzinfo=timezone.utc):
        return "Unknown"

    return latest.strftime("%Y-%m-%d %H:%M UTC")


def build_roles_block(roles: list[dict]) -> str:
    header = f"_Chief-of-Staff matches: {len(roles)} · Snapshot timestamp: {_deterministic_timestamp(roles)}_"

    ordered = sorted(roles, key=_sort_key, reverse=True)
    lines = [header]
    lines.extend(_format_role_line(role) for role in ordered[:MAX_ROLES])
    return "\n".join(lines)


def update_readme() -> None:
    roles = json.loads(ROLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(roles, list):
        raise ValueError(f"Expected a list in {ROLES_PATH}")

    readme_text = README_PATH.read_text(encoding="utf-8")
    start = readme_text.find(START_MARKER)
    end = readme_text.find(END_MARKER)

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "README markers not found. Add START/END markers before running this script."
        )

    start_content = start + len(START_MARKER)
    replacement = "\n" + build_roles_block(roles) + "\n"
    updated = readme_text[:start_content] + replacement + readme_text[end:]
    README_PATH.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    update_readme()
