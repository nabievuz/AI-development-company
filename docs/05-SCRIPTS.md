# 05 — Scripts Inventory

> Everything in `scripts/`. The scripts operate on repo files (the `board/`, the
> role overlays, the generated agents) — there is no runtime API.

## Core (current — load-bearing)

| Script | Purpose |
|---|---|
| `_paths.py` | **Self-locating root (LAW A).** Resolves the repo root at runtime (`DASLAB_ROOT` env → git toplevel → file-relative). Every script imports `ROOT` from here. |
| `gen_subagents.py` | **Source of truth → shims.** Regenerate all `.claude/agents/<role>.md` + `board/ROUTING.md` from the `<dept>/agents/<role>/AGENTS.md` overlays + the model-allocation table. Idempotent; never hand-edit the generated files. |
| `gen_codeowners.py` | Generate `.github/CODEOWNERS` from the dept list + `board/ROUTING.md`. Generated — do not hand-edit. |
| `bootstrap.py` | **First-run setup (LAW B).** Resolve root, ensure `projects/`, regenerate shims, run `doctor.py`. `clone → bootstrap → claude` just works; safe to re-run. |
| `doctor.py` | Environment preflight. REQUIRED checks (Claude Code, Python ≥3.10, git, root resolves, `projects/`) gate exit 0; OPTIONAL checks (ArcRift MCP, Ollama) print WARN, not fail. |
| `board_metrics.py` | Performance KPIs from the board: throughput, cycle time, gate pass-rate, blocked/rework. `--json` for machine-readable. |
| `setup_dokploy_mcp.sh` | One-time setup of the Dokploy MCP server for CI/CD operations. |

## Enforcement-as-code (validators — green + blocking in CI)

| Script | Enforces |
|---|---|
| `board_lint.py` | Ticket schema, status enum, routing, no orphans, no self-review. |
| `check_links.py` | No broken relative links in tracked Markdown. |
| `check_agents_sync.py` | `.claude/agents/*` + `ROUTING.md` match the overlays + model table. |
| `check_gates.py` | AADL gate order (no ticket actionable before its prior gate closes). |
| `check_no_hardcoded_paths.py` | No `/Users/<name>` or `/home/<name>` literal (LAW A). |
| `check_project_isolation.py` | No project-specific name in engine files (LAW C). |
| `check_no_dead_runtime.py` | Keeps the engine server-free: fails CI if a networked runtime endpoint reappears. |
| `check_codeowners.py` | `.github/CODEOWNERS` covers every top-level area + matches `gen_codeowners.py`. |
| `check_quickstart.py` | The README Quickstart runs `bootstrap` before `doctor` and its commands exit 0 on a fresh clone. |
| `diagnostics.py` | **The weighted 7-dimension 100/100 release scorer** — the single source of truth for the release gate. |
