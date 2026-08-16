# DasLab

An operating system for a 32-agent AI software organization: role charters, a
file-based board, a gated delivery lifecycle, and Claude Code orchestration.

DasLab is not a coding agent. It is the layer **above** one — it decides what
gets worked on, by which role, in what order, under which gate, and with what
evidence. The agent that writes the code is Claude Code, invoked per ticket.

- **Source of truth:** [`config/org.yaml`](config/org.yaml) (roles, charters,
  routing) and [`org/schema.daslab.yaml`](org/schema.daslab.yaml) (gates,
  escalation ladder, never-auto-approve classes).
- **State:** ticket files under `board/tickets/`. An agent's edits to a ticket
  file *are* the state — there is no remote API.
- **Everything generated is generated.** Agent charters, guild templates and
  the tool allowlist are compiled from the org model, never hand-edited.

## Quickstart

```bash
python3 scripts/bootstrap.py
python3 scripts/doctor.py
```

`bootstrap.py` is idempotent: it creates the `projects/` workspace, compiles the
32 agent charters into `.claude/agents/`, and runs the environment preflight.
`doctor.py` exits non-zero if a REQUIRED check fails.

Requirements: Python >= 3.11, `git`, and the `claude` CLI on PATH.
Install the runtime dependency with `pip install -r requirements.txt`
(PyYAML only — everything else is stdlib).

## Running a project

DasLab drives projects that live under `projects/<name>/`, each with its own
git history. The engine repo stays project-agnostic (LAW C, enforced by
[`scripts/check_project_isolation.py`](scripts/check_project_isolation.py)).

1. **Write the manifest.** `projects/<name>/PROJECT-OS.yaml` with the six
   required keys: `name`, `mission`, `constraints`, `stack`, `budget`,
   `success_metrics`. See
   [`evals/e2e/sample-pack/PROJECT-OS.yaml`](evals/e2e/sample-pack/PROJECT-OS.yaml)
   for a filled-in example.

2. **Write the goal queue.** `projects/<name>/APPROVED-GOAL-QUEUE.md` — a
   markdown table whose header includes `goal_slug`, plus `status`, `zone`,
   `outcome` and `owner` columns. Only rows with status `founder_approved`,
   `planned` or `active` compile. The queue must carry a Founder approval
   marker (`APPROVED:` / `TASDIQLANDI:`) or nothing compiles at all — this is
   QONUN-3, enforced by
   [`scripts/check_approved_goal_queue.py`](scripts/check_approved_goal_queue.py).

   The `zone` column is the parallelism knob: two goals in different zones can
   run in the same wave, two goals in the same zone cannot. Pick zones along
   file-territory lines so concurrent agents never touch the same files.

3. **Compile goals into tickets.** Each goal becomes one epic plus six story
   tickets, one per AADL stage (Planning, Design, Development, Testing,
   Deployment, Maintenance), each carrying its gate and owning role:

   ```bash
   python3 scripts/gateway_compile.py projects/<name>
   ```

4. **Plan a wave, then run it.** `--dry-run` prints the plan and writes
   nothing; `--dispatch` executes it:

   ```bash
   python3 scripts/orchestrator.py --dry-run
   python3 scripts/orchestrator.py --dispatch
   ```

   The wave planner enforces one ticket per zone and WIP = 1 per role, then the
   orchestrator dispatches the wave in parallel through
   [`scripts/claude_invoker.py`](scripts/claude_invoker.py), journalling every
   attempt so an interrupted wave can be resumed.

5. **Watch it.** `python3 scripts/cockpit.py` renders the operator cockpit in
   the terminal (`--glossary` explains the vocabulary). The React dashboard
   under `dashboard/` reads the same board through the FastAPI control plane in
   `tools/control_plane/`.

## The gate model

Six gates, each owned by a named role, each requiring evidence before the work
advances. GATE-5 (deployment) cannot be skipped: no launch with GATE-5 open.

Certain change classes are never auto-approved and always require a human
answer — new goals, security-sensitive work, **schema migrations**, deployment,
governance or policy edits, permission changes and secret changes. The list
lives in [`org/schema.daslab.yaml`](org/schema.daslab.yaml) under
`never_auto_approve` and is enforced by
[`scripts/check_never_auto_approve.py`](scripts/check_never_auto_approve.py).

Questions the org cannot answer itself become interrupt cards under
`board/interrupts/` and wait for the Founder.

## Current status — read this before trusting the score

`python3 scripts/diagnostics.py` reports 100/100 and CI runs 69 gates, but that
measures the engine, not a delivery record. As of this commit:

- The board is empty and no wave has ever run. `board/wave-ledger.jsonl` is
  empty; there is no dispatch journal, event store or run directory.
- Because there is no runtime data, roughly 19 of the CI gates are **inert** —
  they report `unmeasured`, `0 checked`, or `gate inert (loop off)` and pass.
  They begin to bite once real waves produce evidence. The gates say so in
  their own output; none of them fakes a green.
- The autonomous heartbeat is **off** in [`config/features.yaml`](config/features.yaml)
  (`heartbeat_enabled: false`), and the self-optimizing loop is in shadow mode
  in [`config/loop.yaml`](config/loop.yaml). Waves are launched by hand today.
- [`scripts/heartbeat_go_no_go.py`](scripts/heartbeat_go_no_go.py) is the gate
  that decides when the heartbeat may be flipped on. It currently returns
  **NO-GO**: it wants a clean shadow window and rolling waves that do not exist
  yet.

## Memory layer

Recall and storage are optional and degrade cleanly. Full mode needs Ollama
with the `nomic-embed-text` model for embeddings, plus an ArcRift store at
`~/ArcRift` for persistence. Without them the org still boots and runs;
`bootstrap.py` reports MEMORY-OPTIONAL mode and recall/store become best-effort.
Governance for what may be remembered lives in `config/memory_governance.yaml`.

## Repository layout

| Path | What lives there |
| --- | --- |
| `config/` | org model, feature flags, budgets, RBAC, risk taxonomy, tenant boundary |
| `org/` | the typed org schema — gates, escalation ladder, never-auto-approve |
| `board/` | tickets, interrupt cards, wave ledger, schedule |
| `scripts/` | the engine — orchestrator, wave planner, compilers, and the gate battery |
| `governance/` | per-role guardrails, communication flows, contract schemas |
| `tools/` | sandbox, model gateway, A2A endpoint, MCP bridges, observability, control plane |
| `evals/` | per-role golden evals; a role scoring below 0.80 fails CI |
| `dashboard/` | React operator dashboard |
| `tests/` | 3 500+ tests, run by `python -m pytest` |

## Development

```bash
pip install --require-hashes -r requirements-dev.txt
ruff check .
python -m pytest -q
python3 scripts/diagnostics.py
```

Two laws surprise newcomers:

- **Code-only.** No comments and no docstrings in first-party Python.
  [`scripts/check_no_prose.py`](scripts/check_no_prose.py) enforces it. Names
  and structure carry the meaning; prose belongs in Markdown like this file.
- **No-data never reads as healthy.** A check that measured nothing exits 3, not
  0. Treating an empty measurement as a pass is how dashboards lie.

The full gate battery is in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
Release builds a wheel on a `v*` tag and requires diagnostics at 100/100.

## License

Apache-2.0 — see [LICENSE](LICENSE).
