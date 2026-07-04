# Policy: AI Agent Development Lifecycle (AADL)

> **Status:** Binding board policy — precedence level 2 (root `AGENTS.md` §2).
> **Scope:** Universal. Every DasLab project that ships agentic AI — any
> platform, any channel, any client. This is the enterprise baseline; projects
> may add constraints, never relax them.
> **Source:** 6-Stage AI Agent Development Lifecycle, aligned with NIST AI RMF
> 1.0, ISO/IEC 42001, OWASP Top 10 for LLMs.
> **Adopted:** 2026-06-12.

## 0 — Law

Every AI-agent project moves through **six stages, in order**:

```
Planning → Design → Development → Testing → Deployment → Maintenance
```

A stage is exited only when its **gate checklist** below is fully checked and
logged in the project's `README.md` stage board. Skipping a stage, or starting
work whose predecessor gate is open, is forbidden. `/daslab-plan` decomposes
AI-agent goals into stage-gated epics; `/daslab-cycle` does not dispatch
tickets ahead of their gate. Non-agent software follows the org methodology
(root `AGENTS.md` §3) without the AI-specific artifacts.

## 1 — Stage ↔ DasLab mapping

| # | Stage | Gate | Accountable | Responsible | Consulted |
|---|-------|------|-------------|-------------|-----------|
| 1 | Planning | GATE-1 | cpo | senior-pm | finance-analyst, legal-analyst |
| 2 | Design | GATE-2 | cto | backend-em | security-lead |
| 3 | Development | GATE-3 | cto | backend-em / frontend-em | tech-writer |
| 4 | Testing | GATE-4 | qa-lead | qa-eng | security-eng (red team) |
| 5 | Deployment | GATE-5 | sre-lead | sre-eng | security-lead, legal-analyst |
| 6 | Maintenance | GATE-6 | coo | product-analyst | support-lead |

## 2 — Canonical project skeleton

Created at bootstrap, per the project placement law (one project = one folder):

```
projects/<name>/
├── README.md                  # charter + stage board (gate status log)
├── APPROVED-GOAL-QUEUE.md     # Founder-approved, research-backed work queue
├── docs/
│   ├── 01-planning/           # business-needs, objectives, resources, risk-ethics-review
│   ├── 02-design/             # framework-decision, model-card, grounding-architecture, guardrails-spec
│   ├── 03-development/        # architecture-topography, tool-contracts, onboarding
│   ├── 04-testing/            # eval-report, integration-tests, ux-test-notes, red-team-report
│   ├── 05-deployment/         # launch-runbook, guardrail-verification, observability, compliance-validation
│   └── 06-maintenance/        # kpi-monitor, optimization-log, feedback-loop
└── <code>                     # the codebase (or repo-skeleton/)
```

Existing projects with a different layout add a `LIFECYCLE-MAP.md` mapping
their folders to the six stages and adopt the gates from their next stage on.

## 3 — Stages: mandatory artifacts and gates

### Stage 1 — Planning

Artifacts in `docs/01-planning/`: business needs (core bottleneck, KPIs such
as CPR/AHT, data-feasibility), agent objectives (in/out scope, persona +
autonomy level, task decomposition), resources (token/compute budget with
worst-case loop modeling, infrastructure, team), risk + ethics review (NIST
AI RMF mapping, bias profile, PII/PHI masking plan).

**GATE-1:** ☐ measurable business KPI defined ☐ scope boundaries explicit
☐ token + infra budget approved by finance-analyst ☐ risk-ethics review
signed by legal-analyst ☐ data feasibility confirmed.

### Stage 2 — Design

Artifacts in `docs/02-design/`: framework decision (orchestrator choice with
rationale — LangGraph / CrewAI / AutoGen / Claude Agent SDK / custom), model
card (tier-1 frontier vs tier-2 efficiency vs open-source per task, cost +
latency targets, vendor-abstraction plan), grounding architecture (RAG
pipeline, hybrid search, reranking, semantic caching), guardrails spec
(input: injection/jailbreak/off-topic filters; output: schema validation,
hallucination + leak checks).

**GATE-2:** ☐ framework ADR merged ☐ model card with cost/latency targets
☐ grounding architecture reviewed ☐ guardrails spec covers OWASP LLM Top 10
☐ security-lead sign-off.

### Stage 3 — Development

Artifacts in `docs/03-development/`: architecture topography (routing graph,
state transitions, dependencies), tool contracts (JSON schemas, parameter
limits, prompt template versions), onboarding (containerized dev env —
`Dockerfile` / `docker-compose.yml`). Code follows engineering law: reasoning
loop (ReAct / state machine) explicit, durable state store, async I/O,
unified model gateway (no vendor lock-in), fine-tuning only for form/tone
(LoRA/QLoRA) — never for knowledge injection (that is RAG's job).

**GATE-3:** ☐ topography doc matches code ☐ all tool contracts documented
☐ dev env reproducible in one command ☐ model layer hot-swappable
☐ docs updated in the same change as implementation.

### Stage 4 — Testing

Artifacts in `docs/04-testing/`: eval report (LLM-as-judge rubrics + RAGAS:
faithfulness, answer relevance, context recall — with thresholds), integration
tests (mocked nondeterminism, state-traversal audits), UX tests (latency
perception, streaming, correction/redirect UX), red-team report (prompt
injection, jailbreaks, role-switch, degraded-retrieval behavior — agent must
say "I don't know" rather than hallucinate).

**GATE-4:** ☐ eval suite automated in CI with thresholds ☐ integration tests
green ☐ red-team findings fixed or risk-accepted by security-lead ☐ zero-result
and conflicting-context behavior verified ☐ qa-lead sign-off.

### Stage 5 — Deployment

Artifacts in `docs/05-deployment/`: launch runbook (containerized,
canary/blue-green), guardrail verification (inline enforcement live, static
fallbacks on timeout/safety flags), observability (full traces per
transaction: prompts, tool params, token cost, latency per node; runaway-loop
alerts), compliance validation (tamper-proof trace retention, automated
secret/PII leak scanning).

**GATE-5:** ☐ guardrails verified live in production path ☐ traces + cost
per transaction visible ☐ loop-anomaly kill-switch armed ☐ fallback messages
tested ☐ compliance log retention confirmed ☐ release checklist done. **No
production launch with GATE-5 open.**

### Stage 6 — Maintenance

Artifacts in `docs/06-maintenance/`: KPI monitor (goal-drift detection, daily
token spend vs business value), optimization log (prompt compression, model
cascading — light model first, escalate on failure), feedback loop (explicit
thumbs up/down capture, implicit correction tracing, labeled failures routed
back into the eval set).

**GATE-6 (recurring, reviewed at org monthly cadence):** ☐ KPI vs Stage-1
baseline reported ☐ cost/value ratio positive or escalated ☐ feedback entering
eval set ☐ retro written per incident.

The Maintenance stage **schedules recurring health/eval runs** —
`scripts/stage_gate.py:maintenance_schedule()` declares them as data (never an
installer): the WS4 heartbeat tick (`scripts/loop_controller.py --tick`, gated by
`board/schedule.yaml` + the `heartbeat_enabled` flag) and the WS6 golden-eval
harness (`scripts/agent_eval.py`), plus ArcRift memory hygiene. The cadence lives
in the Founder-owned OS scheduler entry (ADR-0027 SI-1); every run is
never-auto-approve (a tier promotion or gate re-open still waits for a human).

## 4 — Standards alignment

| Framework | Where satisfied |
|---|---|
| NIST AI RMF 1.0 | Stage 1 risk-ethics review, Stage 2 guardrails, Stage 5 observability |
| ISO/IEC 42001 | Stage 3 documentation, Stage 4 evals, Stage 5 compliance validation, gate logging |
| OWASP LLM Top 10 | Stage 2 guardrails spec, Stage 3 tool-contract parameter limits, Stage 4 red team |

## 5 — Enforcement

- `/daslab-plan`: a new AI-agent project first passes the Founder Discovery
  Gate: at least 10 Founder questions, current global research with sources,
  `projects/<name>/APPROVED-GOAL-QUEUE.md`, and explicit Founder approval. Only
  `founder_approved` queue items may be decomposed.
- Approved AI-agent queue items are decomposed into **one epic per stage** (six),
  epic acceptance criteria = the stage's gate checklist; child tickets carry the
  stage epic as `parent`.
- `/daslab-cycle`: never dispatches a ticket whose stage-predecessor epic is
  not `done`. When the board drains, it may refill only from a
  `founder_approved` queue item; it must not invent work.
- Board: a Stage-5 release ticket cannot reach `in_review` while GATE-4 is open.
- Bootstrap: creating `projects/<name>/` starts with the skeleton in §2 and a
  stage board in `README.md`.
- This policy binds all departments; dept overlays may tighten, never loosen.

### 5.1 — Machine enforcement (P22 / stage-gated delivery)

The gate order above is **machine-enforced end-to-end**, not a convention:

- `scripts/stage_gate.py` is the single source of truth for the gate decision. It
  keys off the `stage: GATE-N` frontmatter `gateway_compile.py` stamps on every
  story ticket plus the ticket's `goal`. A stage-N ticket may not **advance**
  (`in_progress`/`in_review`/`done`) while the same goal's GATE-(N-1) is open; a
  `todo`/`backlog` stage ticket is the legitimate gate-waiting state.
- `scripts/board_lint.py` R12 applies that rule to any board it lints (additive —
  a board with no `stage:` tickets lints exactly as before).
- `scripts/gateway_compile.py --gate-walk` walks a compiled project board's gates
  and **refuses to advance past an open gate**; `--emit-cards` surfaces each open
  blocking gate as a `board/interrupts/` interrupt-card (interrupt-card schema)
  for Founder sign-off — the machine never auto-answers a gate (ADR-0027 SI-7).
- **GATE-5 ⇒ no production deploy** reuses the existing `gate5_deployment`
  never-auto-approve category (`config/risk_taxonomy.yaml`): a production-deploy
  ticket must not be auto-approved and must not advance while GATE-5 (Deployment)
  is open. The deployment gate always requires an explicit human sign-off (QONUN-5).
- `/daslab-cycle` triage consults these gates and skips (counts `gate-blocked`)
  any ticket sitting behind an open gate — it never dispatches ahead of a gate.
