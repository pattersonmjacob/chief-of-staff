#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_BIN="${CODEX_BIN:-$(command -v codex || true)}"
MODE="${1:-single}"
BASE_BRANCH="${2:-main}"

if [ -z "$CODEX_BIN" ]; then
  echo "[error] Could not find 'codex' on PATH."
  exit 1
fi

agent_command() {
  local role="$1"
  local role_file="$2"
  local abs_worktree="$3"
  local mode="$4"
  local prompt="$5"
  cat <<EOF
cd "$abs_worktree" && python3 "$ROOT_DIR/scripts/agent_monitor.py" start --role "$role" --mode "$mode" --worktree "$abs_worktree" && set +e; "$CODEX_BIN" --enable multi_agent --full-auto -C "$abs_worktree" "$prompt"; status=\$?; set -e; python3 "$ROOT_DIR/scripts/agent_monitor.py" stop --role "$role" --mode "$mode" --worktree "$abs_worktree"; exit \$status
EOF
}

setup_worktrees() {
  bash "$ROOT_DIR/scripts/setup_multi_agent_worktrees.sh" "$BASE_BRANCH"
}

prompt_for_role() {
  local role="$1"
  local role_file="$2"
  cat <<EOF
Use $role_file as your role brief and follow $ROOT_DIR/AGENTS.md.

Your role: $role

Repo goal:
- Build the easiest publicly available Chief of Staff job board to browse and share.

Immediate focus:
- Improve GitHub Pages until it feels polished, loads cleanly, and works without error.
- Keep finding workflow, scraping, and artifact optimizations that save time and space.

Before finishing:
- Leave a short handoff with files changed, tests run, and next suggestions.
- If you ask the user a question, explain why it matters, give your recommendation, explain why it is recommended, and state the default assumption you will use if they do not answer.
EOF
}

single_orchestrator_prompt() {
  cat <<EOF
Use $ROOT_DIR/.codex/agents/orchestrator.md as your role brief and follow $ROOT_DIR/AGENTS.md.

Your role: orchestrator

Repo goal:
- Build the easiest publicly available Chief of Staff job board to browse and share.

Immediate mission:
- Pages-first polish until the public board feels clean, fast, stable, and easy to share.
- Improve workflow reliability and reduce wasted runtime or artifact bloat.
- Expand source discovery through the board scout and route good candidates into scraper work.
- Use repeated review cycles with handoffs instead of open-ended drifting.

Coordinate these roles when useful:
- workflow-optimizer
- workflow-ops
- scraper-accuracy
- board-scout
- pages-designer
- pages-ui
- qa-review
- security-review

Before finishing:
- Leave a summary of who should act next, what changed, and what still needs review.
- If you ask the user a question, explain why it matters, give your recommendation, explain why it is recommended, and state the default assumption you will use if they do not answer.
EOF
}

build_sessions() {
  local mode="$1"
  case "$mode" in
    multi)
      cat <<EOF
chief-orchestrator|../chief-orchestrator|$ROOT_DIR/.codex/agents/orchestrator.md|orchestrator
chief-workflow|../chief-workflow|$ROOT_DIR/.codex/agents/workflow-optimizer.md|workflow-optimizer
chief-workflow-ops|../chief-workflow-ops|$ROOT_DIR/.codex/agents/workflow-ops.md|workflow-ops
chief-scraper|../chief-scraper|$ROOT_DIR/.codex/agents/scraper-accuracy.md|scraper-accuracy
chief-board-scout|../chief-board-scout|$ROOT_DIR/.codex/agents/board-scout.md|board-scout
chief-pages-design|../chief-pages-design|$ROOT_DIR/.codex/agents/pages-designer.md|pages-designer
chief-pages-ui|../chief-pages-ui|$ROOT_DIR/.codex/agents/pages-ui.md|pages-ui
chief-qa|../chief-qa|$ROOT_DIR/.codex/agents/qa-review.md|qa-review
chief-security|../chief-security|$ROOT_DIR/.codex/agents/security-review.md|security-review
EOF
      ;;
    pages)
      cat <<EOF
chief-orchestrator|../chief-orchestrator|$ROOT_DIR/.codex/agents/orchestrator.md|orchestrator
chief-pages-design|../chief-pages-design|$ROOT_DIR/.codex/agents/pages-designer.md|pages-designer
chief-pages-ui|../chief-pages-ui|$ROOT_DIR/.codex/agents/pages-ui.md|pages-ui
chief-qa|../chief-qa|$ROOT_DIR/.codex/agents/qa-review.md|qa-review
EOF
      ;;
    ops)
      cat <<EOF
chief-orchestrator|../chief-orchestrator|$ROOT_DIR/.codex/agents/orchestrator.md|orchestrator
chief-workflow-ops|../chief-workflow-ops|$ROOT_DIR/.codex/agents/workflow-ops.md|workflow-ops
chief-qa|../chief-qa|$ROOT_DIR/.codex/agents/qa-review.md|qa-review
chief-security|../chief-security|$ROOT_DIR/.codex/agents/security-review.md|security-review
EOF
      ;;
    discovery)
      cat <<EOF
chief-orchestrator|../chief-orchestrator|$ROOT_DIR/.codex/agents/orchestrator.md|orchestrator
chief-board-scout|../chief-board-scout|$ROOT_DIR/.codex/agents/board-scout.md|board-scout
chief-scraper|../chief-scraper|$ROOT_DIR/.codex/agents/scraper-accuracy.md|scraper-accuracy
EOF
      ;;
    security)
      cat <<EOF
chief-orchestrator|../chief-orchestrator|$ROOT_DIR/.codex/agents/orchestrator.md|orchestrator
chief-security|../chief-security|$ROOT_DIR/.codex/agents/security-review.md|security-review
chief-qa|../chief-qa|$ROOT_DIR/.codex/agents/qa-review.md|qa-review
EOF
      ;;
    *)
      return 1
      ;;
  esac
}

launch_single_orchestrator() {
  local prompt
  prompt="$(single_orchestrator_prompt)"
  cd "$ROOT_DIR"
  python3 "$ROOT_DIR/scripts/agent_monitor.py" start --role orchestrator --mode single --worktree "$ROOT_DIR"
  set +e
  "$CODEX_BIN" \
    --enable multi_agent \
    --full-auto \
    -C "$ROOT_DIR" \
    "$prompt"
  local status=$?
  set -e
  python3 "$ROOT_DIR/scripts/agent_monitor.py" stop --role orchestrator --mode single --worktree "$ROOT_DIR"
  return "$status"
}

launch_mode_in_terminal() {
  local mode="$1"
  setup_worktrees

  local session_lines
  session_lines="$(build_sessions "$mode")"
  mapfile -t sessions <<<"$session_lines"

  local osa_script
  osa_script="$(mktemp)"
  {
    echo 'tell application "Terminal"'
    echo 'activate'
    local first=1
    for session in "${sessions[@]}"; do
      IFS='|' read -r _ worktree role_file role_name <<<"$session"
      local abs_worktree
      abs_worktree="$(cd "$ROOT_DIR" && cd "$worktree" && pwd)"
      local prompt
      prompt="$(prompt_for_role "$role_name" "$role_file")"
      local command
      command="$(agent_command "$role_name" "$role_file" "$abs_worktree" "$mode" "$prompt")"
      command="${command//$'\n'/}"
      command="${command//\"/\\\"}"
      prompt="${prompt//$'\n'/\\n}"
      if [ "$first" -eq 1 ]; then
        echo "do script \"$command\""
        first=0
      else
        echo "do script \"$command\" in front window"
      fi
    done
    echo 'end tell'
  } > "$osa_script"

  /usr/bin/osascript "$osa_script"
  rm -f "$osa_script"
}

print_help() {
  cat <<EOF
Usage:
  bash scripts/launch_codex_agents.sh single
  bash scripts/launch_codex_agents.sh multi
  bash scripts/launch_codex_agents.sh pages
  bash scripts/launch_codex_agents.sh ops
  bash scripts/launch_codex_agents.sh discovery
  bash scripts/launch_codex_agents.sh security

Modes:
  single     Launch one orchestrator Codex session in the current repo with multi-agent flags enabled.
  multi      Create worktrees and open one Codex Terminal session per role.
  pages      Launch orchestrator + pages-designer + pages-ui + qa-review.
  ops        Launch orchestrator + workflow-ops + qa-review.
  discovery  Launch orchestrator + board-scout + scraper-accuracy.
  security   Launch orchestrator + security-review + qa-review.
EOF
}

case "$MODE" in
  single)
    launch_single_orchestrator
    ;;
  multi)
    launch_mode_in_terminal multi
    ;;
  pages)
    launch_mode_in_terminal pages
    ;;
  ops)
    launch_mode_in_terminal ops
    ;;
  discovery)
    launch_mode_in_terminal discovery
    ;;
  security)
    launch_mode_in_terminal security
    ;;
  *)
    print_help
    exit 1
    ;;
esac
