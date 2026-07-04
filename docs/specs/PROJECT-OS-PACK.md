<!--
  PROJECT-OS-PACK.md — the input-contract SPEC OF RECORD for ORGANISM WS7 GATEWAY (O7-T01).
  Decision authority: docs/adr/0030-project-os-pack.md (D-1…D-6). This spec writes that
  decision out field by field; it MUST NOT contradict the ADR. WHAT/WHY of the input
  contract — not the compiler (that is O7-T02 `scripts/gateway_compile.py`) and not the
  Stage-2 tech stack (that lives in the per-project AADL 02-design docs).
  Follows docs/specs/templates/SPEC.md (User Scenarios / FR-NNN / SC-NNN), extended with
  the manifest schema + skeleton the contract needs. Platform / org-engine doc.
-->
# SPEC — PROJECT-OS-PACK: the canonical input contract for bootstrapping an AI-agent project

- **Goal:** organism-ws7-gateway
- **Owner:** cpo (with tech-writer — O7-T01 co-owner)
- **Status:** reviewed
- **Decision of record:** [`docs/adr/0030-project-os-pack.md`](../adr/0030-project-os-pack.md) (invariants D-1…D-6)
- **AADL stage:** GATE-1 Planning (ORGANISM WS7 GATEWAY)

## 1 — What a PROJECT-OS-PACK is (and is not)

A **PROJECT-OS-PACK** is the single, normative, machine-readable **input contract** a
Founder hands DasLab to turn a product idea into a delivered product (0→100). It is the
one gate every new project enters through, closing gap **G9 — "no intake compiler"**. The
WS7 compiler (`scripts/gateway_compile.py`, O7-T02) reads a pack, validates it, checks the
Founder gates, and compiles **stage-gated story tickets** into the project's own board —
so the pack must be **one unambiguous shape** the compiler can validate and, when broken,
**reject with actionable errors**.

A pack is **NOT** a compiler, a design doc, or a ticket format. It carries the *intent* and
the *approvals*; the technical decisions are still made downstream in AADL Stage-2 Design.

**A pack is four parts, rooted at `projects/<name>/`** (obeying the QONUN Project Placement
Law — everything a project owns lives inside its one folder):

1. the **`projects/<name>/PROJECT-OS.yaml` manifest** — the single machine-readable
   descriptor (§3);
2. the **canonical `docs/01-planning…06-maintenance` lifecycle skeleton** from AADL §2 (§4);
3. the **Founder discovery answers** — ≥10 Q&A or an explicit waiver (§5);
4. the **`projects/<name>/APPROVED-GOAL-QUEUE.md`** — the Founder-approved, research-backed
   work queue (§6).

Its governing law is its **Constitution** = QONUN laws + project-local constraints, where
project-local may only **tighten**, never relax, org law (§7).

## 2 — User Scenarios

> Given / When / Then, ordered by priority (P1 first). Behavioural, not technical.

- **P1 —** Given a Founder with a new AI-agent product idea, when they hand DasLab a
  well-formed PROJECT-OS-PACK (manifest + canonical skeleton + ≥10 discovery Q&A + a
  Founder-approved goal queue), then the org has exactly one validatable input from which
  the gateway can compile stage-gated story tickets — with no hand-written tickets.
- **P2 —** Given a pack missing a required manifest field, or using a non-canonical doc-tree
  name, or with an open discovery gate, or an unapproved goal queue, when the gateway reads
  it, then the pack is **rejected with an actionable error** naming the exact defect — no
  tickets are compiled.
- **P3 —** Given a pack whose project-local `constraints` attempt to **relax** an org law
  (waive a QONUN rule, skip an AADL gate, loosen a security policy, self-grant
  never-auto-approve), when the gateway validates the Constitution, then the pack is
  **invalid** — org law wins on conflict and the stricter rule applies.
- **P4 —** Given a second, different well-formed pack (a different product, stack, and
  budget), when the same gateway reads it, then it passes with **no gateway code changes**
  (the shape is project-agnostic — O7-T05's generality check).

## 3 — The manifest: `projects/<name>/PROJECT-OS.yaml` (D-1, D-2)

Exactly **one** manifest per pack, at the **project root** (not in `docs/`). It is the
compiler's first read: plain YAML (parseable without executing anything), declaring the
project's identity and its Stage-1 product/KPI surface.

### 3.1 — Closed field set

The manifest carries **exactly** these top-level keys. The set is **closed**: an unknown
key is a lint **warning** (surfaced, never silently dropped); a missing **required** key is
an actionable **rejection**.

| Key | Required | Type | Meaning |
|---|---|---|---|
| `name` | yes | string (kebab-case slug) | The project slug. MUST equal the `<name>` folder segment (`projects/<name>/`). Unique across the org. |
| `mission` | yes | string (one paragraph) | What the product is and for whom — the Stage-1 "business need" seed. |
| `constraints` | yes | list of strings | Project-local constraints (compliance regime, data-residency, latency/cost ceilings, forbidden deps, review regime). Each may only **tighten** org law (§7). May be an empty list `[]` if the project adds nothing beyond org baseline, but the key MUST be present. |
| `stack` | yes | mapping | Intended technology surface — indicative at intake, not binding. Suggested sub-keys: `languages`, `frameworks`, `model_providers`, `infra`. The binding technical decisions are made in AADL Stage-2 Design; this is a *seed*. |
| `budget` | yes | mapping | The resource envelope — the Stage-1 "resources" seed. Suggested sub-keys: `tokens` (monthly token/compute ceiling), `money` (currency + amount), `worst_case_loop` (worst-case loop-cost model). The AADL GATE-1 "token + infra budget approved by finance-analyst" checkbox reads this. |
| `success_metrics` | yes | list of mappings | The measurable business KPI(s) the project is judged against — the Stage-1 "measurable business KPI defined" GATE-1 checkbox. Each entry: `metric` (name, e.g. CPR/AHT/containment-rate), `target` (threshold), `baseline` (optional starting point). This is the KPI-definition surface that makes GATE-1 a CPO-accountable call. |

**Extending the set** is a spec revision + a new/amended ADR (D-2) — never an ad-hoc
per-project key.

### 3.2 — Illustrative manifest (non-normative example)

```yaml
# projects/acme-helpdesk/PROJECT-OS.yaml
name: acme-helpdesk
mission: >
  An AI support agent that resolves tier-1 billing questions for Acme's SaaS
  customers in-chat, deflecting tickets from the human queue while never
  fabricating account state.
constraints:
  - "PII: mask account numbers before any model call (tightens org data-handling baseline)"
  - "Data residency: EU-only inference (org allows global; project restricts)"
  - "No dependency on the 5 banned donor libs (org import-ban; restated for clarity)"
  - "p95 response latency <= 3s"
stack:
  languages: [python]
  frameworks: [claude-agent-sdk]
  model_providers: [anthropic]
  infra: [docker, dokploy]
budget:
  tokens: "15M input / 5M output per month"
  money: "USD 1200 / month ceiling"
  worst_case_loop: "cap 8 tool-iterations per transaction; kill-switch on runaway"
success_metrics:
  - metric: "tier-1 ticket containment rate"
    target: ">= 55%"
    baseline: "0% (net-new)"
  - metric: "hallucinated-account-state incidents"
    target: "0 per 10k transactions"
```

> The example is **illustrative only**. The normative contract is §3.1's field table +
> D-1/D-2; the values above are a plausible instance, not a required template.

## 4 — The lifecycle skeleton: canonical AADL §2, NOT qaqnuz's names (D-3)

The pack's documentation tree is the **canonical** six-stage skeleton from
`governance/policies/ai-agent-lifecycle.md` §2 — **verbatim folder names**, one folder per
AADL lifecycle stage, in order:

```
projects/<name>/
├── README.md                  # charter + stage board (gate status log)
├── PROJECT-OS.yaml            # the manifest (§3)
├── APPROVED-GOAL-QUEUE.md     # Founder-approved, research-backed work queue (§6)
└── docs/
    ├── 01-planning/           # business-needs, objectives, resources, risk-ethics-review
    ├── 02-design/             # framework-decision, model-card, grounding-architecture, guardrails-spec
    ├── 03-development/        # architecture-topography, tool-contracts, onboarding
    ├── 04-testing/            # eval-report, integration-tests, ux-test-notes, red-team-report
    ├── 05-deployment/         # launch-runbook, guardrail-verification, observability, compliance-validation
    └── 06-maintenance/        # kpi-monitor, optimization-log, feedback-loop
```

- The six folder names are **exactly** `01-planning`, `02-design`, `03-development`,
  `04-testing`, `05-deployment`, `06-maintenance`. A GATEWAY scaffolder emits **these**
  names; each stage's mandatory artifacts are the ones AADL §3 lists, and each folder maps
  1:1 to its AADL gate (GATE-1…GATE-6).
- **qaqnuz's layout is explicitly NOT the contract.** qaqnuz uses divergent, human-authored
  names — `00-overview`, `01-intake`, `02-prd`, `03-rfc`, `04-program`, `05-delivery`,
  `06-release`, `07-operations`, `08-decisions`, `09-retro`, `10-diagnostics`, … A **new
  pack MUST use the canonical names**. A pre-existing divergent project reconciles via the
  AADL §2 `LIFECYCLE-MAP.md` escape (a migration aid mapping its folders to the six stages)
  — that escape is **not** a licence for a new pack to drift.
- Because the tree is the **same shape for every project**, the gateway can walk it,
  placeholder-lint it, and map each stage folder to its gate **without per-project
  configuration** — which is exactly what the O7-T05 generality check ("second sample pack
  passes with no gateway code changes") depends on.

## 5 — Founder discovery answers (D-4)

The pack carries the **Founder Discovery Gate** result, per QONUN-3 + AADL §5:

- **At least 10 Founder questions and their answers**, OR an explicit Founder
  decline/waiver.
- The **sourced global research** the law requires: market, competitors,
  regulatory/compliance, technical architecture, pricing/unit-economics, SEO/channel, and
  risks — with sources.
- These live in the project folder, canonically under `docs/01-planning/` (e.g.
  `docs/01-planning/discovery.md` + the research conclusion). The discovery answers seed
  the Stage-1 planning artifacts (business needs, objectives, resources, risk-ethics
  review) that GATE-1 checks.

The discovery gate is a **precondition of a valid pack**: the compiler checks it (≥10 Q&A
or waiver) and, if it is **open**, **generates the questions** rather than proceeding
(O7-T02). A pack with an open discovery gate is not compilable.

## 6 — The approved goal queue: `APPROVED-GOAL-QUEUE.md` (D-5)

The pack carries **`projects/<name>/APPROVED-GOAL-QUEUE.md`** — the Founder-approved,
research-backed work queue (QONUN-3). The queue is only actionable once the Founder has
given the **explicit approval signal**:

- `APPROVED:` / `TASDIQLANDI:` in the queue, i.e. a queue item at `status: founder_approved`
  or later.
- Until then, **no board tickets are compiled**. The existing
  `scripts/check_approved_goal_queue.py` is the gate the compiler wires; `/daslab-plan`
  decomposes only `founder_approved` items, one goal at a time, and never invents work.
- The compiled story tickets are written to the **project's own board**
  (`projects/<name>/board-tickets/`), **never** the org `board/tickets/` (Project Placement
  Law; `board_lint` R9 forbids a `project:` field on an org-board ticket). Each compiled
  ticket is self-contained: embedded context, acceptance criteria, `produces`/`consumes`
  contracts, its AADL stage tag, and its gate reference (O7-T02).

This keeps the QONUN Founder gate intact: the pack format *names* the approved queue as a
required part, and the compiler refuses to emit story tickets from an unapproved queue.

## 7 — The Constitution: QONUN + project-local, never relaxing org law (D-6)

The pack's **Constitution** — the full body of rules binding the project — is the **union**
of:

- the org's **QONUN laws** (Project Placement, AI-Agent Lifecycle, Founder-Approved Goal
  Queue, Model Allocation, Persistent Memory) and all higher-precedence org policy
  (`governance/charter.md`; board-issued `governance/` policy including the AADL; the dept
  charters); **plus**
- the project's **project-local constraints** — the manifest `constraints` field (§3.1) and
  the project's own `docs/01-planning/` risk-ethics review.

**Precedence rule (binding):** a project-local constraint may only **add restrictions** — it
may **tighten** org law, **never relax** it. This is the precedence law: root `AGENTS.md`
§2 ("lower-precedence may add constraints but never relax them set higher up"), restated for
projects by the AADL scope note ("projects may add constraints, never relax them"). Where a
project-local constraint and org law disagree, **org law wins** and the **stricter** of the
two applies.

**Allowed (tightenings):** forbid a dependency the org allows; demand stricter
data-residency, PII-masking, or review than org baseline; set a tighter budget/latency
ceiling; require an extra sign-off.

**Forbidden (relaxations) — make the pack invalid:** waive or weaken a QONUN law; skip or
soften an AADL gate; relax a security/compliance policy; self-grant a never-auto-approve
exception; grant the project any exception to a higher-precedence rule. A pack that attempts
any of these is **rejected with an actionable error** — a project's Constitution is a
tightening lens over org law, never a loophole.

## 8 — Functional Requirements

> One testable requirement per line. `FR-NNN` ids, unique. The WS7 compiler (O7-T02) and
> validators bind to these.

- **FR-001** — A pack MUST contain exactly one manifest at `projects/<name>/PROJECT-OS.yaml`
  (project root), parseable as YAML. (D-1)
- **FR-002** — The manifest MUST declare all required keys `name`, `mission`, `constraints`,
  `stack`, `budget`, `success_metrics`; a missing required key MUST be rejected with an
  actionable error naming the key. (D-2)
- **FR-003** — The manifest's `name` MUST equal the `<name>` folder segment of the pack
  root; a mismatch MUST be rejected. (D-1)
- **FR-004** — An unknown top-level manifest key MUST surface as a lint warning (not a
  silent drop, not a hard reject). (D-2)
- **FR-005** — The pack's doc tree MUST use the canonical AADL §2 folder names
  `docs/01-planning` … `docs/06-maintenance` (exact, ordered); a doc tree using
  non-canonical names (e.g. qaqnuz's `01-intake`/`02-prd`/`03-rfc`/…) MUST be rejected for a
  new pack. (D-3)
- **FR-006** — The pack MUST carry the Founder discovery answers (≥10 Q&A or an explicit
  waiver); an open discovery gate MUST block compilation (the compiler generates the missing
  questions instead of proceeding). (D-4)
- **FR-007** — The pack MUST carry `projects/<name>/APPROVED-GOAL-QUEUE.md`, and the compiler
  MUST verify the Founder approval signal (`APPROVED:`/`TASDIQLANDI:`, i.e. `founder_approved`
  or later) via `scripts/check_approved_goal_queue.py` before compiling any story ticket. (D-5)
- **FR-008** — Compiled story tickets MUST be written to the project's own board
  (`projects/<name>/board-tickets/`), never to the org `board/tickets/`, and MUST carry no
  `project:`-forbidding violation (they live on the project board, so `board_lint` R9 does
  not apply to them). (D-5, QONUN Project Placement)
- **FR-009** — The compiler MUST reject a pack whose project-local `constraints` relax org
  law (waive a QONUN rule, skip/soften an AADL gate, loosen a security/compliance policy,
  self-grant never-auto-approve), with an actionable error; on any project-local↔org-law
  conflict the stricter (org) rule applies. (D-6)
- **FR-010** — The contract MUST be project-agnostic: a second, different well-formed pack
  MUST validate and compile with no gateway code changes. (D-3, O7-T05)

## 9 — Success Criteria

> Measurable. `SC-NNN` ids, unique.

- **SC-001** — A well-formed sample pack (`evals/e2e/sample-pack/`, O7-T04) validates and
  compiles into ≥25 coherent stage-gated story tickets with **zero** hand-written tickets.
- **SC-002** — For each of FR-002/003/005/006/007/009, a deliberately-broken pack fixture is
  **rejected with an actionable error** that names the exact defect (no silent pass, no
  crash).
- **SC-003** — A second, different sample pack (O7-T05) passes with **no** changes to
  `scripts/gateway_compile.py` — proving the shape is project-agnostic.
- **SC-004** — No pack can compile a story ticket while the discovery gate is open (FR-006)
  or the goal queue is unapproved (FR-007) — verified by fixture.
- **SC-005** — A pack that relaxes an org law (FR-009) never validates; the equivalent pack
  that *tightens* the same rule does validate — proving the Constitution is a tightening
  lens, org law winning on conflict.

## 10 — Out of scope (delegated downstream)

- The compiler itself — `scripts/gateway_compile.py` intake/validation/compilation logic is
  **O7-T02** (Development), built against this contract.
- Stage-gated delivery through the AADL gates (interrupt-cards, GATE-5-open ⇒ no prod
  deploy) is **O7-T03**.
- The E2E + generality sample packs and their run logs are **O7-T04 / O7-T05** (Testing).
- The binding technology decisions (framework, model card, grounding, guardrails) are the
  project's own **AADL Stage-2 Design** docs — the manifest `stack` is only an intake seed.

---

**Traceability.** This spec realizes ADR-0030's invariants D-1…D-6. FR-001…FR-010 and
SC-001…SC-005 are the testable surface the WS7 implementation tickets (O7-T02…O7-T05) bind
to; a compiled story ticket may reference them via `implements:` / `spec:` per ADR-0015.
