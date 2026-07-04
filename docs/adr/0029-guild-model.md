# ADR 0029 — Guild model: a guild is per-ROLE craft captured as a compilable agent-template (`governance/agent-templates/<role>.md`), grouped by dept, NO new org unit

- **Status:** Accepted (**CPO — decider; AADL GATE-1 Planning artifact — 2026-07-03**)
- **Date:** 2026-07-03
- **Scope:** Platform / org-engine — the "guild" knowledge model for the ORGANISM operator fleet (WS6 GUILD, O6-T01). A **decision doc only**: it fixes the shape and compile contract that the WS6 implementation tickets (O6-T02 authors the templates, O6-T03 compiles them) must satisfy, and ships **no template files and no generator change** itself. It does not edit `scripts/gen_subagents.py`; it names the existing overlay→shim compile seam and the `check_agents_sync.py` drift guard as the contract the templates layer onto.
- **Deciders:** **CPO (accountable)** — GATE-1 Planning is CPO-accountable (AADL RACI §1; model-allocation Tier O: "GATE-1 accountable — product scope and KPI definitions"); the guild boundary (§9 Q5, "guild = dept vs craft") is a product-scope framing call, and WS6 O6-T01 names `cpo` as owner. CTO consulted — RACI 3.1 ADR ratifier and owner of the `gen_subagents.py` compile path (O6-T03). CEO consulted — WS6 planning owner and this ticket's author (DAS-1485). Backend-EM consulted — owns the O6-T03 compile-through-`gen_subagents` extension. No Founder gate is triggered: this is a decision doc, not a policy/flag/model-table mutation.
- **Relates:** ORGANISM WS6 GUILD (`docs/research/ORGANISM-PROGRAM-PLAN.md` §4 WS6 table O6-T01…O6-T08, §9 Q5 — the approved default #5, and the tool-map row 112 "WS6 templates compile through `gen_subagents`, guarded by `check_agents_sync` (**not** `check_org_drift`)"). Cites — but does **not** edit — `scripts/gen_subagents.py` (the overlay→`.claude/agents/` generator: model/effort table parse, `communication-flows` route compile, ROUTING.md emit), `scripts/check_agents_sync.py` (the shim ↔ ROUTING.md ↔ model-policy drift gate), `governance/policies/model-allocation.md` (the single source of truth for `model` + `effort`, ADR 0013), `governance/communication-flows.yaml` (the derived route graph, ADR 0026), and the six-stage overlay convention (`<dept>/agents/<role>/AGENTS.md`, ADR 0018 role-overlay contract). Builds on ADR 0007/0013 (model + effort tiers under a fixed opus floor) and shares the generate-and-diff drift-gate pattern of ADR 0009 R-12 (`check_org_drift.py` for the org schema — a **sibling** pattern, not the guild's guard).
- **Supersedes / Amends:** nothing. This ADR **constrains by reference** how per-role craft is captured and compiled; it mutates no code, edits no policy table, and forks no generator.

> **Numbering note.** The WS6 plan text (§4 WS6 table O6-T01, §5 ADR list) names this artifact "ADR-0028". The append-only ADR numbering rule (README) already assigned **0028** to *cockpit-form-factor* (Accepted 2026-07-03), so the guild-model decision takes the next free number, **0029**. Plan-text numbers are indicative; the README ledger is authoritative — the same reconciliation ADR 0028 recorded against its own plan-text number. (The plan's §5 line "0029 = Project-OS pack format" is WS7's ADR and will likewise take the next free number when authored.)

> A "guild" is the shared **craft of a role** — the identity, standing priors, toolkit,
> model/effort budget, and accumulated lessons that make a `backend-eng` a good
> backend engineer regardless of which ticket it draws. Today that craft is
> **implicit and scattered**: partly in the hand-written overlay, partly in the
> generated shim, partly in the model table, partly in an agent's head and lost at
> the end of a run. WS6 wants that craft to be an **explicit, reviewable,
> version-controlled artifact** that also *compiles* into the runtime shim — so a
> role's knowledge is one file, not four, and improving a role is a reviewed diff.
> The forked question (§9 Q5) is **what a guild IS**: a new org unit (a "guild"
> department or cross-cutting body), or simply the per-role craft file. This ADR
> closes GATE-1 (Planning) for the WS6 guild model. **No behaviour changes on
> merge** — no template file is authored here and the generator is untouched.

## Context

The audit's WS6 fork (§9 Q5) is genuine and easy to get wrong in a way that costs
org coherence:

- **Guild = a new org unit** (a "Backend Guild", a cross-dept craft body, a parallel
  reporting line). This *invents structure*: it duplicates the department the role
  already lives in, adds a second home for a role, and forces every downstream
  artifact that keys off the 32-node fleet (ROUTING.md, `communication-flows.yaml`,
  the RACI ladder, `schema.daslab.yaml`) to grow a concept it does not have. It also
  reopens settled questions — who does a "guild" report to, does it emit routing
  edges, is it a `sender`/`receiver`? — for zero runtime gain.
- **Guild = the per-role craft file** (the approved default #5). A guild is not a
  *place* in the org; it is the *craft of a role*. Captured as one file per role,
  **grouped by department** (the role already has exactly one department), it needs
  **no new node, no new routing edge, no schema change** — it slots into the existing
  hierarchy and the existing generate-and-diff overlay flow.

The platform already ships the entire compile machinery this needs; **none of it is
invented here**:

- **`scripts/gen_subagents.py`** — the generator. It walks `<dept>/agents/<role>/AGENTS.md`
  overlays, parses the model+effort table from `model-allocation.md`
  (`load_alloc()`), compiles each role's outbound routes from
  `communication-flows.yaml` (`load_outbound_routes()` / `format_routes_block()`),
  and writes `.claude/agents/<role>.md` plus `board/ROUTING.md`. It is idempotent:
  it deletes and fully regenerates its output every run (generate-and-diff clean).
- **`scripts/check_agents_sync.py`** — the drift gate. It cross-checks the generated
  `.claude/agents/*` shims against `ROUTING.md` and the `model-allocation.md` table:
  a role in ROUTING with no shim, a shim missing from ROUTING, a `name:` that does
  not match its filename, a `model:` that is not a valid tier, or a shim model that
  disagrees with the policy row — each fails CI. This is the guard that keeps the
  compiled artifact honest.
- **`governance/policies/model-allocation.md`** — the single source of truth for
  `model` + `effort` (ADR 0013), aliases (`opus`/`sonnet`/`haiku`) that auto-track
  the newest model of each tier; haiku takes no `effort` line.
- **`governance/communication-flows.yaml`** — the derived route graph (ADR 0026); a
  role's allowed `(sender → receiver)` edges are already compiled into its shim.

The question is not "build a guild org" — it is "**where does per-role craft live,
and how does it reach the runtime shim**, without inventing a node and without
forking the generator". This ADR answers that as a closed set of decision
invariants.

**AADL stage.** GATE-1 Planning. A decision doc; it ships no template and no
generator change.

**Extend-vs-new posture (binding).** EXTEND, do not duplicate. The agent-template is
a **new input surface layered onto the existing overlay→shim compile flow**, not a
new pipeline. It reuses the same generator, the same model/effort table, the same
route graph, and the same drift gate. The ADR itself is a NEW file (next free
number 0029) plus a README index row; the *machinery* it decides to use is entirely
pre-existing.

## Decision

A **guild is the per-ROLE craft of a role, captured as a compilable agent-template
file at `governance/agent-templates/<role>.md`, grouped by department** (§9 default
#5). It is **NOT a new org unit** — no guild department, no cross-cutting body, no
new routing node or edge, no `schema.daslab.yaml` change. The template **compiles
into the runtime shim through the existing `scripts/gen_subagents.py` overlay flow**
and is kept honest by the existing `scripts/check_agents_sync.py` generate-and-diff
drift gate. The following are the **binding guild-model invariants** — the contract
every WS6 template/compile ticket satisfies, and the citation any future "what is a
guild / where does role craft live?" question resolves to.

### G-1 — A guild is per-ROLE craft, grouped by dept; NO new org unit

The unit of the guild is the **role**, not a new organizational body. There is
exactly **one template per role key**, named `governance/agent-templates/<role>.md`,
where `<role>` is the same key used for `.claude/agents/<role>.md`,
`<dept>/agents/<role>/AGENTS.md`, and the ROUTING/model/flows tables.

- Templates are **grouped by department** for authoring/review locality (a role has
  exactly one department in the fleet), but "grouped by dept" is an organizing
  convention over the flat per-role files — it introduces **no** `guild:` node, no
  parallel reporting line, no new `sender`/`receiver`, and **no** edit to
  `org/schema.daslab.yaml`, `board/ROUTING.md`, or `governance/communication-flows.yaml`.
- The role's **department, manager, and reporting line stay exactly as ROUTING.md /
  the schema already define them**. A guild is a *craft*, not a *place*: it answers
  "what does a good `backend-eng` know and reach for", never "who does the Backend
  Guild report to". This dissolves the §9 Q5 ambiguity by ruling *craft*, and
  respects the existing 32-node hierarchy unchanged.

### G-2 — Template contents: the closed set of craft fields

Each `governance/agent-templates/<role>.md` carries, and only carries, the role's
craft as a fixed set of fields:

- **identity / goal / behavioral-priors** — who the role is, the standing objective
  of its craft, and the durable priors it works by (the reusable half of what today
  is re-derived per run or half-stated in the overlay).
- **toolkit allowlist** — the tools/capabilities the role is expected to reach for
  (a positive craft statement; it does not widen any security boundary — see the Law
  check).
- **`model` + `effort`, copied VERBATIM from `governance/policies/model-allocation.md`**
  (G-3).
- **`produces` / `consumes` defaults** — the typed artifact contract(s) the role
  characteristically hands downstream / expects upstream (the same registry as the
  board's `produces`/`consumes` fields, `governance/schemas/<name>.yaml`, DAS-1467),
  as role-level *defaults* a ticket may still override.
- **allowed `communication-flows` routes** — the role's outbound `(delegation |
  escalation) → receiver` edges, drawn from `governance/communication-flows.yaml`
  (the same set `gen_subagents.py` already compiles into the shim, ADR 0026) — never
  hand-authored topology.
- **eval-baseline reference** — a pointer to the role's golden-eval baseline
  (the WS6 `evals/<role>/…` harness + scorecard, O6-T04/O6-T05), so the template
  states the bar its craft is measured against.
- **a `## Learned` section** — a bounded, deduped, dated accumulation of accepted
  role lessons (the sink for O6-T06's `daslab-learn` distillation of Founder-accepted
  feedback). This is the ONLY part of a template that grows over the role's life; it
  is append-with-hygiene, not free-form drift.

### G-3 — `model` + `effort` are VERBATIM from the allocation table; NO Tier F / Fable 5

The template's `model` and `effort` values are **copied verbatim from
`governance/policies/model-allocation.md`** — the single source of truth (ADR
0013) — and are **never** authored, guessed, or edited in the template.

- The allocation table stays the SSOT; the template is a *consumer* of it, exactly as
  the shim is. `gen_subagents.py`'s `load_alloc()` remains the one parser; a template
  that restated a different model/effort would be caught by `check_agents_sync.py`'s
  policy cross-check (G-4) and fail CI.
- **No Tier F / no Fable 5.** Fable 5 is decommissioned with no restore path
  (model-allocation §Tier-F, retired); `cto` and `security-lead` run on **opus**
  permanently. The valid model tiers are exactly `{opus, sonnet, haiku}`; **haiku
  takes no `effort`** (400 error) and its template omits the effort line, mirroring
  the shim. An explicit per-role effort cell wins; a blank cell falls back to
  `opus → high`, `sonnet → medium` — the same rule the generator already applies.

### G-4 — Compiles via `gen_subagents.py` → `.claude/agents/`; guarded by `check_agents_sync.py` (generate-and-diff)

The template reaches the runtime through the **existing** overlay→shim compile flow,
not a new pipeline:

- `scripts/gen_subagents.py` **compiles** the per-role templates into
  `.claude/agents/<role>.md` — the same overlay the generator already applies. The
  generator stays idempotent (it deletes and fully regenerates `.claude/agents/*` +
  `board/ROUTING.md` every run), so the output is **generate-and-diff clean**: a
  hand-edit to a shim, or a template change not re-compiled, shows up as a diff.
- `scripts/check_agents_sync.py` is the **drift guard**: it fails CI when a shim and
  ROUTING.md disagree, when a `name:` does not match its filename, when a `model:` is
  not a valid tier, or when a shim model diverges from the `model-allocation.md`
  policy row. This is the guard the WS6 tool-map (§ plan row 112) names for the
  templates — **`check_agents_sync`, NOT `check_org_drift`**. (`check_org_drift.py`
  is the sibling generate-and-diff gate for the *org schema* → `_org_generated.py`
  under R-12 / ADR 0009; the guild templates follow the same *pattern* but are
  guarded by `check_agents_sync`, keeping the two gates cleanly separated by SSOT.)
- Because the compile path and the drift gate are pre-existing, the guild model adds
  **no new validator and no new generator** — O6-T03 is an *extension* of
  `gen_subagents.py` to read the template surface, and the diagnostics gate keeps it
  honest.

### G-5 — Overlay-consistent, review-first; a template never re-decides an SSOT

The template is the craft layer *alongside* the role overlay (ADR 0018), never a
competing source of truth for anything already owned elsewhere:

- The template **references, never restates**, every value owned by an SSOT: `model`
  + `effort` come from the allocation table (G-3), routes come from
  `communication-flows.yaml` (ADR 0026), the reporting line comes from
  ROUTING.md/schema (G-1), `produces`/`consumes` names resolve to
  `governance/schemas/<name>.yaml` (DAS-1467). A template can *default*, it can
  *characterize*, it can *accumulate lessons* — it can never *fork* a governed value.
- Editing a template is ordinary reviewed engineering work (a diff, a PR, a green
  diagnostics run), **except** where a field touches a governed surface (a model/
  effort change is a `model-allocation.md` edit under chairman approval; a route
  change is a `communication-flows` edit; neither is done *in* a template). The
  `## Learned` section grows only via the `daslab-learn` distillation of
  **Founder-accepted** feedback (O6-T06) — bounded, deduped, dated — never by an
  agent free-writing about itself mid-run.

## Consequences

**Positive.**
- WS6 O6-T02 (author the templates) and O6-T03 (compile them through
  `gen_subagents.py`) build against a **fixed, closed set of five invariants** and a
  fixed field list (G-2) instead of re-deriving "what is a guild / what goes in a
  template" per ticket. O6-T02's acceptance ("compiles via `gen_subagents`;
  `check_agents_sync` guards drift") maps directly onto G-4.
- The §9 Q5 guild boundary is resolved **without inventing structure**: one file per
  role, grouped by dept, no new node/edge/schema change. Deleting the guild feature
  is deleting `governance/agent-templates/` and reverting the generator's read of it —
  the 32-node fleet, ROUTING, flows, and RACI are untouched.
- Per-role craft becomes **one reviewable artifact** instead of four scattered
  sources, and the `## Learned` sink gives O6-T06's learned-instructions loop a
  bounded, dated home that *compiles back into the runtime shim* — closing the
  self-improvement loop without a parallel process.
- Model/effort **cannot drift**: the template consumes the allocation table verbatim
  (G-3) and `check_agents_sync` cross-checks the compiled shim against the same SSOT
  (G-4), so a mistyped tier fails CI rather than silently mis-routing a role.

**Negative / accepted.**
- Adding a per-role template surface is **32 more files to author** (O6-T05 fans this
  out one child per role). **Accepted** — the craft already exists implicitly; making
  it explicit is the whole point, and the fanout + golden-eval bar (O6-T04/T05) is how
  the plan already scoped that cost.
- A template that *duplicates* an SSOT value (e.g. restating a model) is a latent
  inconsistency risk. **Accepted and mitigated** — G-3/G-5 make the template a
  *consumer* (verbatim copy, or better, a compile-time read), and `check_agents_sync`
  fails any shim whose model disagrees with the policy row, so a stale duplicate is
  caught at CI, not at runtime.
- Grouping "by dept" is an authoring convention, not an enforced directory shape in
  this ADR (the files are flat per-role keyed like the shims). **Accepted** — the
  role→dept mapping is already owned by the overlay tree and ROUTING; a second
  enforced grouping would duplicate that SSOT. If a directory grouping is later
  wanted it is an implementation detail of O6-T02/O6-T03, not a new org unit.

**Law check.**
- **Charter / RACI** — GATE-1 Planning is CPO-accountable (AADL RACI §1;
  model-allocation Tier O). The ADR is decided by the CPO with CTO (RACI 3.1 ADR
  ratifier + `gen_subagents` owner), CEO (WS6 planning owner / author), and
  Backend-EM (O6-T03 compile) consulted. It amends no policy — it constrains a
  knowledge-capture shape by reference.
- **AADL** — a GATE-1 Planning artifact for ORGANISM WS6; no gate skipped; ships no
  template and no generator change. The templates it decides are view/craft layers;
  they sign no gate and answer no interrupt-card.
- **Model allocation** — the SSOT is **unchanged**. Templates consume `model` +
  `effort` **verbatim** from `model-allocation.md` (G-3); no Tier F / Fable 5 (retired,
  no restore path); haiku omits `effort`. The opus floor is untouched.
- **Board audit / governance-as-policy** — no SSOT edited in place
  (`gen_subagents.py`, `check_agents_sync.py`, `model-allocation.md`,
  `communication-flows.yaml`, `schema.daslab.yaml` all untouched by this ADR). No
  never-auto-approve category is triggered (a decision doc, not a policy/flag/model
  mutation). No new org node or routing edge is created.
- **Project placement** — a platform-level ADR under `docs/adr/`; no project artifact
  written; the `board/tickets/` ticket carries no `project:` field. Templates live in
  `governance/agent-templates/`, an org-engine path.

## Enforcement / acceptance

- This ADR is decided by the **CPO** (GATE-1 Planning) and is `Accepted` on merge. It
  adds a row to `docs/adr/README.md` and extends the ADR themes with a WS6 GUILD
  entry.
- G-1…G-5 are the contract the WS6 implementation tickets satisfy and their
  acceptance hooks test:
  - **G-1** — one `governance/agent-templates/<role>.md` per role key, grouped by
    dept; NO new node/edge, NO `schema.daslab.yaml` / `ROUTING.md` /
    `communication-flows.yaml` topology change. `check_org_drift.py` (org-schema
    generate-and-diff) stays green because the schema is untouched.
  - **G-2/G-3** — each template carries the closed craft field set, with `model` +
    `effort` **verbatim** from `model-allocation.md`, no Tier F / Fable 5, haiku
    omitting `effort`.
  - **G-4** — the templates compile through `scripts/gen_subagents.py` into
    `.claude/agents/*` (generate-and-diff clean) and `scripts/check_agents_sync.py`
    passes (shim ↔ ROUTING ↔ model-policy in sync). O6-T03's acceptance
    ("generate-and-diff clean") maps here.
  - **G-5** — no template restates/forks an SSOT value; `## Learned` grows only via
    the `daslab-learn` distillation of Founder-accepted feedback (O6-T06), bounded/
    deduped/dated.
- Any future "should a guild be a new department / a cross-cutting org body / a new
  routing node?" question resolves to **no** by G-1. An undeclared guild structure is
  not in this envelope — so it is not permitted; widening it is a new ADR that
  supersedes this one, never an in-place edit.
