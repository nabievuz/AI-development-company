# DasLab

[![CI](https://github.com/nabievuz/daslab/actions/workflows/ci.yml/badge.svg)](https://github.com/nabievuz/daslab/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/nabievuz/daslab?label=release&color=blue)](https://github.com/nabievuz/daslab/releases)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

**DasLab** (*Dasturlash Laboratoriyasi*, "Programming Laboratory"; ticket prefix `DAS`) is an
AI-native software company — a complete organization of **32 Claude Code subagents** that plan,
design, build, review, ship, and operate real software with minimal human input.

It is not a single agent with tools. It is an *org*: a board, a CEO, a C-suite, leads, and individual
contributors — each a separate subagent with its own charter, instructions, and reporting line. The
whole company is a self-contained, reproducible system checked into this repository. A fresh
`git clone` boots the entire org.

**v3.0 "MUSTAQIL"** (*mustaqil*, "autonomous / self-reliant") extends the org from an internal
build-shop into one with **interop and self-host reach**: it can call the ecosystem, run headless,
execute on a governed loop substrate, observe itself, harden its own tenant, prove a project 0→100,
expose a self-hosted control plane, and be *called* as a governed agent by another agent system.
Every autonomy-bearing capability ships **default-OFF** — see [Honest scope](#honest-scope).

Public repo: **github.com/nabievuz/daslab** (`main` is the released line). Versioned per
[SemVer](https://semver.org/) — see [`CHANGELOG.md`](CHANGELOG.md). License: **Apache-2.0**.

---

## At a glance

| Capability | What it means |
| --- | --- |
| **32-agent organization** | A four-level hierarchy (Board → CEO → C-suite → leads → ICs) across six departments, each agent a Claude Code subagent with a written charter. |
| **File-based board** | Platform (org-engine) work lives as Markdown tickets in `board/tickets/DAS-*.md`; a project's own tickets live in `projects/<slug>/board-tickets/`. No timer, no server, no API — just files, git, and subagents. |
| **Operator-invoked waves** | Work advances only when a human runs `/daslab-cycle`. One wave triages the board, dispatches every actionable subagent in parallel, collects results, and reports. |
| **Orchestration skills** | `/daslab-plan` turns a goal into board tickets; `/daslab-cycle` runs one work wave; `/daslab-run` drains the approved goal queue across waves. |
| **AADL lifecycle** | Every AI-agent build moves through six gated stages: Planning → Design → Development → Testing → Deployment → Maintenance. |
| **100/100 release gate** | `scripts/diagnostics.py` is a weighted, all-or-nothing 7-dimension scorer. It exits non-zero unless the score is exactly 100/100. |
| **Interop & self-host reach** *(v3.0)* | Nine workstreams (WS-A…I): ecosystem tool bridge, headless Agent-SDK runner, governed loop substrate, self-observability, tenant hardening, a 0→100 proof, a self-hosted control plane, and the **A2A outbound** callable-agent surface. All flag-gated OFF. |
| **Governed budget rails** *(v3.0)* | Per-run / per-day / monthly SI-5 spend ceilings evaluated on real, month-to-date-windowed cost, with an idle+alert sanctioned-pause on a trip — never a silent stall. |
| **Durable runs** *(v2.0)* | Every wave gets a run-id, wave checkpoints, and a committed hash-chained attestation — crash-safe resume/fork with zero lost or duplicated tickets (kill-drill verified). |
| **Observability & cost** *(v2.0)* | OTel-shaped span events per dispatch, a per-run cost ledger, and committed, git-auditable KPI evidence — the T1–T7 gates read from real spans, never vibes. |
| **HEARTBEAT tempo** | An autonomous scheduler substrate (ADR-0027 safety rails). Ships **OFF / shadow**; going live is a Founder-only, evidence-gated act (`scripts/check_heartbeat_readiness.py`, [`docs/runbooks/heartbeat-go-live.md`](docs/runbooks/heartbeat-go-live.md)). |
| **Golden-eval competence** | All **32 roles** carry ≥3 deterministic golden tasks scored ≥0.80 at their assigned tier (`scripts/agent_eval.py`), guarded by an anti-gaming probe. |
| **ArcRift memory** | Long-term memory lives in an MCP server. Each unit of work recalls context at the start and stores a decision at the end, scoped strictly per project. |

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

**First time here?** [`docs/BOSHLANGICH-QOLLANMA.md`](docs/BOSHLANGICH-QOLLANMA.md) walks the same
path one step at a time, in Uzbek, assuming no prior knowledge — what each command prints, how to
read it, and what to do when it fails.

The engine's runtime is **stdlib-only except PyYAML** — a fresh clone boots with nothing installed.
For the optional Python package surface (the reusable `daslab_sdk`, the control plane), see
[Packages](#packages).

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

## Interop & self-host reach (MUSTAQIL, v3.0)

MUSTAQIL is nine workstreams that give the org reach beyond its own repo. **Each is feature-flagged in
[`config/features.yaml`](config/features.yaml) and ships default-OFF** — with a flag off, dispatch and
board behavior are byte-identical to pre-merge (SC-005). Turning any flag on is a QONUN-5 Founder-only act.

| WS | Name | What it adds | Contract | Flag (default OFF) |
| --- | --- | --- | --- | --- |
| **A** | REACH | Ecosystem tool / MCP bridge — the org can *call* external tools | ADR-0033 | `ws_a_tool_bridge` |
| **B** | RUNNER | Headless **Agent-SDK runner** ([`daslab_sdk`](daslab_sdk/)) — dispatch a ticket/wave without a live session | ADR-0034 | `ws_b_agent_sdk_runner` |
| **C** | LOOP | Governed per-task loop/execution substrate + sandbox isolation | ADR-0035 | `ws_c_langgraph_loop` |
| **D** | LENS | Self-observability — OTel-shaped spans, redaction-scrubbed | ADR-0036 | `ws_d_langfuse_lens` |
| **E** | TENANT | Internal self-host hardening (in-tenant boundary, TN-1) | ADR-0038 | `ws_e_tenant_hardening` |
| **F** | TEMPO | HEARTBEAT go-live — the autonomous tempo loop | ADR-0027 | `heartbeat_enabled` |
| **G** | PROOF | Deliver one scoped project 0→100 with committed, attested evidence | ADR-0037 | `ws_g_proof` |
| **H** | CONTROL | Self-hosted web control plane ([`tools/control_plane/`](tools/control_plane/), FastAPI) | ADR-0039 | `ws_h_control_plane` |
| **I** | A2A OUTBOUND | DasLab as a **callable governed agent** for another agent system | ADR-0040 | `a2a_outbound` |

**A2A OUTBOUND (WS-I)** is the newest surface: an external agent system submits a *goal proposal*
(board intake) — **never** a gate approval; approvals stay Founder-only (QONUN-5). Publishing the
endpoint is a Founder act, the surface is in-tenant only (TN-1), and it reuses the existing ADR-0009
admission + ADR-0012 redaction edge — no second admission path. See
[`docs/design/a2a-outbound.md`](docs/design/a2a-outbound.md) and the endpoint in
[`tools/a2a/`](tools/a2a/).

### Honest scope

Everything autonomy-bearing ships **OFF**. `a2a_outbound`, `heartbeat_enabled`, and every `ws_*` flag
default to false; no endpoint is published and no autonomous tick runs until a Founder flips the flag.
HEARTBEAT go-live is additionally **evidence-gated** on a ≥3-day clean shadow window of *counted* waves
(`scripts/check_heartbeat_readiness.py` → NOT READY at 0/3; `scripts/heartbeat_go_no_go.py` → NO-GO).
The FR-004 monthly credit ceiling is declared and enforceable (`config/budgets.yaml`,
`active_plan` × `plan_credit_usd`), month-to-date windowed so it cannot latch. No KPI number is
fabricated: unmeasured is reported as unmeasured.

---

## Governance

DasLab is run as a governed company, not a free-for-all.

- **Company charter** — [`governance/charter.md`](governance/charter.md) defines the mission, the
  binding values (customer outcome first; decisions in writing; smallest reversible step; no silent
  blockers; authority local / accountability upstream; budget is a constraint; security and compliance
  non-negotiable), the governance structure, and the authority matrix.
- **Binding board policies** — [`governance/policies/`](governance/policies/) holds
  [`raci.md`](governance/policies/raci.md) (per-decision RACI, exactly one Accountable per row),
  [`model-allocation.md`](governance/policies/model-allocation.md),
  [`ai-agent-lifecycle.md`](governance/policies/ai-agent-lifecycle.md),
  [`quality-bar.md`](governance/policies/quality-bar.md), and
  [`memory-modes.md`](governance/policies/memory-modes.md).
- **Cadence** — per-wave reports, weekly board minutes, monthly strategic review, quarterly charter review.

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

```bash
python3 scripts/diagnostics.py        # prints SCORE = 100/100 on a clean tree

# Full local gate:
ruff check scripts tests && python3 -m pytest -q && python3 scripts/diagnostics.py
```

### CI-enforced validators

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pull requests and pushes to `main`. It
lints with `ruff`, `py_compile`s every tracked Python file, runs the `pytest` suites, runs a
`gitleaks` secret scan, boots a fresh clone from another path (portability), and runs a long chain of
enforcement validators, including:

- `board_lint.py` — ticket schema, status enum, routing, no orphans, no self-review
- `check_agents_sync.py` — fails if the agent shims or `ROUTING.md` drift from the overlays and model table
- `check_gates.py` — AADL gate order
- `check_never_auto_approve.py` — a Founder-only decision can never be auto-approved
- `check_wave_reconciliation.py` / `check_attestation.py` — the committed run-attestation chain reconciles
- `check_no_hardcoded_paths.py` / `check_no_dead_runtime.py` — portability; keep the engine server-free
- `check_project_isolation.py` — no project-specific name leaks into engine files
- `check_quickstart.py` — the README Quickstart commands exit 0 on a fresh clone
- `check_links.py` — broken relative links

---

## Packages

DasLab is primarily a **clone-and-run** system: a fresh `git clone` boots the whole org and work is
driven in-place through the `/daslab-*` skills. Its Python surface is deliberately split into a small,
well-defined set of first-party packages ([`pyproject.toml`](pyproject.toml)) and a large flat layer of
in-place CLI/validator modules.

### Distributable packages

Declared explicitly under `[tool.setuptools] packages` — these are the git-tracked, importable
first-party packages (each with an `__init__.py`). Vendored third-party deps, the test suite, and the
flat `scripts/*.py` modules are deliberately excluded.

| Package | What it is |
| --- | --- |
| [`daslab_sdk`](daslab_sdk/) | **The one clean, reusable library.** WS-B headless Agent-SDK runner (ADR-0034): `dispatch_ticket` / `dispatch_wave` over the Claude Agent SDK `query()`, feature-flagged and inert until on. |
| [`governance/guardrails`](governance/guardrails/) | Per-role input/output guardrail tripwires (retry-with-feedback, escalation). |
| [`scripts/a2a_intake`](scripts/a2a_intake/) | A2A goal-proposal → board intake (WS-I), with control-char/injection guards. |
| [`scripts/cache`](scripts/cache/) | Result cache + prompt-cache-prefix machinery. |
| [`scripts/cost`](scripts/cost/) | Per-run cost ledger (windowed span aggregation, SI-5 rails). |
| [`scripts/dgox`](scripts/dgox/) | DGO-X shadow event store + control-plane primitives. |
| [`tools/a2a`](tools/a2a/) | A2A outbound endpoint + publish surface (WS-I). |
| [`tools/model_gateway`](tools/model_gateway/) | Model-allocation gateway. |
| [`tools/observability`](tools/observability/) | OTel-shaped span emission (WS-D). |
| [`tools/sandbox`](tools/sandbox/) | Per-task sandbox execution adapter (WS-C). |

Install (editable) plus optional extras:

```bash
pip install -e .                     # daslab + the packages above (runtime dep: PyYAML)
pip install -e ".[control-plane]"    # + FastAPI/uvicorn/httpx/pydantic for tools/control_plane (WS-H)
pip install -e ".[dev]"              # + pytest/ruff/black (contributor toolchain)
```

The version is single-sourced from the top-level [`VERSION`](VERSION) file (`[tool.setuptools.dynamic]`).
The reproducible, hash-pinned lockfiles are [`requirements.txt`](requirements.txt) (runtime) and
[`requirements-dev.txt`](requirements-dev.txt) (toolchain), compiled from the `*.in` sources.

### In-place modules (not packaged)

- **`scripts/*.py`** — ~110 flat CLI/validator/generator modules (`diagnostics.py`, `board_lint.py`,
  `gen_subagents.py`, `loop_controller.py`, `heartbeat_go_no_go.py`, …) run as
  `python3 scripts/<name>.py` and imported through `sys.path`, not as a package.
- **`tools/{browser,control_plane,guardrails,mcp_bridges}`** — app / namespace surfaces without a
  package `__init__.py` (the control plane vendors its own FastAPI stack under `.vendor/`).
- **`tests/`** — the pytest suite; not shipped.
- **`projects/`** — per-project workspaces, gitignored (each manages its own git).

---

## Repository layout

| Path | What lives there |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md) | Umbrella spec + Claude Code instructions and the QONUN laws (binding). |
| [`CHANGELOG.md`](CHANGELOG.md) / [`VERSION`](VERSION) | Release history (Keep a Changelog) and the current SemVer string. |
| [`pyproject.toml`](pyproject.toml) | Project metadata, the distributable-package list, and ruff/black/pytest config. |
| [`governance/`](governance/) | Company charter, binding board policies, the `guardrails/` package, board minutes. |
| `engineering/` `product/` `design/` `marketing/` `operations/` | Department charters (`<dept>/CLAUDE.md`), role overlays, and department artifacts. |
| [`board/`](board/) | File-based ticket store (`tickets/DAS-*.md`) and the `ROUTING.md` reviewer table. |
| [`daslab_sdk/`](daslab_sdk/) | The headless Agent-SDK runner package (WS-B). |
| [`scripts/`](scripts/) | Load-bearing tooling — flat CLI/validators plus the `dgox/` `cost/` `cache/` `a2a_intake/` packages. |
| [`tools/`](tools/) | Interop/self-host surfaces: `a2a/`, `control_plane/`, `observability/`, `sandbox/`, `model_gateway/`, `mcp_bridges/`, `browser/`, `guardrails/`. |
| [`config/`](config/) | Runtime config — feature flags, budgets, RBAC, tenant boundary, risk taxonomy, thresholds. |
| [`.claude/agents/`](.claude/agents/) / [`.claude/skills/`](.claude/skills/) | The 32 generated subagent shims and the orchestration skills (do not hand-edit the shims). |
| [`skills/`](skills/) | Operator and role skills (`daslab-canary`, `daslab-investigate`, `daslab-learn`, …). |
| [`docs/`](docs/) | Architecture, usage, operator guides, runbooks, specs, and ADRs in [`docs/adr/`](docs/adr/). |
| [`metrics/`](metrics/) | The metric registry plus committed KPI evidence and wave attestations. |
| [`tests/`](tests/) | pytest suites for the validators, the SDK, DGO-X, and the budget/evidence rails. |
| `projects/` | Per-project workspaces (gitignored; each manages its own git). |

---

## Precedence

When documents disagree, lower levels may **add** constraints but never relax a higher one:

1. [`governance/charter.md`](governance/charter.md) — the company charter
2. board-issued policy in [`governance/`](governance/) — RACI, the AADL lifecycle, model allocation, security/compliance
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
   `rm -rf projects/<name>`. Platform tickets live in `board/tickets/`; project tickets never do.
2. **AI-Agent Lifecycle** — every AI-agent program follows the six-stage AADL, each stage closed by its
   gate. No production launch with GATE-5 open.
3. **Founder-Approved Goal Queue** — a new project cannot produce board tickets until the Founder is
   asked ≥10 discovery questions, the answers are enriched with sourced research into
   `projects/<slug>/APPROVED-GOAL-QUEUE.md`, and the Founder explicitly approves the queue.
4. **Model Allocation** — each agent runs on the Claude model its task complexity needs
   (opus × 10 / sonnet × 19 / haiku × 3); the model is passed explicitly on every dispatch.
5. **Persistent Memory (ArcRift)** — recall context at the start of work, store the decision at the end,
   scoped strictly per project; mixing one project's facts into another is forbidden.

A cross-cutting law — **never-auto-approve** — guarantees that a Founder-only decision (a gate approval,
publishing an endpoint, flipping `heartbeat_enabled`) can never be auto-answered by an agent
(`scripts/check_never_auto_approve.py`, `config/risk_taxonomy.yaml`).

---

## ArcRift persistent memory

DasLab's long-term memory lives in **ArcRift**, a local MCP server wired in [`.mcp.json`](.mcp.json).
Context is not lost between sessions: each unit of work calls `recall_context` at the start and
`store_memory` at the end, scoped by a flat project key (`daslab`, or `daslab-<slug>`). Graph triple
extraction routes to a local Claude bridge; embeddings use a local Ollama model. ArcRift and Ollama are
**optional** for booting the engine — `scripts/doctor.py` treats them as WARN. Schema migrations are
managed with Alembic ([`alembic.ini`](alembic.ini) + [`migrations/`](migrations/)). The binding rule is
the Persistent Memory Law in [`CLAUDE.md`](CLAUDE.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), and
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

The core rule is **one issue = one branch = one PR = one worktree**. Never commit directly to `main` or
`release/*`; protected branches require an approving review and green CI before merge — and you may not
review your own PR (per [`board/ROUTING.md`](board/ROUTING.md)). Release history is tracked in
[`CHANGELOG.md`](CHANGELOG.md) ([SemVer](https://semver.org/) per [ADR 0022](docs/adr/0022-semantic-versioning-policy.md)):
release = force-push `main` + an annotated `vX.Y.Z` tag + a GitHub Release.

Currently there is no active external product: the MUSTAQIL v3.0 machinery ships built-and-OFF, and the
org stands ready to take the next Founder-approved goal queue.

---

## License

Licensed under the [Apache License 2.0](LICENSE).
