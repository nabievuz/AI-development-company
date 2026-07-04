# DasLab

[![CI](https://github.com/nabievuz/daslab/actions/workflows/ci.yml/badge.svg)](https://github.com/nabievuz/daslab/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/nabievuz/daslab?label=release&color=blue)](https://github.com/nabievuz/daslab/releases)

**DasLab** (*Dasturlash Laboratoriyasi*, "Programming Laboratory"; ticket prefix `DAS`) is an
AI-native software company — a complete organization of **32 Claude Code subagents** that plan,
design, build, review, ship, and operate real software with minimal human input.

It is not a single agent with tools. It is an org: a board, a CEO, a C-suite, leads, and individual
contributors — each a separate subagent with its own charter, instructions, and reporting line. The
whole company is a self-contained, reproducible system checked into this repository. A fresh
`git clone` boots the entire org.

Public repo: **github.com/nabievuz/daslab** (`main` is the released line). Versioned per
[SemVer](https://semver.org/) — see [`CHANGELOG.md`](CHANGELOG.md). License: **Apache-2.0**.

---

## At a glance

| Capability | What it means |
| --- | --- |
| **32-agent organization** | A four-level hierarchy (Board → CEO → C-suite → leads → ICs) across six departments, each agent a Claude Code subagent with a written charter. |
| **File-based board** | Platform (org-engine) work lives as Markdown tickets in `board/tickets/DAS-*.md`; a project's own tickets live in its own `projects/<slug>/board-tickets/` board. No timer, no server, no API — just files, git, and subagents. |
| **Operator-invoked waves** | Work advances only when a human runs `/daslab-cycle`. One wave triages the board, dispatches every actionable subagent in parallel, collects results, and reports. |
| **Orchestration skills** | `/daslab-plan` turns a goal into board tickets; `/daslab-cycle` runs one work wave; `/daslab-run` drains the approved goal queue across waves. |
| **AADL lifecycle** | Every AI-agent build moves through six gated stages: Planning → Design → Development → Testing → Deployment → Maintenance. |
| **100/100 release gate** | `scripts/diagnostics.py` is a weighted, all-or-nothing 7-dimension scorer. It exits non-zero unless the score is exactly 100/100. |
| **DGO-X control plane** | A graph-orchestrated, gate-driven control plane layered on top of the board — currently in shadow mode, changing nothing about dispatch. |
| **ArcRift memory** | Long-term memory lives in an MCP server. Each unit of work recalls context at the start and stores a decision at the end, scoped strictly per project. |
| **Durable runs** *(v2.0)* | Every wave gets a run-id, wave checkpoints, and a committed hash-chained attestation — crash-safe resume/fork with zero lost or duplicated tickets (kill-drill verified). |
| **Observability & cost** *(v2.0)* | OTel-shaped span events per dispatch, a per-run cost ledger, and committed, git-auditable KPI evidence — the T1–T7 gates read from real spans, never vibes. |
| **HEARTBEAT tempo** *(v2.0)* | An autonomous scheduler substrate (ADR-0027 safety rails). It ships **OFF / shadow** by default; going live is a Founder-only, evidence-gated act (`scripts/check_heartbeat_readiness.py`, [`docs/runbooks/heartbeat-go-live.md`]). |
| **Golden-eval competence** *(v2.0)* | All **32 roles** carry ≥3 deterministic golden tasks scored ≥0.80 at their assigned tier (`agent_eval.py`), guarded by an anti-gaming probe (empty-submission + strict task.md answer-leak detection). |
| **Project-OS gateway** *(v2.0)* | A documentation pack compiles into a project board of self-contained story tickets the org then delivers 0→100 through the six AADL gates. |

---

## Quickstart

```bash
git clone https://github.com/nabievuz/daslab.git
cd daslab

# 1. Idempotent first-run setup (creates projects/, regenerates the 32 agents).
python3 scripts/bootstrap.py

# 2. Environment preflight. Required checks (Claude Code, Python) must PASS;
#    ArcRift and Ollama are optional and surface only as WARN.
python3 scripts/doctor.py
```

Then open a Claude Code session at the repo root and drive the org:

```text
claude
> /daslab-plan "<your goal>"   # decompose a goal into board tickets
> /daslab-cycle                 # run one gate-enforced work wave
> /daslab-run                   # drain the Founder-approved goal queue across waves
```

The Quickstart's `bootstrap` → `doctor` ordering is itself CI-enforced (`scripts/check_quickstart.py`).

---

## The organization

DasLab is structured as a real company on a four-level hierarchy:

```
Board (Chairman of the Board + Board Member)
  └─ CEO
       └─ C-suite department managers — CTO · CPO · CDO · CMO · COO
            └─ Leads
                 └─ Individual Contributors
```

The 32 agents split across six departments (sums to 32, one file per role in `.claude/agents/`):

| Department | Manager | Agents |
| --- | --- | ---: |
| Governance | Chairman of the Board | 3 (Chairman, Board Member, CEO) |
| Engineering | CTO | 13 |
| Product | CPO | 4 |
| Design | CDO | 4 |
| Marketing | CMO | 4 |
| Operations | COO | 4 |

Of the 32 roles, 29 are wave-dispatched (the CEO, all five C-suite managers, every lead, and every
IC); only the Chairman and the Board Member are wake-on-approval — they act on approvals rather than
participating in every `/daslab-cycle` wave.

The full reviewer and reporting map for every role lives in [`board/ROUTING.md`](board/ROUTING.md)
(generated, never hand-edited). The org chart and roster are documented in
[`docs/02-ORG.md`](docs/02-ORG.md).

### Model allocation

Each agent runs on the Claude model its task complexity needs — the task decides, not the title.
The canonical table is [`governance/policies/model-allocation.md`](governance/policies/model-allocation.md):

- **opus × 10** — the eight gate owners plus the CTO and the Security Lead, permanently on opus.
- **sonnet × 19** — the execution core.
- **haiku × 3** — high-frequency, templated work.

`scripts/gen_subagents.py` parses that table and regenerates every `.claude/agents/<role>.md` shim plus
`board/ROUTING.md`. On dispatch, the model is **always** passed explicitly — the frontmatter alone is
not trusted at runtime.

---

## Runtime: the file-based board

DasLab runs as Claude Code subagent sessions over a file-based board. There is **no timer, no server,
and no API** — role subagents and the orchestrator read and edit files directly, and git plus worktree
isolation handle concurrency.

- **One ticket = one file** at `board/tickets/DAS-*.md`, with snake_case YAML frontmatter
  (`id`, `title`, `status`, `assignee`, `author`, `dept`, `priority`, `parent`, `goal`,
  `created`, `updated`) plus acceptance criteria.
- **Status enum (Kanban):** `backlog → todo → in_progress → blocked → in_review → done`.
- **Roles** live as generated shims in `.claude/agents/` and are produced from the department and role
  overlays — never hand-edited.

See [`board/README.md`](board/README.md) for the full ticket-store specification.

### The wave

Work advances only when a human operator invokes `/daslab-cycle`. **One wave** = the orchestrator
triages the board, dispatches every actionable role subagent in parallel, collects results, and
reports. Each subagent runs once per wave: read its ticket → do the work → report → exit. A role with
nothing actionable is simply not dispatched.

WIP is one ticket per role per wave. Concurrency is bounded only by the Claude Code harness, the AADL
gate order, and the same-repo-zone correctness guard (one ticket per repo zone per wave) — never by a
clock or a policy cap.

### Orchestration skills

The three orchestration skills live in `.claude/skills/`:

| Skill | What it does |
| --- | --- |
| **`/daslab-plan`** | Decomposes a goal into board tickets — epics plus PR-sized tickets with owners per RACI. Runs the Founder Discovery Gate for new projects. Dispatches no work. |
| **`/daslab-cycle`** | Runs ONE work wave: prewarm ArcRift recall, triage and route the board, select every actionable ticket, create one git worktree per code-touching ticket, dispatch role subagents in parallel with an explicit model, collect and verify, reap worktrees, and report. |
| **`/daslab-run`** | The supervisor that drains the Founder-approved goal queue across waves — plan the next approved item, then run cycle waves until the tickets drain. |

Additional operator and role skills live in the top-level `skills/` directory:
`daslab-canary`, `daslab-investigate`, `daslab-learn`, `daslab-qa`, `daslab-review`, and
`daslab-security-audit`.

---

## Governance

DasLab is run as a governed company, not a free-for-all.

- **Company charter** — [`governance/charter.md`](governance/charter.md) defines the mission, the
  binding values (customer outcome first; decisions in writing; smallest reversible step; no silent
  blockers; authority local / accountability upstream; budget is a constraint; security and compliance
  non-negotiable), the governance structure, and the authority matrix for hires, strategy, budget,
  policy, spend, and release.
- **Binding board policies** — [`governance/policies/`](governance/policies/) holds
  [`raci.md`](governance/policies/raci.md) (per-decision RACI across eight domains, exactly one
  Accountable per row), [`model-allocation.md`](governance/policies/model-allocation.md),
  [`ai-agent-lifecycle.md`](governance/policies/ai-agent-lifecycle.md),
  [`quality-bar.md`](governance/policies/quality-bar.md), and
  [`memory-modes.md`](governance/policies/memory-modes.md).
- **Cadence** — per-wave reports, weekly board minutes, monthly strategic review, and quarterly charter
  review.

### Methodology

The operating model is a deliberate hybrid of three disciplines:

- **Operational layer — Kanban.** Pull-based, WIP = 1, no sprints.
- **Governance layer — PRINCE2 / PMBOK.** Charter, RACI, RFC/ADR gates, board approvals for hires,
  budget, and strategy, with weekly/monthly/quarterly cadence.
- **Engineering practice — Lean + selective XP.** Smallest reversible step, no silent blockers, TDD on
  engineering roles.

### The AI-Agent Development Lifecycle (AADL)

Every AI-agent program moves through six ordered stages, each closed by its numbered gate checklist
and logged in the project's stage board:

```
Planning → Design → Development → Testing → Deployment → Maintenance
 GATE-1     GATE-2    GATE-3        GATE-4     GATE-5        GATE-6
```

The binding source is [`governance/policies/ai-agent-lifecycle.md`](governance/policies/ai-agent-lifecycle.md),
aligned with NIST AI RMF 1.0, ISO/IEC 42001, and the OWASP Top 10 for LLMs. `/daslab-plan` produces
stage-gated epics, and `/daslab-cycle` never dispatches a ticket sitting behind an open gate
(enforced by `scripts/check_gates.py`). Skipping a stage is forbidden; shipping to production with
GATE-5 open is forbidden.

---

## Quality engine

### The release gate

[`scripts/diagnostics.py`](scripts/diagnostics.py) is the single source of truth for the release gate:
a weighted 7-dimension scorer that exits non-zero unless the total is exactly **100/100**.

| Dimension | Weight |
| --- | ---: |
| Documentation | 20 |
| Architecture | 20 |
| Code quality | 15 |
| Consistency | 15 |
| Portability | 15 |
| Security | 10 |
| Git hygiene | 5 |
| **Total** | **100** |

Each dimension is all-or-nothing: it earns its full weight only if every check passes, otherwise 0.
A missing artifact fails gracefully without crashing.

```bash
python3 scripts/diagnostics.py        # prints SCORE = 100/100 on a clean tree

# Full local gate:
ruff check scripts && python3 -m pytest -q && python3 scripts/diagnostics.py
```

### CI-enforced validators

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests and pushes to `main`. It
lints with `ruff`, `py_compile`s every tracked Python file, runs the `pytest` suites, and runs a long
chain of enforcement validators, including:

- `board_lint.py` — ticket schema, status enum, routing, no orphans, no self-review
- `check_agents_sync.py` — fails if the agent shims or `ROUTING.md` drift from the overlays and the model table
- `check_gates.py` — AADL gate order
- `check_no_hardcoded_paths.py` — portability
- `check_project_isolation.py` — no project-specific name leaks into engine files
- `check_no_dead_runtime.py` — keeps the engine server-free
- `check_codeowners.py` — `CODEOWNERS` coverage and sync
- `check_quickstart.py` — the README Quickstart commands exit 0 on a fresh clone
- `check_links.py` — broken relative links

…plus `check_precedence.py`, `check_never_auto_approve.py`, `check_clarifications.py`, and more.

---

## DGO-X control plane

**DGO-X** is a deterministic, graph-orchestrated, gate-driven control plane that sits *on top of* the
file-based board — it extends the board model, it does not replace it. It was adopted in
[`docs/adr/0010-adopt-dgox-graph-orchestrated-control-plane.md`](docs/adr/0010-adopt-dgox-graph-orchestrated-control-plane.md),
with Phase-1 data contracts in ADR-0011 and the redaction policy in ADR-0012.

The Python helpers live in [`scripts/dgox/`](scripts/dgox/):

- `state.py` — a typed `graph_state` schema with per-field write authority and up-only severity invariants
- `events.py` — an append-only event store, the audit system-of-record
- `board_adapter.py` — board-runtime integration

DGO-X currently runs in **shadow mode**: it mirrors state alongside the board without changing any
dispatch behavior, so `/daslab-cycle` is unaffected. Shadow event emission is feature-flagged in
[`config/features.yaml`](config/features.yaml) (`dgox_emit`, off by default) and stays off until a
downstream consumer goes live.

---

## ArcRift persistent memory

DasLab's long-term memory lives in **ArcRift**, a local MCP server wired in
[`.mcp.json`](.mcp.json) under the name `ArcRift`. Context is not lost between sessions:

- Each unit of work calls `recall_context` at the start and `store_memory` at the end.
- Memory is scoped strictly by a flat project key (`daslab`, or `daslab-<slug>`); mixing one project's
  facts into another is forbidden. `prune_memory` removes stale facts.
- Graph triple extraction routes to a local Claude bridge; embeddings use a local Ollama model.
- ArcRift and Ollama are **optional** for booting the engine — `scripts/doctor.py` treats them as WARN,
  not required. Schema-migration discipline is managed with Alembic (`alembic.ini` + `migrations/`).

The binding rule is the Persistent Memory Law in [`CLAUDE.md`](CLAUDE.md).

---

## Repository layout

| Path | What lives there |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Umbrella spec (binding): runtime rules, precedence, QONUN laws. |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code project instructions and the QONUN laws. |
| [`CHANGELOG.md`](CHANGELOG.md) / `VERSION` | Release history (Keep a Changelog) and the current SemVer string. |
| [`governance/`](governance/) | Company charter, binding board policies, board minutes. |
| `engineering/` `product/` `design/` `marketing/` `operations/` | Department charters (`<dept>/CLAUDE.md`), role overlays (`<dept>/agents/<role>/AGENTS.md`), and department artifacts. |
| [`board/`](board/) | File-based ticket store (`tickets/DAS-*.md`) and the `ROUTING.md` reviewer table. |
| [`.claude/agents/`](.claude/agents/) | The 32 generated subagent shims (do not hand-edit). |
| [`.claude/skills/`](.claude/skills/) | Orchestration skills: `daslab-plan`, `daslab-cycle`, `daslab-run`. |
| [`skills/`](skills/) | Operator and role skills: `daslab-canary`, `daslab-investigate`, `daslab-learn`, `daslab-qa`, `daslab-review`, `daslab-security-audit`. |
| [`scripts/`](scripts/) | Load-bearing tooling, including the `scripts/dgox/` control-plane package. |
| [`tests/`](tests/) | pytest suites for the validators and DGO-X. |
| [`docs/`](docs/) | [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) (system design + diagrams), [`USAGE.md`](docs/USAGE.md) (operator guide), the operator guides (`docs/README.md` index), and ADRs in [`docs/adr/`](docs/adr/). |
| [`config/`](config/) | Runtime config — `.env.example` plus YAML thresholds and policy files. |
| [`org/`](org/) | `schema.daslab.yaml` — the org-schema single source of truth. |
| [`metrics/`](metrics/) | `registry.yaml` — the metric registry. |
| [`migrations/`](migrations/) | Alembic migrations. |
| [`experiments/`](experiments/) | GATE-6 evidence records. |
| `projects/` | Per-project workspaces (gitignored; each manages its own git). |

---

## Precedence

When documents disagree, lower levels may **add** constraints but never relax a higher one:

1. [`governance/charter.md`](governance/charter.md) — the company charter
2. board-issued policy in [`governance/`](governance/) (security, compliance, hiring, conduct) — e.g. RACI, the AADL lifecycle, model allocation
3. `<dept>/CLAUDE.md` — department charter
4. `<dept>/agents/<role>/AGENTS.md` — role overlay
5. `<dept>/AGENTS.md` — department runtime instructions
6. [`AGENTS.md`](AGENTS.md) — the umbrella spec

---

## The QONUN laws

QONUN ("law") rules are hard, binding constraints defined in [`CLAUDE.md`](CLAUDE.md) and
[`AGENTS.md`](AGENTS.md). The headline laws:

1. **Project Placement** — every project lives ONLY under `projects/<name>/`. One project = one folder;
   `projects/` is gitignored and each project manages its own git. Deleting a project is a single
   `rm -rf projects/<name>`.
2. **AI-Agent Lifecycle** — every AI-agent program follows the six-stage AADL, each stage closed by its
   gate. No production launch with GATE-5 open.
3. **Model Allocation** — each agent runs on the Claude model its task complexity needs
   (opus × 10 / sonnet × 19 / haiku × 3); the model is passed explicitly on every dispatch.
4. **Persistent Memory (ArcRift)** — recall context at the start of work, store the decision at the end,
   scoped strictly per project.

A further law, the **Founder-Approved Goal Queue**, governs how new work enters the org: a new project
cannot produce board tickets until the Founder is asked at least ten discovery questions, the answers
are enriched with research into `projects/<project>/APPROVED-GOAL-QUEUE.md`, and the Founder explicitly
approves the queue.

---

## Load-bearing scripts

All in [`scripts/`](scripts/), each typed with an argparse entrypoint:

| Script | Role |
| --- | --- |
| `bootstrap.py` | Idempotent first-run setup (creates `projects/`, regenerates the 32 agents). |
| `doctor.py` | Environment preflight — Claude Code and Python required (PASS); ArcRift and Ollama optional (WARN). |
| `gen_subagents.py` | Regenerates `.claude/agents/*` and `board/ROUTING.md` from the org tree and model table. |
| `gen_codeowners.py` / `check_codeowners.py` | Generate `CODEOWNERS` and gate it against drift. |
| `board_lint.py` | Validates every board ticket. |
| `check_agents_sync.py` | Drift gate: shims and `ROUTING.md` vs the overlays and model table. |
| `check_gates.py` | AADL gate-order enforcement. |
| `check_links.py` | Broken relative-link scanner. |
| `check_no_hardcoded_paths.py` / `check_no_dead_runtime.py` | Portability and no-dead-runtime guards. |
| `check_project_isolation.py` | No project name in engine files. |
| `diagnostics.py` | The weighted 100/100 release-gate scorer. |
| `wave_kpi.py` / `cockpit.py` | Wave-KPI reader and passive operator cockpit. |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

The core rule is **one issue = one branch = one PR = one worktree**. Never commit directly to `main` or
`release/*`; protected branches require an approving review and green CI before merge — and you may not
review your own PR (per [`board/ROUTING.md`](board/ROUTING.md)). Release history is tracked in
[`CHANGELOG.md`](CHANGELOG.md) ([SemVer](https://semver.org/) per [ADR 0022](docs/adr/0022-semantic-versioning-policy.md)).

Currently there is no active product: the org stands ready to take the next Founder-approved goal queue.

---

## License

Licensed under the [Apache License 2.0](LICENSE).
