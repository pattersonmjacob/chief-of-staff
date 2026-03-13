from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
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
    company = role.get("company")
    platform = role.get("platform")
    location = role.get("location")
    url = role.get("url") or ""
    recency = _recency_label(role)
    summary = _summary_token(role)

    role_title = f"[{title}]({url})" if url else title
    suffix_parts = [part for part in (company, platform, location) if part]
    suffix = f" — {' · '.join(suffix_parts)}" if suffix_parts else ""

    meta_parts = [part for part in (recency, summary) if part]
    meta = f" — {' · '.join(meta_parts)}" if meta_parts else ""
    return f"- {role_title}{suffix}{meta}"


def _truncate(value: str, limit: int = 24) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _summary_token(role: dict) -> str:
    token_candidates = [
        ("team", role.get("team")),
        ("dept", role.get("department")),
        ("mode", role.get("work_mode") or role.get("employment_type")),
        (
            "comp",
            role.get("comp")
            or role.get("compensation")
            or role.get("salary_range")
            or role.get("salary"),
        ),
    ]
    tokens = [f"{label}:{_truncate(str(value))}" for label, value in token_candidates if value]
    if not tokens:
        return ""
    return "summary " + " | ".join(tokens)


def _recency_label(role: dict) -> str:
    first_seen = _parse_iso8601(role.get("first_seen_at"))
    now = datetime.now(timezone.utc)

    if role.get("is_new"):
        return "new since last run"
    if first_seen > datetime.min.replace(tzinfo=timezone.utc) and now - first_seen <= timedelta(hours=24):
        return "opened in last 24h"
    if first_seen > datetime.min.replace(tzinfo=timezone.utc):
        return f"opened {first_seen.strftime('%Y-%m-%d')}"
    return "opened date unknown"


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
