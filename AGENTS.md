# Multi-Agent Workflow

This repo supports parallel Codex agents working in isolated git worktrees.

## Product Goal

Build the easiest publicly available Chief of Staff job board to browse and share.

Current priorities:
- Make the GitHub Pages experience fast, clear, polished, and reliable.
- Improve scraper accuracy, especially for Lever normalization and job metadata quality.
- Keep workflows fast, cheap, and deterministic.
- Preserve a clean public feed for Chief of Staff, adjacent strategy and operations, program-management, and learning-design roles.

## Agent Roles

- `orchestrator`
  - Owns planning, merge order, and cross-agent acceptance criteria.
  - Keeps the backlog prioritized and prevents duplicate work.
- `workflow-optimizer`
  - Improves GitHub Actions runtime, artifact size, scrape chunking, and publish reliability.
- `workflow-ops`
  - Monitors GitHub Actions, diagnoses failures, and can rerun safe workflows when useful.
- `scraper-accuracy`
  - Focuses on ATS normalization, metadata extraction, and source-level diagnostics.
- `board-scout`
  - Finds new ATS providers and custom public job boards, then reverse-engineers their usable fields.
- `pages-designer`
  - Owns visual direction, hierarchy, typography, empty states, and mobile polish.
- `pages-ui`
  - Owns HTML/CSS/JS implementation quality, performance, resilience, and accessibility.
- `qa-review`
  - Verifies tests, artifact contracts, failure handling, and dashboard behavior.

Role briefs live under `.codex/agents/`.
Native Codex agent configs also live under `.codex/agents/*.toml` and are registered in `.codex/config.toml`.

## Working Rules

- Use one git worktree per agent.
- Keep each agent scoped to one domain unless the orchestrator explicitly expands scope.
- Prefer additive improvements over broad rewrites.
- Agents should work in reviewable cycles and leave handoffs after each pass.
- If an agent asks the user a question, it must include:
  - why the question matters right now
  - its recommended answer
  - why that recommendation is the best default
  - a concise statement of what it will assume if the user does not answer
- Before merging Pages work:
  - Dashboard loads with `docs/data/*.json`.
  - Empty/error states render cleanly.
  - Mobile layout works.
  - Filters/search do not throw runtime errors.
- Before merging scraper/workflow work:
  - `python3 -m unittest discover -s tests -v`
  - `PYTHONPYCACHEPREFIX=/tmp/chief-of-staff-pyc python3 -m py_compile src/*.py tests/*.py`
  - workflow YAML parses cleanly

## Handoff Contract

Every agent should leave:
- a short summary of what changed
- files touched
- tests run
- risks or follow-ups

Additional requirements:
- `workflow-ops` must record every rerun, workflow check, or operational action taken.
- `board-scout` must leave a structured source-analysis handoff with:
  - board/vendor name
  - sample URLs
  - how jobs are loaded
  - fields available
  - anti-bot/rate-limit notes
  - integration recommendation
  - estimated implementation complexity

If an agent changes the publish contract, it must update:
- `tests/test_pipeline_contract.py`
- `README.md`
- `docs/index.html` if dashboard-visible behavior changed

## Worktree Layout

Recommended sibling worktrees:
- `../chief-orchestrator`
- `../chief-workflow`
- `../chief-workflow-ops`
- `../chief-scraper`
- `../chief-board-scout`
- `../chief-pages-design`
- `../chief-pages-ui`
- `../chief-qa`

Use `scripts/setup_multi_agent_worktrees.sh` to create them.

## One-command Launch

- `bash scripts/launch_codex_agents.sh single`
  - launches one orchestrator Codex session in this repo with multi-agent flags enabled
- `bash scripts/launch_codex_agents.sh multi`
  - creates worktrees and opens one Codex session per role in Terminal
- `bash scripts/launch_codex_agents.sh ops`
  - launches orchestrator + workflow-ops + qa-review
- `bash scripts/launch_codex_agents.sh discovery`
  - launches orchestrator + board-scout + scraper-accuracy
- `bash scripts/launch_codex_agents.sh pages`
  - launches orchestrator + pages-designer + pages-ui + qa-review
