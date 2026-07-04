# ADR 0014 — Native ticket-altitude Clarify gate: `[NEEDS CLARIFICATION]` marker + Definition-of-Ready (spec-kit graft)

- **Status:** Accepted (ratified 2026-06-26; CTO-ratified; no binding-policy text changed; **fail-closed since 2026-06-26 — ADR-0013 ratified**)
- **Date:** 2026-06-26
- **Scope:** Planning/execution machinery — `.claude/skills/daslab-cycle/SKILL.md` (Step 3 selection),
  `.claude/skills/daslab-plan/SKILL.md` (decomposition), two new `scripts/check_*.py` validators +
  `scripts/diagnostics.py` registration. **Does NOT edit `governance/policies/ai-agent-lifecycle.md`
  binding text** (that is precedence-2 board policy — Board-ratification-only).
- **Deciders:** **CTO (accountable — ratify);** Founder (scope-lift authority — see Context); Security
  Lead (consulted — clarify routing must never relax a security gate)
- **Relates:** ADR 0002 (enforcement-as-code — every gate ships as a typed validator + failing-case
  pytest); ADR 0013 (effort-tier boundary — **must ratify first**, see §Sequencing); ADR 0006 (static
  cache prefix — markers ride the volatile per-ticket tail, prefix unchanged); QONUN-3 (Founder-Approved
  Goal Queue); QONUN-5 (never-auto-approve); `board/ROUTING.md`; `board/README.md`; AADL all stages.
- **Origin:** GitHub Spec Kit (`github/spec-kit`) Spec-Driven Development — its `[NEEDS CLARIFICATION]`
  marker + `/clarify` phase. This ADR grafts **only that one idea**, natively, and explicitly rejects
  the `specify` CLI, the `.specify/` tree, a separate `constitution.md`, and `specs/NNN/` proliferation
  (redundant with DasLab's existing constitution + parallel-wave orchestrator; would serialize waves and
  import spec-kit's unsolved spec-drift defect, issue #1191).

## Context

**The gap (DasLab's own diagnostic).** Once a ticket reaches `todo`, `/daslab-cycle` Step 3 selects it
as *actionable* and dispatches it to a code subagent **regardless of whether its `## Description` is
precise enough to execute**. There is no structured mechanism to flag an under-specified ticket *before*
work starts. The Founder Discovery Gate (the 10-question QONUN-3 rule) fires only at **project** intake
inside `/daslab-plan` — there is **no clarify gate at ticket altitude**. Underspecified tickets dispatched
straight to code are the documented driver of the 20–40% rework failure mode (spec-kit's own benchmarks;
Scott Logic; ranthebuilder.cloud).

**Why spec-kit's marker, and nothing else.** Spec Kit's pipeline (`constitution → specify → clarify →
plan → tasks → analyze → implement`) maps almost 1:1 onto things DasLab already owns in a **stronger,
machine-enforced** form: the constitution is `CLAUDE.md` + `AGENTS.md` + `governance/` + the 18-ADR corpus
+ ~29 `check_*.py` validators + the `diagnostics.py` 100/100 release gate; `specify`/`tasks` is
`/daslab-plan`; `implement` is `/daslab-cycle` + AADL gate order + CI-green done-gate. The **one** primitive
DasLab lacks is *clarify-before-build at ticket altitude*. Grafting it is wave-compatible: clarification is
front-loaded in the ticket file (async, merge-able), **not** an interactive mid-wave Q&A, so it does not
serialize the parallel-wave model.

**Scope-lift.** This is org-engine work, outside the standing `scope-qaqnuz-only` directive (2026-06-23).
The Founder **explicitly lifted scope for this item on 2026-06-26** and authorized creation of this ADR +
the implementing ticket (DAS-1416). Authoring is authorized; **dispatch is not** — DAS-1416 stays
`status: backlog` / `approval: human:founder` until an explicit `APPROVED:` / `TASDIQLANDI:` signal (QONUN-3).

## Decision

Adopt a **fail-closed, native Definition-of-Ready gate** at ticket altitude, plus the orthogonal QONUN-3
CI validator the engine currently lacks. Five parts:

1. **The marker.** A ticket may carry inline `[NEEDS CLARIFICATION: <precise question>]` tokens in its
   `## Description` or `## Acceptance criteria`. **Max 3 per ticket** (spec-kit's cap) — more than 3 means
   the ticket is too underspecified to be one ticket and must return to `/daslab-plan` for decomposition.

2. **Definition-of-Ready (DoR) predicate.** A ticket is **actionable only if it contains zero unresolved
   `[NEEDS CLARIFICATION:` tokens.** Resolution = the author (or the routed reviewer) replaces the marker
   with the answer and incorporates it. Resolution source is the **existing** Founder discovery answers /
   ticket context — **not** a new interactive round (preserves autonomous wave execution).

3. **`/daslab-cycle` wiring (Step 3 "Select every actionable ticket", ≈ line 74 — the *selection* step,
   not Triage).** A ticket with an unresolved marker is **not actionable**: skip it, count it as
   `clarify-blocked` in the wave report, and if it is `todo` **reassign it to the author's reviewer per
   `ROUTING.md`** (a thinking, opus-tier role) for resolution — **never** dispatch it to a code subagent.
   **Circuit-breaker:** if `clarify-blocked` exceeds a fixed share of the actionable set (proposed default:
   **≥ half**), the wave **halts and emits a blocker report** instead of looping — so an autonomous
   overnight run cannot stall on agents over-flagging to dodge hard tickets.

4. **`/daslab-plan` wiring.** When a queue row under-specifies scope, the decomposer **emits
   `[NEEDS CLARIFICATION: …]` instead of silently guessing**. This makes the gap explicit and routable
   rather than a downstream rework.

5. **Enforcement-as-code (ADR 0002), two validators:**
   - **`scripts/check_clarifications.py`** — fails CI if any ticket in `in_progress` / `in_review` /
     `done` still contains an unresolved `[NEEDS CLARIFICATION:` token, **or** any ticket carries > 3
     markers. **Rollout is staged:** ship **warn-only** (reports clarify-block counts, exit 0) for **one
     wave**, then flip to **fail-closed** (non-zero exit) — the safe rollback path.
   - **`scripts/check_approved_goal_queue.py`** — closes the documented, **orthogonal** QONUN-3 gap (no
     validator exists today): asserts `projects/<name>/APPROVED-GOAL-QUEUE.md` exists and carries a
     Founder-approved item before any of that project's tickets may sit at `todo`. Cheap, independent of
     the clarify graft, bundled here because it is the same "front-load intent before dispatch" theme.

   Both validators register in `scripts/diagnostics.py` under the **Consistency** dimension and **must
   preserve `SCORE = 100/100`** before merge. Per ADR 0002 each ships with a **failing-case pytest** and
   an entry in the CI validator list — so "one new file" is realistically ~4 touches each.

## Sequencing (load-bearing)

**Ratify ADR 0013 (effort-tier boundary) first.** It is still `Status: Proposed` and `gen_subagents.py`
still hardcodes `EFFORT_BY_MODEL = {"opus": "max", "sonnet": "max"}` (uniform `max`). The clarify gate
routes blocked tickets to an **opus-tier reviewer**; doing that before effort-tiering lands raises token
spend on every wave. Order: **(1) Founder scope-lift → (2) ratify ADR 0013 → (3) approve DAS-1416 (this
ADR, Phase 1) → warn-only wave on a pilot project → flip fail-closed.**

## Consequences

**Positive.** Closes the under-specified-dispatch gap (the 20–40% rework mode) at ticket altitude, with a
machine-enforced DoR rather than advisory prose — directly answering the research's central warning that
*a non-deterministic agent ignores an unenforced convention*. Wave-compatible by construction (front-loaded,
async, merge-able; gates fire **per-wave selection**, never per-ticket interactively). Bundles the missing
QONUN-3 CI check at near-zero marginal cost.

**Negative / accepted.** (a) Over-flagging risk — an IC could mark a hard ticket to dodge it; bounded by
the **max-3 cap**, the **circuit-breaker**, and **opus-tier reviewer routing** (the reviewer, not the
flagger, resolves). (b) Two more permanent validators on the single 100/100 release gate — recurring
maintenance load, accepted as the price of enforcement. (c) The warn-only → fail-closed rollout means one
wave of non-blocking noise before the gate bites — accepted as the safe-rollback cost.

**Explicitly NOT adopted** (rejected spec-kit surface): the `specify` CLI / `uv`·`uvx` / `.specify/` tree /
`/speckit.*` commands (collide with `/daslab-*`, violate DRY/QONUN); a standalone `constitution.md` (4th
constitution = the discussion #2476 DRY trap; would trip `check_precedence.py`); repo-root `specs/NNN-*/`
folders (collide with the Project Placement Law); per-feature `SPEC.md` + `FR-NNN`/`SC-NNN` + an `analyze`
validator (deferred to a future, **size-gated** ADR for non-design-driven goals only — redundant for
qaqnuz, which already has `design/screens/**/*.pen` 1:1 with its tickets); the `converge` ceremony
(its drift problem is spec-kit's own unsolved defect); any **per-wave** (vs per-goal/per-epic) gating
(would serialize the wave model).

**Law check.** QONUN-1 (no project files moved — org-engine files only; project specs, if ever added by a
later ADR, land under `projects/<slug>/`). QONUN-3 (**strengthened** — adds the missing CI assertion; this
ADR's own ticket honours it via `status: backlog` + `approval: human:founder`). QONUN-4 (no model/effort
re-tier — clarify routing rides existing roles; effort stays per ADR 0013). QONUN-5 (this is a
`governance_or_policy` change → **must not** be `approval: auto*`; markers also tighten recall scoping).
ADR 0006 (the static cache prefix is byte-identical — markers live in the volatile per-ticket tail;
`check_cache_prefix.py` unaffected). The binding `ai-agent-lifecycle.md` policy text is **untouched**; this
ADR is additive (ADR + validators + skill sub-steps). Any future change to that binding text would require
**Board ratification**, out of scope here.

## Enforcement / acceptance (handed to DAS-1416)

- `docs/adr/0014-native-clarify-gate.md` authored (this file) + **CTO-ratified**; ADR README index entry
  added **only on ratification** (Proposed ADRs are not indexed — matches the ADR-0013 precedent).
- `scripts/check_clarifications.py` + failing-case pytest; **warn-only first**, then fail-closed.
- `scripts/check_approved_goal_queue.py` + failing-case pytest.
- `.claude/skills/daslab-cycle/SKILL.md` Step 3: skip unresolved-marker tickets, count `clarify-blocked`,
  `todo` → author's reviewer per `ROUTING.md`, never a code subagent; circuit-breaker on the threshold.
- `.claude/skills/daslab-plan/SKILL.md`: emit markers instead of guessing under-specified scope.
- Both validators registered in `scripts/diagnostics.py`; `SCORE = 100/100` preserved before merge.
- ArcRift `store_memory` (project=`daslab`): record that ADR-0014 grafts the ticket-altitude Clarify gate
  and rejected the spec-kit CLI (drift + serialization vs parallel waves).

## References

- GitHub Spec Kit (`github/spec-kit`), MIT, v0.11.x — README + `spec-driven.md` (SDD manifesto).
- GitHub Blog — "Spec-driven development with AI: get started with a new open-source toolkit".
- Spec-drift / no-update defect: spec-kit issue #1191. Constitution-vs-CLAUDE.md DRY tension: discussion #2476.
- Independent eval (2.77/5) + ~10× overhead: Scott Logic; ranthebuilder.cloud; augmentcode.com.
- DasLab diagnostic workflow (2026-06-26): 14-agent fan-out, two adversarial reviewers converged on this
  single graft as spec-kit's only genuinely-additive idea for DasLab.
