from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".codex" / "config.toml"
LAUNCHER_PATH = ROOT / "scripts" / "launch_codex_agents.sh"
RUNTIME_DIR = ROOT / ".codex" / "runtime"
STATE_DIR = RUNTIME_DIR / "state"
DOCS_DATA_DIR = ROOT / "docs" / "data"
DOCS_STATUS_JSON = DOCS_DATA_DIR / "agents_status.json"
DOCS_GRAPH_MMD = DOCS_DATA_DIR / "agents_graph.mmd"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_agent_key(name: str) -> str:
    return name.replace("_", "-").strip()


def _load_config_agents() -> dict[str, dict[str, Any]]:
    agents: dict[str, dict[str, Any]] = {}
    current_agent = ""
    section_pattern = re.compile(r"^\[agents\.([A-Za-z0-9_]+)\]\s*$")
    field_pattern = re.compile(r'^(description|config_file)\s*=\s*"([^"]*)"')
    for raw_line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        section_match = section_pattern.match(line)
        if section_match:
            current_agent = _normalize_agent_key(section_match.group(1))
            agents[current_agent] = {
                "name": current_agent,
                "description": "",
                "config_file": "",
            }
            continue
        if not current_agent:
            continue
        field_match = field_pattern.match(line)
        if not field_match:
            continue
        field_name, value = field_match.groups()
        agents[current_agent][field_name] = value.strip()
    return agents


def _parse_launch_modes() -> tuple[dict[str, list[str]], dict[str, str]]:
    text = LAUNCHER_PATH.read_text(encoding="utf-8")
    mode_pattern = re.compile(r"^\s*([a-z]+)\)\n\s*cat <<EOF\n(.*?)\nEOF", re.MULTILINE | re.DOTALL)
    role_modes: dict[str, list[str]] = {}
    role_worktrees: dict[str, str] = {}
    for mode, body in mode_pattern.findall(text):
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) != 4:
                continue
            _, worktree, _, role = parts
            role_modes.setdefault(role, []).append(mode)
            role_worktrees.setdefault(role, worktree)
    for role in role_modes:
        role_modes[role] = sorted(set(role_modes[role]))
    return role_modes, role_worktrees


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout.strip()


def _git_status_for_worktree(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "branch": "",
            "dirty_count": 0,
            "ahead": 0,
            "behind": 0,
        }

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    dirty_output = _run_git(["status", "--porcelain"], path)
    dirty_count = len([line for line in dirty_output.splitlines() if line.strip()])

    ahead = 0
    behind = 0
    counts = _run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], path)
    if counts:
        parts = counts.split()
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            ahead = int(parts[0])
            behind = int(parts[1])

    return {
        "exists": True,
        "branch": branch,
        "dirty_count": dirty_count,
        "ahead": ahead,
        "behind": behind,
    }


def _state_path(role: str) -> Path:
    safe = role.replace("/", "-")
    return STATE_DIR / f"{safe}.json"


def _read_state(role: str) -> dict[str, Any]:
    path = _state_path(role)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(role: str, payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(role).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _status_label(active: bool, exists: bool, dirty_count: int) -> str:
    if active:
        return "running"
    if not exists:
        return "missing"
    if dirty_count:
        return "dirty"
    return "idle"


def build_snapshot() -> dict[str, Any]:
    agents = _load_config_agents()
    role_modes, role_worktrees = _parse_launch_modes()

    items: list[dict[str, Any]] = []
    active_count = 0
    dirty_count = 0
    missing_count = 0

    for name in sorted(agents):
        state = _read_state(name)
        relative_worktree = role_worktrees.get(name, "")
        absolute_worktree = (ROOT / relative_worktree).resolve() if relative_worktree else ROOT
        git_status = _git_status_for_worktree(absolute_worktree)
        active = bool(state.get("active"))
        if active:
            active_count += 1
        if git_status["dirty_count"]:
            dirty_count += 1
        if not git_status["exists"]:
            missing_count += 1

        item = {
            "name": name,
            "description": agents[name]["description"],
            "config_file": agents[name]["config_file"],
            "modes": role_modes.get(name, []),
            "worktree": relative_worktree,
            "worktree_exists": git_status["exists"],
            "branch": git_status["branch"],
            "dirty_count": git_status["dirty_count"],
            "ahead": git_status["ahead"],
            "behind": git_status["behind"],
            "active": active,
            "last_started_at": state.get("last_started_at", ""),
            "last_stopped_at": state.get("last_stopped_at", ""),
            "last_mode": state.get("last_mode", ""),
            "status": _status_label(active, git_status["exists"], git_status["dirty_count"]),
        }
        items.append(item)

    snapshot = {
        "generated_at": utc_now_iso(),
        "summary": {
            "total_agents": len(items),
            "active_agents": active_count,
            "dirty_worktrees": dirty_count,
            "missing_worktrees": missing_count,
        },
        "agents": items,
    }
    return snapshot


def build_mermaid(snapshot: dict[str, Any]) -> str:
    lines = ["graph TD", "    orchestrator[orchestrator]"]
    for agent in snapshot["agents"]:
        name = agent["name"]
        if name == "orchestrator":
            continue
        node = name.replace("-", "_")
        label = f"{name}\\n{agent['status']}"
        lines.append(f"    {node}[{label}]")
        lines.append(f"    orchestrator --> {node}")

    mode_groups: dict[str, list[str]] = {}
    for agent in snapshot["agents"]:
        for mode in agent["modes"]:
            mode_groups.setdefault(mode, []).append(agent["name"])

    for mode, members in sorted(mode_groups.items()):
        mode_node = f"mode_{mode}"
        lines.append(f"    {mode_node}(({mode}))")
        for member in sorted(members):
            node = member.replace("-", "_")
            lines.append(f"    {mode_node} --- {node}")

    return "\n".join(lines) + "\n"


def write_snapshot_files(snapshot: dict[str, Any]) -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_STATUS_JSON.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    DOCS_GRAPH_MMD.write_text(build_mermaid(snapshot), encoding="utf-8")


def command_start(args: argparse.Namespace) -> int:
    current = _read_state(args.role)
    current.update(
        {
            "active": True,
            "last_started_at": utc_now_iso(),
            "last_mode": args.mode,
            "worktree": args.worktree,
        }
    )
    _write_state(args.role, current)
    write_snapshot_files(build_snapshot())
    return 0


def command_stop(args: argparse.Namespace) -> int:
    current = _read_state(args.role)
    current.update(
        {
            "active": False,
            "last_stopped_at": utc_now_iso(),
            "last_mode": args.mode or current.get("last_mode", ""),
            "worktree": args.worktree or current.get("worktree", ""),
        }
    )
    _write_state(args.role, current)
    write_snapshot_files(build_snapshot())
    return 0


def command_snapshot(_: argparse.Namespace) -> int:
    write_snapshot_files(build_snapshot())
    print(str(DOCS_STATUS_JSON))
    return 0


def _format_time(value: str) -> str:
    if not value:
        return "-"
    return value.replace("T", " ").replace("Z", " UTC")


def _render_watch(snapshot: dict[str, Any]) -> str:
    width = shutil.get_terminal_size((120, 30)).columns
    summary = snapshot["summary"]
    lines = [
        "Agent Overseer",
        "=" * min(width, 120),
        f"Generated: {_format_time(snapshot['generated_at'])}",
        f"Agents: {summary['total_agents']}  Running: {summary['active_agents']}  Dirty worktrees: {summary['dirty_worktrees']}  Missing: {summary['missing_worktrees']}",
        "",
        f"{'Agent':<20} {'Status':<8} {'Modes':<20} {'Branch':<18} {'Dirty':<5} {'Last activity':<24}",
        "-" * min(width, 120),
    ]
    for agent in snapshot["agents"]:
        last_activity = agent["last_started_at"] or agent["last_stopped_at"]
        lines.append(
            f"{agent['name']:<20} "
            f"{agent['status']:<8} "
            f"{','.join(agent['modes'])[:20]:<20} "
            f"{agent['branch'][:18]:<18} "
            f"{str(agent['dirty_count']):<5} "
            f"{_format_time(last_activity)[:24]:<24}"
        )
    lines.extend(
        [
            "",
            "Legend: running = active Codex session tracked by launcher, dirty = local changes, missing = worktree not created.",
            "Refresh docs data with: python3 scripts/agent_monitor.py snapshot",
        ]
    )
    return "\n".join(lines)


def command_watch(args: argparse.Namespace) -> int:
    try:
        while True:
            snapshot = build_snapshot()
            write_snapshot_files(snapshot)
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.write(_render_watch(snapshot))
            sys.stdout.write("\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Track and visualize Codex agent status")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--role", required=True)
    start.add_argument("--mode", required=True)
    start.add_argument("--worktree", required=True)
    start.set_defaults(func=command_start)

    stop = subparsers.add_parser("stop")
    stop.add_argument("--role", required=True)
    stop.add_argument("--mode", default="")
    stop.add_argument("--worktree", default="")
    stop.set_defaults(func=command_stop)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.set_defaults(func=command_snapshot)

    watch = subparsers.add_parser("watch")
    watch.add_argument("--interval", type=float, default=2.0)
    watch.set_defaults(func=command_watch)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
