#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_BRANCH="${1:-main}"

declare -A WORKTREES=(
  [chief-orchestrator]="../chief-orchestrator"
  [chief-workflow]="../chief-workflow"
  [chief-workflow-ops]="../chief-workflow-ops"
  [chief-scraper]="../chief-scraper"
  [chief-board-scout]="../chief-board-scout"
  [chief-pages-design]="../chief-pages-design"
  [chief-pages-ui]="../chief-pages-ui"
  [chief-qa]="../chief-qa"
)

cd "$ROOT_DIR"

for branch in "${!WORKTREES[@]}"; do
  target="${WORKTREES[$branch]}"
  if [ -d "$target/.git" ] || [ -f "$target/.git" ]; then
    echo "[info] Worktree already exists: $target"
    continue
  fi

  if git show-ref --verify --quiet "refs/heads/$branch"; then
    echo "[info] Reusing local branch $branch for $target"
    git worktree add "$target" "$branch"
  else
    echo "[info] Creating worktree $target from $BASE_BRANCH as branch $branch"
    git worktree add -b "$branch" "$target" "$BASE_BRANCH"
  fi
done

echo
echo "[info] Multi-agent worktrees ready."
echo "[info] Role registry: .codex/config.toml"
echo "[info] Role briefs: .codex/agents/"
echo "[info] Backlog: .codex/backlog.md"
