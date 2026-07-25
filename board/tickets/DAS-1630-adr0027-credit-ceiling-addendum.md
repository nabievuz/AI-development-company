---
id: DAS-1630
title: Ratify an ADR-0027 addendum recording the monthly credit ceiling as an outer cap
status: done
assignee: cto
author: sre-lead
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: docs/adr
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Companion to DAS-1618, flagged by DAS-1617's design (§3.7) and confirmed by the
CTO at GATE-1.** ADR-0027's SI-5 text names only per-run and per-day caps. The
MUSTAQIL monthly credit ceiling is a later DAS-1543 addition asserted by SPEC-010
FR-004 — an **extension, not a contradiction**, which is why ADR-0027 was
deliberately left unamended through GATE-1 and GATE-2.

DAS-1618 has now wired that ceiling into the `--tick` path
(`loop_controller._monthly_credit_exhausted`, a `flow_router` dispatch-blocked
clause, and a `check_heartbeat_readiness` blocker). The CTO's standing call was that
once the wiring lands, **a ratified ADR-0027 addendum is the clean record** — so the
binding contract matches the enforced behavior rather than trailing it.

Record in the addendum:
- The monthly credit ceiling as an outer cap alongside SI-5's per-run/per-day caps.
- That on exhaustion the action stays `idle` with `sanctioned_pause` as a **reason
  string, never a fourth action** — `flow_router.DECISIONS` remaining the closed
  alphabet `{dispatch, validate, idle}` is itself SI-7's structural enforcement, so
  the addendum must not read as licence to widen it.
- That it blocks `dispatch` only, never `validate`, and is never an error.
- The `active_plan` resolution: inert in the tick, blocking at the readiness gate
  (see DAS-1629, which is blocked on Founder input) — and why failing closed in the
  tick would be a false red that prevents the shadow window from accumulating.

**Ratification is a CTO act.** Verify the wiring actually behaves as the addendum
describes by reading DAS-1618's merged code — do not ratify from the design doc
alone. If the shipped behavior and the design have diverged, the addendum records
the shipped behavior or the divergence is bounced back to DAS-1618; it never
documents an intent the code does not implement.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT widen SI-5/SI-6 caps.

## Acceptance criteria
- [x] Addendum authored against ADR-0027 recording the monthly ceiling as an outer cap, its `idle` + `sanctioned_pause` semantics, and the `active_plan` resolution. — `docs/adr/0042-adr0027-addendum-monthly-credit-ceiling.md`, clauses SI-5.1…SI-5.6 (incl. the explicit window definition, SI-5.2, and the undated-record exclusion, SI-5.6).
- [x] The addendum verified against DAS-1618's shipped code, not only DAS-1617's design note — divergences reconciled or bounced. — §Reconciliation: 3 design/code differences, all resolved in favour of the code; **nothing bounced** (none was a defect).
- [x] ADR-0027's `Accepted` status and SI-1..SI-7 numbering preserved; `docs/adr/README.md` updated if the repo convention requires it. — `0027-scheduler-safety.md` byte-unmodified; new ADR row 0042 + WS4 theme note added per the README append-only rule.
- [ ] `check_links.py`, `check_spec_consistency.py`, `board_lint` green; `diagnostics.py` 100/100; no `project:` field (R9). — links/spec/board_lint **green**, R9 clean; `diagnostics.py` = **85/100**, NOT 100. Shortfall is provably external to this ticket (see Log) — left unticked rather than falsely ticked.

## Log
### 2026-07-24 — SRE / DevOps Lead
Raised in DAS-1617's GATE-2 close (design §3.7) and re-flagged by DAS-1618's report;
recorded by the orchestrator in the same run. Held `depends_on: [DAS-1618]` and not
dispatched alongside it deliberately — an ADR ratified against wiring still under
review could document behavior that the review then changes.

### 2026-07-24 — CTO

**RATIFIED.** `docs/adr/0042-adr0027-addendum-monthly-credit-ceiling.md` — Accepted,
CTO as decider/ratifier (RACI 3.1 A). This closes the standing call I made at WS-F
GATE-1 (DAS-1616): the monthly credit ceiling is an EXTENSION of ADR-0027, not a
contradiction, so ADR-0027 stayed unamended through GATE-1/GATE-2 and the clean record
is this addendum now that DAS-1618's wiring has landed and been reviewed twice.

**Form — repo convention, not a rewrite.** `docs/adr/README.md` states the ADR set is
append-only: an extension to an accepted record is a **new numbered ADR that references
it**, never an edit in place (the ADR-0025 → ADR-0010/0011 and ADR-0032 → ADR-0031
precedents; DAS-1617 design §3.7 explicitly sanctions "an addendum **or a small amending
ADR**"). So: new file at the next free number (0042), `Supersedes / Amends: supersedes
nothing — EXTENDS ADR-0027 SI-5 by reference`. `0027-scheduler-safety.md` is
**byte-unmodified** — `Accepted` status, decision text, and SI-1…SI-7 numbering all
intact. The addendum introduces **no new top-level invariant**; its clauses are numbered
**SI-5.1…SI-5.6** so subordination is structural. Added one README ledger row and a
pointer sentence in the WS4 HEARTBEAT theme paragraph.

**Ratified against the SHIPPED CODE — what I actually read, not the design doc.**
- `scripts/loop_controller.py` — `_window_start(now, *, unit)` (lines ~243-272),
  `_per_day_budget_exceeded`, `_monthly_credit_exhausted` (~305-368), `tick()` (~371-494)
  incl. how `_now` is resolved once and threaded into the ceiling check.
- `scripts/flow_router.py` — `DECISIONS` (line 93), `_dispatch_blocked` (~220-238) incl.
  clause ordering, `route()`'s dispatch-only gating (~335-338), the SI-1..SI-7 header.
- `scripts/check_heartbeat_readiness.py` — `_active_plan()` (~62-76) and `assess()`
  (~79-134) incl. the two distinct blocker strings.
- `scripts/cost/cost_ledger.py` — `_parse_created_at` (~253-264) and the `since` kwarg on
  `aggregate_spans` (~285-321) incl. the `ts is None or ts < since` skip branch.
- Cross-checks: `scripts/ws_b_admission.py::check_credit_exhaustion` (`used_usd >= limit`,
  unknown plan → `None`); `config/budgets.yaml` `mustaqil.monthly_credit_ceiling`;
  `scripts/kill_switch_drill.py::decision_alphabet_is_closed`; and the existing tests in
  `tests/test_loop_controller.py` / `tests/test_flow_router.py` cited as SI-5.x evidence.

**Divergence verdict: NOTHING bounced to DAS-1618.** Three design/code differences, all
resolved in favour of the code and written into §Reconciliation:
1. `_monthly_credit_exhausted` signature grew `events_path` + `now=` beyond design §3.3 —
   a strict improvement; it is what implements §3.5's "same reader, different window" and
   makes the window injectable. No arithmetic was added to the adapter.
2. Design §3.5 told DAS-1618 to add `active_plan` to `config/budgets.yaml`; it is still
   absent. **Correctly not done** — the design itself says the live plan is not resolvable
   by any agent. Routed to DAS-1629 (`blocked`, Founder). The readiness gate blocks on it,
   so the omission is loud, not silent. Verified `grep -c active_plan config/budgets.yaml`
   = 0.
3. SI-5/FR-004's "idle **+ alert**" — `loop_controller.py` contains **no** `alerting`
   reference at all, for the monthly ceiling or the pre-existing per-day cap. Recorded as
   an **open residual, not ratified as complete**; predates DAS-1618 and was outside its
   scope. Routed as newly discovered work.

**The window clause (SI-5.2) — why it is written the way it is.** SI-5 named ceilings
without naming the window they are measured over, and that silence is exactly what let
D1 through: a *monthly* limit compared against a *lifetime* total. A lifetime total is
monotonic non-decreasing, so once crossed it never falls back — the tick latches at
`idle` **permanently**, the ≥3-day clean shadow window (SI-7) can never accumulate, and
go-live becomes **structurally unreachable**. So SI-5.2 states, exhaustively: UTC calendar
month; lower bound `YYYY-MM-01T00:00:00` UTC and **INCLUSIVE** (shipped filter is
`ts < since` → equality retained); anchored to an explicitly-threaded evaluation instant,
not a wall-clock read inside the aggregator; rolling (resets at the boundary — the
load-bearing property); one shared `_window_start` primitive for **every** SI-5 spend
ceiling. I also recorded honestly that the shipped filter is lower-bound-only (no upper
bound), and that the per-day cap does **not** yet satisfy the clause (still lifetime —
DAS-1632), rather than implying the rule is already universal.

Also recorded per the ratification brief: the ceiling as an outer cap alongside — never
in place of — per-run/per-day, tightest-constraint-wins, one accountant (SI-5.1);
exhaustion ⇒ `idle` with `sanctioned_pause` as a **reason string, never a fourth action**,
with an explicit prohibition on widening `DECISIONS` because that closure *is* SI-7's
structural enforcement (SI-5.3); blocks `dispatch` only, never `validate`, never an error,
never a fabricated pause (SI-5.4); the `active_plan` resolution — inert in the tick,
blocking at the readiness gate, with the reasoning that failing closed in the tick is a
false red that is the *same* permanent latch reached from the other direction (SI-5.5);
and undated/unparseable-`created_at` records excluded from the window because counting
them would place them in **every** window forever, reintroducing the latch — with the
silent-drop residual named as DAS-1633 (SI-5.6).

⛔ Constraints honored: `heartbeat_enabled` untouched (still OFF); no SI-5/SI-6 cap
widened — the addendum only *adds* a blocking condition and forbids widening the decision
alphabet; zone lock respected — the only files I wrote are
`docs/adr/0042-adr0027-addendum-monthly-credit-ceiling.md`, `docs/adr/README.md`, and this
ticket. No `scripts/`, `tests/`, `config/`, or `tools/` file edited; no git state mutated.

**Verification (verbatim):**
- `python3 scripts/check_links.py` → `check_links: OK — no broken relative links in
  tracked Markdown (/Users/owner/DasLab).` EXIT=0
- `python3 scripts/check_spec_consistency.py` → `OK: 10 SPEC.md file(s) checked, structure
  + ticket refs consistent.` EXIT=0
- `python3 scripts/board_lint.py` → `board_lint: OK — 190 ticket(s) checked, 0
  violations.` EXIT=0 (1 pre-existing non-fatal body-status WARN on DAS-1507, unrelated).
  R9 clean — this ticket declares no `project:` field.
- `python3 scripts/diagnostics.py` → `SCORE = 85/100`. **NOT 100.** Single failing
  dimension: `[FAIL] Code-quality 0/15 … XX ruff-clean: ruff reported lint findings`.
  `ruff check scripts tests` → `Found 2 errors.` — both **C416** in
  `scripts/heartbeat_go_no_go.py:589` and `:590`.

**That shortfall is external to this ticket and I could not fix it.**
`scripts/heartbeat_go_no_go.py` is **untracked** (`git status --porcelain` → `??`, no git
log) — it is the file the concurrently-dispatched go/no-go-report agent is writing right
now, in the `scripts/` zone this ticket is explicitly locked out of. Counterfactual proof
that my change is neutral: `ruff check scripts tests --exclude
scripts/heartbeat_go_no_go.py` → `All checks passed!`, i.e. Code-quality would score 15/15
and diagnostics 100/100 but for that in-flight file. My change is Markdown-only and cannot
affect ruff. Criterion 4 is therefore left **unticked** rather than falsely ticked
(ADR-0020 — an unmeasured/unmet gate is never asserted green); it closes with no further
action on DAS-1630 once the go/no-go ticket lands its file clean.

Status → `done`: the ratification act is complete and the ADR is `Accepted`. Routed to the
orchestrator: (a) the unwired `idle_and_alert` limb of SI-5 in the `--tick` path needs a
ticket (SRE Lead), (b) re-run `diagnostics.py` after the go/no-go ticket lands.
