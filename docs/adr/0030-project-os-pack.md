# ADR 0030 — PROJECT-OS-PACK: the canonical, machine-readable input contract a Founder hands DasLab to bootstrap an AI-agent project (`projects/<name>/PROJECT-OS.yaml` manifest + canonical lifecycle skeleton + discovery answers + `APPROVED-GOAL-QUEUE.md`)

- **Status:** Accepted (**CPO — decider; AADL GATE-1 Planning artifact — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / org-engine — the "pack format" input contract for the ORGANISM GATEWAY workstream (WS7, O7-T01). A **decision doc + a companion spec of record** (`docs/specs/PROJECT-OS-PACK.md`, authored in the same change). It fixes the **shape and normativity** of a project's on-disk inputs — the one gate every new project enters through — so that the WS7 compiler (`scripts/gateway_compile.py`, O7-T02) has a single, unambiguous, validatable contract to read. It ships **no compiler and no validator**; O7-T02 builds the intake against this contract.
- **Deciders:** **CPO (accountable)** — GATE-1 Planning is CPO-accountable (AADL RACI §1; `model-allocation.md` Tier O: "GATE-1 accountable — product scope and KPI definitions"); the project input contract is a product-scope + KPI-definition call (the manifest names mission, constraints, budget, and success-metrics — the Stage-1 KPI surface). Tech-writer consulted (WS7 O7-T01 co-owner; owns the pack's authored docs surface). CTO consulted — owns `scripts/gateway_compile.py` (O7-T02) which reads this contract, and is the RACI 3.1 ADR ratifier. CEO consulted — WS7 planning owner and this ticket's author (DAS-1491/DAS-1492). Finance-analyst + legal-analyst are the AADL GATE-1 Consulted for budget + risk-ethics, which the manifest's `budget` and the pack's `01-planning/` risk-ethics review feed. No Founder gate is triggered: this is a decision doc + spec, not a policy/flag/model-table mutation.
- **Relates:** ORGANISM WS7 GATEWAY (`docs/research/ORGANISM-PROGRAM-PLAN.md` §4 WS7 table O7-T01…O7-T05 — "kills G9 (no intake compiler)", "docs-pack → stage-gated story tickets → delivered 0→100"; row 117 "`ai-agent-lifecycle.md §2` = the **canonical** `docs/01-planning…06-maintenance` skeleton a GATEWAY scaffolder must emit"; §5 ADR list). Binds to — and does **not** edit — `governance/policies/ai-agent-lifecycle.md` (the AADL: the six-stage law §0, the canonical project skeleton §2, the per-stage artifacts + gates §3 — the **source of truth** for the skeleton, NOT qaqnuz's divergent folder names), the three QONUN laws in `CLAUDE.md` (Project Placement, AI-Agent Lifecycle, Founder-Approved Goal Queue), the precedence law (root `AGENTS.md` §2), `docs/specs/templates/SPEC.md` (the spec template the companion spec follows), and `scripts/check_approved_goal_queue.py` (the existing goal-queue approval gate O7-T02 wires). Builds on ADR 0004 (project-agnostic engine — one factory, any goal), ADR 0014 (the Clarify gate / `[NEEDS CLARIFICATION]`), and ADR 0015 (the size-gated per-epic `SPEC.md` + `FR-NNN`/`SC-NNN` traceability the compiled story tickets inherit).
- **Supersedes / Amends:** nothing. This ADR **constrains by reference** the shape of a project's inputs; it mutates no code, edits no policy, and forks no generator. It is the WS7 counterpart of the pattern ADR 0026–0029 established for WS2–WS6: a decision doc that fixes a contract the workstream's implementation tickets satisfy.

> **Numbering note.** The WS7 plan text (`ORGANISM-PROGRAM-PLAN.md` §4 O7-T01, §5 ADR list) names this artifact "ADR-0029" ("Project-OS pack format & gateway compile contract"). The append-only ADR numbering rule (`docs/adr/README.md`) already assigned **0029** to *guild-model* (Accepted 2026-07-03), so the pack-format decision takes the next free number, **0030** — exactly as ADR 0029's own numbering note foreshadowed ("The plan's §5 line '0029 = Project-OS pack format' is WS7's ADR and will likewise take the next free number when authored."). Plan-text numbers are indicative; the README ledger is authoritative. (The plan's §5 also lists a separate "0030 = `interrupted` status" line — a *different* WS1 ADR; that too will take its own next free number when authored, and does not collide with this one.)

> **Precedence note.** The ticket (DAS-1492) refers to "precedence §1.5". The AADL policy has no §1.5; the binding precedence law lives in **root `AGENTS.md` §2** ("lower-precedence may add constraints but never relax them set higher up") and is restated for projects by the **AADL scope note** ("projects may add constraints, never relax them"). This ADR cites those two real sources as the precedence authority for the pack's Constitution rule (D-6); "§1.5" is read as a pointer to that precedence law, not a literal section.

> A **PROJECT-OS-PACK** is the bundle of files a Founder hands DasLab to turn a
> product idea into a delivered product. Today that bundle is **implicit and
> drifts**: qaqnuz's on-disk layout (`00-overview`, `01-intake`, `02-prd`,
> `03-rfc`, `04-program`, `05-delivery`, `06-release`, `07-operations`, …) diverges
> from the AADL's canonical `docs/01-planning…06-maintenance` six-stage skeleton, so
> a compiler has no single shape to read and every project re-invents its own
> folders. WS7's GATEWAY compiler (`gateway_compile.py`) can only exist if the
> input it consumes is **one normative, machine-readable contract**. This ADR fixes
> that contract; the companion `docs/specs/PROJECT-OS-PACK.md` writes it out field by
> field. **No behaviour changes on merge** — no compiler is authored here and no
> project layout is migrated.

## Context

WS7 GATEWAY is the workstream that closes gap **G9 — "no intake compiler"**: today
there is no single gate through which a new project enters the org, no normative
description of what a Founder must hand over, and no machine-readable manifest a
compiler can validate. The evidence of the gap is concrete:

- **The on-disk shape is implicit and already drifted.** The AADL (`ai-agent-lifecycle.md`
  §2) defines a **canonical** project skeleton — `README.md` + `APPROVED-GOAL-QUEUE.md`
  + `docs/01-planning/` … `docs/06-maintenance/`, one folder per lifecycle stage, with
  §3 naming the mandatory artifacts inside each. The one real project on disk, qaqnuz,
  uses a *different* set of names (`01-intake`, `02-prd`, `03-rfc`, `04-program`,
  `05-delivery`, `06-release`, `07-operations`, `08-decisions`, `09-retro`, …). Both
  are legitimate — the AADL even provides a `LIFECYCLE-MAP.md` escape for a divergent
  existing layout (§2) — but the *divergence itself* proves the point: **without a
  normative contract, every project's inputs are a different shape**, and a compiler
  that must read "the planning docs" cannot know where they are.
- **There is no manifest.** A Founder's intent — the project's name, mission,
  constraints, tech stack, budget, and success metrics — lives today only in prose,
  scattered across docs, unvalidatable, and impossible for a compiler to key off.
- **The approval + discovery machinery already exists but has nothing to read.** The
  Founder-Approved Goal Queue law (`CLAUDE.md` QONUN-3) and its enforcer
  (`scripts/check_approved_goal_queue.py`), the ≥10-question Founder Discovery Gate
  (AADL §5), and the `APPROVED:`/`TASDIQLANDI:` approval signal are all in place — but
  they are wired to a project shape that is assumed, not specified.

The question WS7 O7-T01 answers is therefore **not** "how do we compile a project" (that
is O7-T02's `gateway_compile.py`) — it is "**what, exactly, is the normative input a
project enters through, and how is it shaped so a compiler can validate it and refuse a
malformed pack with actionable errors**". This ADR answers that as a closed set of
decision invariants; the companion spec writes the field-level contract.

**AADL stage.** GATE-1 Planning for ORGANISM WS7. A decision doc + spec; it ships no
compiler and no validator, migrates no project, and skips no gate.

**Extend-vs-new posture (binding).** The pack contract is **NEW** (no existing ADR or
spec defines the project input contract), but it is **assembled from existing,
canonical parts, never forked from them**:

- The `docs/01-planning…06-maintenance` skeleton and the per-stage artifacts are the
  **canonical** ones from `ai-agent-lifecycle.md` §2/§3 — copied by reference, never
  renamed (explicitly **not** qaqnuz's divergent names).
- `APPROVED-GOAL-QUEUE.md`, the discovery Q&A, and the `APPROVED:`/`TASDIQLANDI:`
  approval signal are the **existing** QONUN-3 goal-queue machinery; the pack *names*
  their place in the contract, it does not re-invent the queue.
- The compiled story tickets inherit the **existing** board schema (`board/README.md`)
  and the ADR 0015 spec-traceability layer; the pack does not define a new ticket
  format.
- The ADR is a NEW file (next free number 0030) + a README index row; the spec reuses
  `docs/specs/templates/SPEC.md`. The *machinery* the contract points at is entirely
  pre-existing.

## Decision

A **PROJECT-OS-PACK** is the canonical, normative, machine-readable **input contract**
a Founder hands DasLab to bootstrap an AI-agent project. It is **one bundle of four
parts, rooted at `projects/<name>/`** (obeying the Project Placement Law):

1. a **`projects/<name>/PROJECT-OS.yaml` manifest** — the single machine-readable
   descriptor (D-1/D-2);
2. the **canonical `docs/01-planning…06-maintenance` lifecycle skeleton** from AADL §2
   (D-3);
3. the **Founder discovery answers** (≥10 Q&A or an explicit waiver) (D-4);
4. the **`projects/<name>/APPROVED-GOAL-QUEUE.md`** — the Founder-approved, research-backed
   work queue (D-5).

Its governing law — its **Constitution** — is the org's QONUN laws **plus** the
project's own local constraints, where a project-local constraint may only **tighten**,
**never relax**, org law (D-6). The following are the **binding pack-format invariants**
— the contract the WS7 compiler (O7-T02) and every downstream WS7 ticket satisfy, and
the citation any future "what is a project's input contract / where does it live?"
question resolves to. The companion `docs/specs/PROJECT-OS-PACK.md` is the field-level
spec of record; this ADR fixes the decisions the spec must not contradict.

### D-1 — The manifest is `projects/<name>/PROJECT-OS.yaml`: one machine-readable descriptor at the project root

Every pack has exactly **one manifest**, `projects/<name>/PROJECT-OS.yaml`, at the root
of the project folder. It is the single machine-readable entry point the compiler reads
first: it is YAML (parseable without executing anything), it declares the project's
identity and Stage-1 product/KPI surface, and its `name` MUST equal the `<name>`
directory segment (the compiler rejects a mismatch). Placing it at the project root —
not in `docs/` — keeps it the obvious, stable anchor a scaffolder writes and a compiler
resolves without a search.

### D-2 — The manifest's field set is closed: `name`, `mission`, `constraints`, `stack`, `budget`, `success_metrics`

The manifest carries, and the compiler validates, a **fixed set of fields** (their
grammar and required/optional status are the spec's job; their *presence in the contract*
is this ADR's):

- **`name`** — the project slug (== the `<name>` folder segment; kebab-case, unique).
- **`mission`** — one-paragraph statement of what the product is and for whom (the
  Stage-1 "business need" seed).
- **`constraints`** — the project-local constraints: the tightenings the project adds on
  top of org law (compliance regime, data-residency, latency/cost ceilings, forbidden
  dependencies, …). These feed the Constitution (D-6) and may only **tighten** org law.
- **`stack`** — the intended technology surface (languages, frameworks, model
  provider(s), infra target). Indicative at intake; the binding technical decisions are
  still made in AADL Stage-2 Design (this is a *seed*, not a design doc).
- **`budget`** — the token/compute + money budget envelope (the Stage-1 "resources"
  seed; the AADL GATE-1 "token + infra budget approved by finance-analyst" checkbox
  reads this).
- **`success_metrics`** — the measurable business KPI(s) the project is judged against
  (the Stage-1 "measurable business KPI defined" GATE-1 checkbox; CPR/AHT-style
  metrics with thresholds). This is the KPI-definition surface that makes GATE-1 a
  CPO-accountable call.

The set is **closed**: a compiler validates exactly these keys, an unknown top-level key
is a lint warning (surfaced, not silently dropped), and a missing required key is an
actionable rejection. Extending the set is a spec revision + a new/amended ADR, never an
ad-hoc per-project addition.

### D-3 — The lifecycle skeleton is the CANONICAL AADL §2 six-stage tree — `docs/01-planning…06-maintenance`, NOT qaqnuz's divergent names

The pack's documentation tree is the **canonical** skeleton from
`ai-agent-lifecycle.md` §2, verbatim:

```
projects/<name>/
├── README.md                  # charter + stage board (gate status log)
├── APPROVED-GOAL-QUEUE.md     # Founder-approved, research-backed work queue (D-5)
├── PROJECT-OS.yaml            # the manifest (D-1/D-2)
└── docs/
    ├── 01-planning/           # business-needs, objectives, resources, risk-ethics-review
    ├── 02-design/             # framework-decision, model-card, grounding-architecture, guardrails-spec
    ├── 03-development/        # architecture-topography, tool-contracts, onboarding
    ├── 04-testing/            # eval-report, integration-tests, ux-test-notes, red-team-report
    ├── 05-deployment/         # launch-runbook, guardrail-verification, observability, compliance-validation
    └── 06-maintenance/        # kpi-monitor, optimization-log, feedback-loop
```

- The six folder names are **exactly** `01-planning`, `02-design`, `03-development`,
  `04-testing`, `05-deployment`, `06-maintenance` — one folder per AADL lifecycle stage,
  in order. A GATEWAY scaffolder emits **these** names; the per-stage mandatory
  artifacts are the ones AADL §3 lists (feeding each stage's GATE checklist).
- qaqnuz's layout (`01-intake`, `02-prd`, `03-rfc`, `04-program`, `05-delivery`,
  `06-release`, `07-operations`, …) is **explicitly NOT the contract**. It is a legacy,
  divergent, human-authored layout; a pack MUST use the canonical names. (An existing
  divergent project reconciles via the AADL §2 `LIFECYCLE-MAP.md` escape — that is a
  migration aid for a pre-existing tree, **not** a licence for a new pack to drift.)
- This makes the tree the *same shape for every project*, which is precisely what lets
  `gateway_compile.py` walk it, placeholder-lint it, and map each stage folder to its
  AADL gate without per-project configuration.

### D-4 — The pack carries the Founder discovery answers (≥10 Q&A, or an explicit waiver)

The pack includes the **Founder Discovery Gate** result: at least **10 Founder
questions and their answers**, or an explicit Founder decline/waiver, per the QONUN
Founder-Approved Goal Queue law and AADL §5. These answers live in the project folder
(canonically under `docs/01-planning/`, e.g. a `discovery.md`, plus the sourced global
research the law requires — market, competitors, regulatory, technical architecture,
pricing/unit-economics, SEO/channel, risks). The discovery answers are a **precondition
of a valid pack**: the compiler checks the gate (≥10 Q&A or waiver) and, if it is open,
generates the questions rather than proceeding (O7-T02). A pack with an open discovery
gate is not compilable.

### D-5 — The pack carries `projects/<name>/APPROVED-GOAL-QUEUE.md`, and the approval signal is load-bearing

The pack includes **`projects/<name>/APPROVED-GOAL-QUEUE.md`** — the Founder-approved,
research-backed work queue (QONUN-3). The queue is only actionable once the Founder has
given an **explicit approval signal** (`APPROVED:` / `TASDIQLANDI:`, i.e. queue-item
`status: founder_approved` or later). Until then, **no board tickets are compiled** —
the existing `scripts/check_approved_goal_queue.py` is the gate O7-T02 wires, and
`/daslab-plan` decomposes only `founder_approved` items. This keeps the QONUN Founder
gate intact: the pack format *names* the approved queue as a required part, and the
compiler refuses to emit story tickets from an unapproved queue.

### D-6 — Constitution = QONUN laws + project-local constraints; project-local NEVER relaxes org law (precedence)

The pack's **Constitution** — the full body of rules that binds the project — is the
**union** of:

- the org's **QONUN laws** (Project Placement, AI-Agent Lifecycle, Founder-Approved
  Goal Queue, Model Allocation, Persistent Memory) and all higher-precedence org policy
  (`governance/charter.md`, board-issued `governance/` policy including the AADL, the
  dept charters); **plus**
- the **project-local constraints** declared in the manifest's `constraints` field and
  the project's own `01-planning` risk-ethics review.

A project-local constraint may only **add restrictions** — it may **tighten** org law,
**never relax** it. This is the precedence law: root `AGENTS.md` §2 ("lower-precedence
may add constraints but never relax them set higher up") and its AADL restatement
("projects may add constraints, never relax them"). Concretely: a project may forbid a
dependency the org allows, demand a stricter data-residency or review regime than org
baseline, or set a tighter budget ceiling — but it may **never** waive a QONUN law,
skip an AADL gate, relax a security/compliance policy, or grant itself an exception to
never-auto-approve. Where a project-local constraint and org law disagree, **org law
wins** and the stricter of the two applies. The compiler treats a pack that attempts to
relax org law (e.g. a `constraints` entry that waives a gate or a QONUN rule) as an
**invalid pack**, rejected with an actionable error — a project's Constitution is a
tightening lens over org law, never a loophole.

## Consequences

**Positive.**
- WS7 O7-T02 (`gateway_compile.py`) builds against a **fixed, closed contract**: one
  manifest with a known field set (D-2), one canonical doc tree it can walk (D-3), one
  discovery gate to check (D-4), and one approval gate to honour (D-5). "Validate pack →
  check discovery gate → verify approval → compile story tickets" (O7-T02's acceptance)
  maps directly onto D-1…D-5.
- **Project inputs stop drifting.** Every new pack is the same shape (D-3), so "compile
  a project" is one code path, not one per project — which is exactly what O7-T05's
  "second sample pack passes with no gateway code changes" generality check requires.
- The **Founder gate stays intact**: the pack format *names* the discovery answers (D-4)
  and the approved queue (D-5) as required parts and wires the existing
  `check_approved_goal_queue.py`, so no pack can bootstrap tickets without Founder
  approval. QONUN-3 is enforced by the contract, not by convention.
- The **Constitution is a tightening lens, never a loophole** (D-6): a project can be
  *stricter* than the org but never weaker, so onboarding a project cannot smuggle in a
  relaxation of a QONUN law, an AADL gate, or a security policy.
- Deleting the pack feature is deleting `docs/specs/PROJECT-OS-PACK.md` + this ADR +
  the compiler's read of the manifest — the AADL, QONUN, the goal-queue gate, and the
  board schema are all untouched, because the pack *references* them rather than forking
  them.

**Negative / accepted.**
- The canonical `01-planning…06-maintenance` tree diverges from qaqnuz's real layout, so
  the two do not share folder names. **Accepted** — the AADL already anticipated this
  with the §2 `LIFECYCLE-MAP.md` escape for a pre-existing divergent tree; the pack
  contract binds *new* packs to the canonical names, and qaqnuz is a legacy project that
  maps rather than migrates. Forcing a rename of a live project is out of scope here.
- A closed manifest field set (D-2) means a genuinely new field needs a spec revision +
  an ADR amendment, not an ad-hoc key. **Accepted** — a closed, validatable set is the
  whole point; an open manifest could not be lint-checked, and "add a field" is a
  reviewed contract change, exactly as it should be.
- The pack contract assumes the AADL six-stage skeleton, so a non-agent (plain
  software) project would carry stages it does not strictly need. **Accepted** — WS7's
  scope is *AI-agent* project delivery (the AADL's universal scope); a non-agent project
  follows the org methodology without the AI-specific artifacts (AADL §0), and is not
  the pack's target.

**Law check.**
- **Charter / RACI** — GATE-1 Planning is CPO-accountable (AADL RACI §1;
  `model-allocation.md` Tier O). The manifest's `mission`/`constraints`/`success_metrics`
  are the product-scope + KPI-definition surface that makes this a CPO call. Decided by
  the CPO with tech-writer (O7-T01 co-owner), CTO (`gateway_compile.py` owner + ADR
  ratifier), and CEO (WS7 owner / author) consulted; finance-analyst + legal-analyst are
  the GATE-1 Consulted whose budget + risk-ethics inputs the manifest and `01-planning`
  feed. It amends no policy — it constrains an input shape by reference.
- **AADL** — a GATE-1 Planning artifact for ORGANISM WS7; no gate skipped. The pack's
  skeleton (D-3) and per-stage artifacts are the **canonical** AADL §2/§3 ones, copied
  by reference and **not** renamed; the discovery gate (D-4) and approval gate (D-5) are
  the AADL §5 / QONUN-3 gates named, not re-invented. The pack ships no compiler, migrates
  no project, and signs no gate.
- **QONUN — Project Placement** — the entire pack is rooted at `projects/<name>/`; the
  manifest, docs tree, discovery answers, and goal queue all live inside the project
  folder. This ADR + spec are **platform** docs under `docs/adr/` + `docs/specs/`
  (org-engine machinery, WS7), and the `board/tickets/DAS-1492` ticket carries **no
  `project:` field** — it is org-engine work, not project work.
- **QONUN — Founder-Approved Goal Queue** — the pack format *requires* the discovery
  answers (D-4) and the Founder-approved `APPROVED-GOAL-QUEUE.md` (D-5); the compiler
  wires the existing `check_approved_goal_queue.py` and refuses to emit tickets from an
  unapproved queue. The Founder gate is preserved, not bypassed.
- **Precedence / Constitution** — D-6 is the precedence law (root `AGENTS.md` §2 + the
  AADL scope note): a project-local constraint may only tighten org law; org law wins
  on conflict; a pack that relaxes org law is invalid. No never-auto-approve category is
  triggered (a decision doc + spec, not a policy/flag/model mutation). No SSOT is edited
  in place — `ai-agent-lifecycle.md`, `check_approved_goal_queue.py`, the board schema,
  and the QONUN laws are all untouched and only referenced.

## Enforcement / acceptance

- This ADR is decided by the **CPO** (GATE-1 Planning) and is `Accepted` on merge. It
  adds a row to `docs/adr/README.md` and extends the ADR themes with a WS7 GATEWAY entry.
- The companion `docs/specs/PROJECT-OS-PACK.md` is the field-level spec of record; it
  must not contradict D-1…D-6, and it is what O7-T02 (`gateway_compile.py`) validates a
  real pack against.
- D-1…D-6 are the contract the WS7 implementation tickets satisfy and their acceptance
  hooks test:
  - **D-1/D-2** — exactly one `projects/<name>/PROJECT-OS.yaml` per pack, with the closed
    field set (`name`, `mission`, `constraints`, `stack`, `budget`, `success_metrics`);
    a missing required field or a `name`↔folder mismatch is an actionable rejection
    (O7-T02: "broken pack rejected with actionable errors").
  - **D-3** — the doc tree uses the **canonical** `01-planning…06-maintenance` names
    (AADL §2), never qaqnuz's divergent names; a GATEWAY scaffolder emits exactly this
    shape, and O7-T05's "second sample pack passes with no gateway code changes" proves
    the shape is project-agnostic.
  - **D-4/D-5** — the compiler checks the discovery gate (≥10 Q&A or waiver) and the
    Founder approval signal (`APPROVED:`/`TASDIQLANDI:` via
    `check_approved_goal_queue.py`) before compiling any story ticket; an open gate
    blocks compilation.
  - **D-6** — a pack whose project-local constraints attempt to relax org law (waive a
    QONUN rule, skip an AADL gate, loosen a security policy, self-grant
    never-auto-approve) is an **invalid pack**; the Constitution is a tightening lens,
    org law wins on conflict.
- Any future "what is the project input contract / where does the manifest live / can a
  project relax a QONUN law?" question resolves via D-1…D-6 (and the companion spec). An
  undeclared pack shape is not in this envelope — so it is not permitted; widening the
  contract is a spec revision + a new ADR that supersedes this one, never an in-place
  drift.
