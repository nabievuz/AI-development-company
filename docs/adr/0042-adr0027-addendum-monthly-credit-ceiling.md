# ADR 0042 — Addendum to ADR-0027 SI-5: the monthly subscription credit ceiling is an OUTER cap, measured over the UTC calendar month, and exhaustion is an `idle` carrying a `sanctioned_pause` reason — never a fourth decision action

- **Status:** Accepted (**CTO — decider and ADR ratifier; RACI 3.1 A — 2026-07-24**)
- **Date:** 2026-07-24
- **Scope:** Platform / org-engine — an **addendum to [ADR-0027](0027-scheduler-safety.md) SI-5** (read through SI-7). It records, as the binding contract, the monthly subscription credit ceiling that MUSTAQIL WS-F wired into the `--tick` path. It ships **no runtime change**: the code it ratifies already landed (DAS-1618) and is unchanged by this document.
- **Deciders:** **CTO (accountable)** — ADR ratifier (RACI 3.1: IC authors, MGR reviews, CTO ratifies). SRE Lead consulted (author of the WS-F verification design and of the review that surfaced the window defect); COO consulted by reference (GATE-6 Maintenance Accountable, unchanged from ADR-0027).
- **Relates:** [ADR-0027](0027-scheduler-safety.md) SI-5 / SI-7 (the amended-by-reference invariants); [`docs/specs/010-mustaqil-ws-f-tempo/SPEC.md`](../specs/010-mustaqil-ws-f-tempo/SPEC.md) **FR-004**; [`docs/design/ws-f-tempo-verification.md`](../design/ws-f-tempo-verification.md) §3 (the design this ratifies the *implementation* of); [`docs/runbooks/heartbeat-go-live.md`](../runbooks/heartbeat-go-live.md). Shipped enforcement points: `scripts/loop_controller.py` (`_window_start`, `_monthly_credit_exhausted`, `tick`), `scripts/flow_router.py` (`_dispatch_blocked`, `DECISIONS`), `scripts/check_heartbeat_readiness.py` (`assess`, `_active_plan`), `scripts/cost/cost_ledger.py` (`aggregate_spans(since=…)`), `scripts/ws_b_admission.py` (`load_mustaqil_budgets`, `check_credit_exhaustion` — the sole credit accountant), `config/budgets.yaml` (`mustaqil.monthly_credit_ceiling`).
- **Supersedes / Amends:** **supersedes nothing.** This is an **addendum**: it EXTENDS ADR-0027 SI-5 by reference and is read as part of it. ADR-0027 is **not edited in place** — it stays `Accepted`, its decision stands unchanged, and its invariant numbering stays exactly **SI-1…SI-7**. This addendum introduces **no new top-level invariant**; its clauses are numbered **SI-5.1…SI-5.6** to make their subordination structural. Per the append-only ADR rule (README), an extension to an accepted record is a new numbered ADR that references it, never a rewrite of the original.

> **Why this exists.** ADR-0027 SI-5 named only `caps.per_run` and `caps.per_day`. The Claude-subscription **monthly credit** — the real outer bound on what an unattended substrate can spend — arrived later (DAS-1543 budgets, asserted by SPEC-010 FR-004). The CTO's standing call at WS-F GATE-1 was that this is an **extension, not a contradiction**, so ADR-0027 was deliberately left unamended through GATE-1 and GATE-2 while the shape was still a design. The wiring has now landed and been reviewed twice. This addendum is the clean record: the binding contract now **matches** the enforced behavior instead of trailing it.
>
> **Ratified against the shipped code, not the design document.** Every clause below was checked against the merged implementation named in *Relates*; where the design and the code differ, the code is what is written down here (§Reconciliation).

## Context

`config/budgets.yaml` declares `mustaqil.monthly_credit_ceiling` — `plan_credit_usd`
per plan, `on_exhaustion: sanctioned_pause`, `metered_overflow: false` — and calls it,
in its own comment, "the OUTER ceiling". It was enforced only on the WS-B admission
path. The heartbeat's `--tick` dispatch path never read it: SI-5 in the tick was
per-run + per-day only, so the substrate's own hard dispatch ceiling was missing the
one bound that actually stops the money.

DAS-1618 closed that gap by calling the existing accountant from three sites (tick
adapter, router clause, readiness gate). Its first implementation contained a defect
that is the reason this addendum is written the way it is, and is worth stating
plainly because the failure mode is counter-intuitive:

**A monthly limit was compared against a *lifetime* spend total.** A lifetime total is
monotonic non-decreasing. Once it crossed the ceiling it could never fall back below
it. The tick would therefore have latched at `idle` **permanently** — and because
SI-7's go-live gate requires a **≥ 3-day clean shadow window** that only accumulates
while ticks keep evaluating, a permanent latch makes go-live **structurally
unreachable**. A safety rail that can be entered but never exited is not a safety
rail; it is an outage with a governance justification. The defect was caught in
review and fixed before merge (`_window_start` + `aggregate_spans(since=…)`), and
`tests/test_loop_controller.py` carries an explicit regression test that reproduces
the pre-fix behavior.

The root cause was not carelessness. It was that **SI-5 named ceilings without
naming the window they are measured over** — an omission an implementer can only
resolve by guessing. §SI-5.2 exists so that guess is never available again.

**AADL stage.** A GATE-1/GATE-3 record for MUSTAQIL WS-F: the decision doc catching
up to shipped, reviewed code. No runtime change, no flag moved.

## Decision

**The monthly subscription credit ceiling is a binding part of ADR-0027 SI-5: an
OUTER cap that sits alongside — never in place of — the per-run and per-day caps.
Spend against it is measured over the UTC calendar month with an inclusive start
boundary. Exhaustion blocks `dispatch` only, produces the action `idle` with
`sanctioned_pause` as a *reason*, and is never an error.**

### SI-5.1 — The ceiling is an OUTER cap, alongside the per-run/per-day caps

`mustaqil.monthly_credit_ceiling.plan_credit_usd[active_plan]` is a third dispatch
ceiling, evaluated in addition to `caps.per_run` and `caps.per_day`. It **does not
replace, relax, widen, or subsume** either of them, and they do not subsume it: the
**tightest binding constraint wins**, and any one of the three blocking is sufficient
to withhold a dispatch. Concretely, `loop_controller.tick()` computes
`_per_day_budget_exceeded(...)` and `_monthly_credit_exhausted(...)` independently and
passes both into the router, which has one clause for each.

- **One accountant, no second one.** "Is the monthly credit exhausted" has exactly one
  implementation: `ws_b_admission.check_credit_exhaustion`. `loop_controller`
  `_monthly_credit_exhausted` is a **thin adapter with no arithmetic of its own** — it
  loads the `mustaqil:` block and calls that function. This is ADR-0027's
  "**activate, don't duplicate**" rule applied to the new ceiling.
- The adapter deliberately does **not** route through `ws_b_admission.admit()` (which
  fails closed on the per-tick-absent `model`) or `gated_admit()` (gated on the
  unrelated `ws_b_agent_sdk_runner` flag). A safety rail that silently vanishes when
  an unrelated feature flag is OFF is not a safety rail.
- **`metered_overflow` stays OFF and unreachable from the tick.** No parameter, kwarg,
  CLI flag, or environment variable on the heartbeat path may enable overflow.
  Flipping it is a Founder-only `config/budgets.yaml` edit.
- Exhaustion is evaluated as `used_usd >= limit` (`check_credit_exhaustion`): the
  ceiling binds **at** the limit, not only past it. An **unknown plan is fail-safe
  inert** (`None`, never a fabricated exhaustion).

### SI-5.2 — The window: the UTC calendar month, start boundary INCLUSIVE (the clause that must not be ambiguous)

**This is the most important clause in this document.** Every spend figure SI-5
compares against a ceiling is a **windowed** total over a **UTC calendar window** —
**never a lifetime total**.

For the monthly credit ceiling the window is:

> **`[ first instant of the UTC calendar month containing the evaluation instant , the evaluation instant ]`**

stated exhaustively, so no implementer has to infer any part of it:

1. **Lower bound = `YYYY-MM-01T00:00:00.000000` UTC, and it is INCLUSIVE.** A span whose
   `created_at` equals that instant exactly **is counted in the window**. The shipped
   filter is `if ts is None or ts < since: continue` — strictly-less-than, so equality
   is retained (`cost_ledger.aggregate_spans`). `loop_controller._window_start(now,
   unit="month")` returns precisely that instant (`day=1, hour=0, minute=0, second=0,
   microsecond=0`).
2. **Timezone is UTC, always.** `_window_start` normalises an aware datetime to UTC and
   then strips `tzinfo`, yielding the naive-UTC convention that
   `cost_ledger._parse_created_at` produces, so the boundary and the span timestamps
   are directly comparable. There is no local-time, no operator-timezone, and no
   billing-timezone reading of "month".
3. **The window is anchored to the evaluation instant `now`, which is threaded
   explicitly, not read from the wall clock deep inside the aggregator.**
   `tick(now=…)` resolves `_now` once and passes it to
   `_monthly_credit_exhausted(..., now=_now)`, which passes it to `_window_start`. A
   tick is therefore a pure, reproducible function of its inputs — the same inputs
   yield the same decision, and a test can pin the month.
4. **The window ROLLS, and resetting at the boundary is the load-bearing property.**
   Spend from a previous billing month is excluded. Crossing the ceiling in one month
   must not carry into the next. This is what makes the ceiling a *pause* rather than
   a *latch* (§Context).
5. **Upper bound, as shipped:** the filter applies the **lower bound only**, so the
   effective upper bound is unbounded. This is equivalent to "the evaluation instant"
   given `created_at` is stamped at emit time and is never in the future; a
   hypothetical future-dated span would be counted in the current month's total.
   Recorded here as shipped behavior rather than smoothed over.
6. **The same rule binds every SI-5 spend ceiling, not just this one.** The per-day cap
   is "the UTC calendar day, start boundary inclusive", by the same
   `_window_start(now, unit="day")` primitive — **one** windowing mechanism, not two
   divergent ones. The shipped `_per_day_budget_exceeded` still aggregates
   **lifetime** and therefore does not yet satisfy this clause; that is a known,
   separately-ticketed defect (**DAS-1632**), named here rather than papered over.

**A ceiling stated without its window is an unfinished ceiling.** Any future spend
ceiling added anywhere in the substrate MUST name its window and its boundary
inclusivity in the same breath as its limit, and MUST obtain the window from
`_window_start` rather than deriving one privately.

### SI-5.3 — On exhaustion the action is `idle`; `sanctioned_pause` is a REASON, never a fourth action

The decision on exhaustion is **`idle`**, carrying the deterministic reason string
`"monthly subscription credit exhausted — sanctioned pause (SI-5/FR-004)"`.

**`flow_router.DECISIONS` remains exactly the closed alphabet
`{dispatch, validate, idle}`.** This is not a style preference and this addendum is
**not** licence to widen it. The closed alphabet **is** SI-7's never-auto-approve
enforcement: because no `approve` / `answer` / `sign` action can be *represented*, the
router structurally cannot sign a gate or answer an interrupt-card. Adding a fourth
action — `paused`, or any other — would widen the very set whose narrowness is the
guarantee, trading a structural property for a runtime check. **Forbidden.** It is
asserted by `kill_switch_drill.decision_alphabet_is_closed()` and
`tests/test_flow_router.py::TestDecisionAlphabet`.

`on_exhaustion: sanctioned_pause` in `config/budgets.yaml` is therefore a **reason
label**, surfaced in prose and in the `safety_rails` output — never an action value.

### SI-5.4 — Blocks `dispatch` only, never `validate`; and it is never an error

- **Dispatch only.** The clause lives in `flow_router._dispatch_blocked`, which is
  consulted **only** for a tentative `dispatch`. A `validate` decision is never
  withheld by credit exhaustion. Validation is read-only and free; blinding the org's
  validators exactly when its budget is stressed would be the opposite of safe. This
  follows the quiet-hours precedent already asserted in `tests/test_scheduler.py`.
- **Never an error.** Exhaustion must not raise, must not exit non-zero, and must not
  be recorded as a failure. `--tick` still exits 0. It is "an expected idle, like a
  gate" (`config/budgets.yaml`, verbatim) — and equally never a **false green**: the
  tick states plainly *why* it idled, surfacing `monthly_credit_exhausted` in the
  returned `safety_rails` dict and in `_print_tick`'s rail block, in **shadow mode
  too**. The ceiling must be observable in the shadow window before it can be trusted
  live.
- **Never a fabricated pause.** Every failure path in the adapter — missing file,
  absent YAML, import error, unknown plan — is isolated to `False`. A fabricated
  exhaustion would freeze the tick at `idle` and is treated as exactly as damaging as
  a false green (§Context).

### SI-5.5 — The `active_plan` resolution: inert in the tick, blocking at the readiness gate

`config/budgets.yaml` declares the credit **per plan** but not **which plan is
active**. Three resolutions were available; the shipped one is the third:

1. **Inherit `CreditState`'s dataclass default (`plan="max_20x"`)** — rejected. Silently
   assuming the most generous plan under-reports exhaustion on a smaller plan; the
   ceiling would read as unbreached while real credit ran out.
2. **Fail closed in the tick** (treat an undeclared plan as exhausted) — rejected, and
   this is the subtle one. It looks like the conservative choice and is in fact the
   damaging one: every tick would idle, the ≥ 3-day clean shadow window (SI-7) would
   never accumulate, and the go-live gate the ceiling exists to protect would become
   permanently unreachable. **A false red that freezes the substrate is as damaging as
   a false green** — it is the same permanent-latch failure as the lifetime-total
   defect, arrived at from the other direction.
3. **Inert in the tick, blocking at the readiness gate — adopted.** With no declared
   plan and no injected `credit_state`, `_monthly_credit_exhausted` returns `False`
   (the tick keeps evaluating and the shadow window keeps accumulating), while
   `check_heartbeat_readiness.assess()` treats an unenforceable ceiling as a
   **readiness blocker**: `ready = (not flag_on) and window_met and
   credit_precondition_met`, with two distinct blocker strings for the two distinct
   conditions (`active_plan is undeclared` vs `credit exhausted`).
   `_active_plan()` never guesses a plan; absent/malformed reads to `None`.

Net effect, and the reason this is the right shape: **the heartbeat can never be
declared READY while its outer ceiling is unenforceable, and it is never frozen by an
unconfigured one.** The two properties are obtained at the two different seams where
each is correct — evidence accumulation in the tick, gate strictness at the gate.

As of this ratification `mustaqil.monthly_credit_ceiling.active_plan` is **absent**
from `config/budgets.yaml`, so readiness correctly reports NOT READY on that ground.
Declaring it is a fact about the Founder's subscription, not about the repository, and
is tracked by **DAS-1629** (`blocked` on Founder input by design). No agent may infer
it.

### SI-5.6 — A record with a missing or unparseable `created_at` is EXCLUDED from the window

Once a window is applied, `aggregate_spans` skips any span whose `created_at` is
missing or does not parse (`ts is None` takes the same branch as `ts < since`).

**Why exclusion is correct, and inclusion is not.** An undated span belongs to **no**
window. Counting it "to be safe" would add it to the total of **every** window —
this month, next month, and every month after — because nothing ever ages it out.
That is a monotonic non-decreasing component inside a total that must be able to fall
back to zero: it **reintroduces exactly the permanent-latch failure** the windowing
was introduced to remove (§Context). Undated records are excluded so that the window
means what it says.

**The residual this creates is real and is named, not hidden.** An excluded span is a
span whose spend is invisible to the ceiling (the cap under-counts — it fails
**open**) and whose wave is invisible to the clean-day evidence, with **no error, no
warning, and no dropped-record count** anywhere. The correct fix is not to count
undated records but to make undated records impossible: pin one `created_at` format
contract at the emitting seam and reconcile it with every consumer. That is tracked as
**DAS-1633** and is deliberately not resolved inside this addendum, because fixing it
at one seam is what makes this class of bug survive.

## Reconciliation — shipped code vs. DAS-1617's design

Checked clause by clause against the merged implementation. **No divergence requiring
a bounce back to DAS-1618 was found.** Three differences from the design text, all
resolved in favour of the code:

| Design (`ws-f-tempo-verification.md` §3) | Shipped | Verdict |
|---|---|---|
| §3.3 signature `_monthly_credit_exhausted(budgets_path, credit_state=None)` | `(budgets_path, events_path, credit_state=None, *, now=None)` | **Code wins — a strict improvement.** The extra parameters are what implement §3.5's "same reader, different window" and make the window injectable/testable. No arithmetic was added; the adapter still holds none. |
| §3.5 "DAS-1618 must also add `mustaqil.monthly_credit_ceiling.active_plan` to `config/budgets.yaml`" | Not added; key still absent | **Correctly NOT done.** The design itself states the live plan's terms are "not resolvable by any agent". Routed to **DAS-1629** (`blocked`, Founder). The readiness gate blocks on it, so the omission is loud, not silent. |
| SI-5 / FR-004 "idle **+ alert**" (`on_breach: idle_and_alert`, "breach → `scripts/alerting.py`") | `loop_controller.tick()` calls `alerting.sanctioned_pause_alert(budget_exceeded, credit_exhausted)` **after** the decision is finalized and adds only `result["alert"]` — covering **both** the pre-existing per-day cap and the monthly ceiling (DAS-1634) | **Limb WIRED and verified — recorded here by DAS-1642** *(this row, ratified 2026-07-24 against DAS-1618, read as an open residual; DAS-1634 has since landed the limb and it is re-checked against the shipped code below)*. `sanctioned_pause_alert` returns `dict \| None`, severity **`info`**, metric **`SI-5`** — outside `filter_quiet`'s `{warning, critical}` ANOMALY set, so Quiet Mode and `--fail-on-critical` (CI) never confuse a sanctioned pause with a breach or an unexpected stall. It is **observation-only**: computed AFTER `decision` (loop_controller.py `tick`, lines ~484–498 then ~516–520), failure-isolated to `alert=None`, and adds **no fourth action** — `flow_router.DECISIONS` stays the closed `{dispatch, validate, idle}` (§SI-5.3 intact; the alert reads the same two booleans `route_from_store` already consumed and never alters the decision). The alert is **emitted in-band** on the tick surface (`result["alert"]`) and printed by `_print_tick`; a persistent / monitored sink **outside** `tick()` is deliberately **deferred (DAS-1643)**. This row records the limb as wired and emitted in-band — **not** end-to-end delivery. |

Verified present in the shipped code and consistent with every clause above:
`_window_start` (month/day, inclusive start, UTC-normalised, `ValueError` on any other
unit); `aggregate_spans(..., since=)` with `since=None` preserving lifetime behavior
for every existing caller; the single `_dispatch_blocked` clause positioned between
the SI-5 per-day and SI-6 in-flight clauses (deterministic reason ordering);
`DECISIONS` unchanged; `assess()`'s two distinct blocker strings; and the
`tests/test_loop_controller.py` regression test that reproduces the pre-fix
lifetime-window behavior.

## Consequences

**Positive.**
- The binding contract now **matches enforced behavior**. "Does the heartbeat honor the
  monthly credit ceiling, and over what window?" resolves to a citation instead of a
  code-reading exercise.
- The window ambiguity that produced the defect is closed by construction: SI-5.2 names
  the boundary, its inclusivity, its timezone, its anchor, and the single mechanism
  (`_window_start`) that must produce it. The same mistake now requires contradicting a
  written invariant rather than filling a silence.
- SI-7's structural guarantee is **restated as a prohibition** in the same document that
  adds a new blocking condition — the moment at which someone would most plausibly reach
  for a fourth action.
- Both permanent-latch shapes (lifetime totals; fail-closed-on-undeclared-plan) are
  written down with their mechanism, so "conservative" is never confused with "safe".

**Negative / accepted.**
- Named residuals remain open — the per-day lifetime window (**DAS-1632**) and the
  silent drop of undated spans (**DAS-1633**), plus the undeclared `active_plan`
  (**DAS-1629**, Founder-gated). The SI-5 alert limb, recorded above originally as an
  open residual, is now **wired and verified (DAS-1634)**: `loop_controller.tick()`
  emits `alerting.sanctioned_pause_alert` (severity `info`, metric `SI-5`) as an
  observation alongside the `idle` decision, adding no fourth action. What remains of
  that limb is a **persistence residual, separately ticketed (DAS-1643)**: the alert is
  emitted **in-band** on the tick surface and printed by `_print_tick`, but nothing yet
  routes it to a monitored sink outside `tick()` — parity with the rest of the
  trigger-gated alerting surface, not end-to-end delivery. **Accepted and recorded**: an
  addendum that documented any of these as solved would be precisely the false-green
  ADR-0020 forbids. Readiness correctly reports NOT READY.
- ADR-0027's invariant contract is now spread across two files. **Accepted** — the
  append-only rule makes that the correct cost; SI-5.1…SI-5.6 are numbered as
  subordinate clauses so the relationship is unambiguous, and ADR-0027's README row and
  theme paragraph point here.
- The ceiling is only as good as the cost-ledger's coverage; under-counted spend means an
  under-enforced ceiling. **Accepted** — it fails open in the direction of not fabricating
  a pause, and the coverage gap is DAS-1633, not a silent assumption.

**Law check.**
- **Charter / RACI** — the CTO is the ADR ratifier (RACI 3.1 A). Ratified by the CTO;
  SRE Lead consulted as the design/review author. No policy amended; ADR-0027 extended
  by reference, not edited.
- **AADL** — a decision record for MUSTAQIL WS-F. No gate skipped, no gate signed, no
  stage asserted complete. Ships no runtime change.
- **Never-auto-approve (QONUN-5)** — reinforced, not relaxed: SI-5.3 forbids widening the
  decision alphabet; `heartbeat_enabled` is untouched and its flip stays a Founder act
  (SI-7, FR-006); `metered_overflow` stays OFF and Founder-only; `active_plan` is a
  Founder declaration no agent may infer.
- **Board / governance-as-policy** — no SSOT edited in place. `config/budgets.yaml`,
  `config/features.yaml`, `config/loop.yaml`, and ADR-0027 itself are all unmodified by
  this document; it adds one ADR file and one `docs/adr/README.md` ledger row.
- **Project placement** — a platform-level ADR under `docs/adr/`; no project artifact
  written; the ticket carries no `project:` field.
- **Model allocation** — unchanged; CTO on opus per the table.

## Enforcement / acceptance

- This addendum is `Accepted` on ratification and is **read as part of ADR-0027 SI-5**.
  ADR-0027 keeps its `Accepted` status, its decision text, and its SI-1…SI-7 numbering.
- Already-passing evidence for the clauses above (re-run, not asserted):
  - **SI-5.1 / SI-5.2** — `tests/test_loop_controller.py`: `_window_start` unit/boundary
    tests, the D1 regression test reproducing the pre-fix lifetime behavior, the
    current-month-counts and mixed-months-only-current-counts tests, and the
    "does not inherit `max_20x` default" test.
  - **SI-5.3** — `tests/test_flow_router.py::TestDecisionAlphabet` and
    `kill_switch_drill.decision_alphabet_is_closed()`; plus
    `test_monthly_credit_exhausted_is_a_reason_never_a_fourth_action`.
  - **SI-5.4** — `test_monthly_credit_exhausted_never_blocks_validate`,
    `test_monthly_credit_exhausted_never_raises_or_errors`, and
    `test_tick_surfaces_monthly_credit_exhausted_rail`.
  - **SI-5.5** — `scripts/check_heartbeat_readiness.py` reports the ceiling line and its
    blocker; it currently reports NOT READY (undeclared `active_plan`, insufficient clean
    window).
  - **SI-5.6** — `aggregate_spans`'s `ts is None` exclusion branch and its windowing tests.
- Any future "may the heartbeat dispatch past an exhausted credit ceiling / add a fourth
  decision action / measure spend over a lifetime total / assume a plan?" question
  resolves to **no** by SI-5.1…SI-5.6 read with ADR-0027 SI-5/SI-7. An undeclared
  autonomy is not in the envelope — so it is not permitted.
