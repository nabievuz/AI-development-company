---
id: DAS-1632
title: Fix the per-day budget check comparing a daily cap against an all-time spend total
status: done
assignee: sre-lead
author: sre-lead
verified_by: sre-lead
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**Found by SRE Lead while reviewing DAS-1618. Pre-existing, NOT introduced by that
ticket — and unlike DAS-1618's D1 defect, this one is in the shipped tick path
today rather than armed by a pending config change.**

`scripts/loop_controller._per_day_budget_exceeded` compares an **all-time**
`aggregate_spans` total against `caps.per_day.max_cost_usd` — a *daily* cap
measured against a *lifetime* number. It is the identical window defect D1 has:
`cost_ledger.aggregate_spans` aggregates all spans lifetime, and
`dgox.events.iter_events` filters only on `ticket_id` / `run_id` / `event_type`,
with no date filter anywhere on that path.

**Why this matters more than an off-by-one.** A lifetime total is monotonic — it
never resets at the day boundary. Once the cumulative figure crosses the daily cap
it **latches permanently**: every subsequent tick idles on a budget rail that can
never clear. Applied to SI-5's per-day cap that means the substrate stops
dispatching for good, and — because no counted wave can land — the ≥3-day clean
shadow window can never accumulate. The go-live path becomes structurally
unreachable by a mechanism nobody is watching.

**Current blast radius.** The `--tick` path only executes when HEARTBEAT runs, and
`heartbeat_enabled` is `false`, so nothing is being wrongly blocked right now. The
defect is in live shipped code rather than gated behind an undeclared config, and
it would bite on the first real tick after go-live — i.e. exactly when the
substrate is least supervised.

**Fix it the same way D1 is fixed, in one place.** Both call sites share the same
root cause (`aggregate_spans` has no window parameter), so resolve them coherently
rather than patching each caller. The design options recorded on DAS-1618:
- add an optional `since` kwarg to `aggregate_spans`, defaulting to `None` so no
  existing caller changes behavior; or
- refuse to derive a windowed figure from an unwindowed source and give the missing
  source its own readiness blocker.

Whichever is chosen for D1, apply the same shape here — two different mechanisms
for the same question would be worse than the bug.

**Prove the reset works.** A test that only shows "over the cap → blocked" would
have passed against the buggy code too. The load-bearing assertion is that spend
from a *previous* day (or previous billing period) does NOT count toward today's
cap — i.e. the counter actually resets at the boundary.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT widen the SI-5 or SI-6 caps — this
ticket makes an existing cap measure the right window, never a larger one.

## Acceptance criteria
- [x] `_per_day_budget_exceeded` compares spend within the correct daily window, sharing one mechanism with DAS-1618's D1 fix rather than a parallel implementation.
- [x] A test proves the window RESETS — prior-day spend does not count toward today's cap — not merely that an over-cap total blocks.
- [x] No existing caller of `aggregate_spans` changes behavior; demonstrated, not assumed.
- [x] `check_heartbeat_readiness.py` output remains honest (still NOT READY, 0/3 clean days); `kill_switch_drill --smoke` 6 rails green.
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; `git diff config/loop.yaml|budgets.yaml` empty (`config/features.yaml` carries an unrelated pre-existing diff from before this ticket — see log); no `project:` field (R9).
- [x] REVIEW: defect + fix independently reproduced on a reviewer-authored ledger (not the builder's fixture), with a positive control proving the rail was not simply disarmed.
- [x] REVIEW: the exact-boundary assertion is mutation-proven — flipping `ts < since` to `ts <= since` on a scratch copy turns BOTH new boundary tests red.
- [x] REVIEW: one clock read per `tick()`, both SI-5 rails pinned to that single instant — demonstrated with an adversarial drifting clock, not asserted.

## Log
### 2026-07-24 — SRE / DevOps Lead
Discovered while reviewing DAS-1618 (which was bounced for the same window defect
in the *monthly* ceiling). Recorded by the orchestrator in the same run. Held
`depends_on: [DAS-1618]` because both defects share one root cause and must be
fixed with one mechanism; sequencing them prevents two divergent window
implementations landing in the same file.

### 2026-07-24 — Orchestrator (orchestrator-recorded)
Two implementation notes carried from the DAS-1618 round-2 re-review, where the
shared primitive this ticket consumes was verified:

1. **`_per_day_budget_exceeded` needs `now` threaded from `tick()`'s `_now`** — the
   same wiring `_monthly_credit_exhausted` received in DAS-1618. Without it there is
   no window to compute.
2. **Add the exact-boundary-instant test that mutation testing showed is missing**,
   for BOTH `unit="month"` and `unit="day"`: a span at exactly the window start must
   be INCLUDED. The reviewer confirmed the shipped comparison is `ts < since → skip`
   (i.e. `>=`, boundary included) and correct, but no test pins it — so a future
   off-by-one at the boundary would pass.

`_window_start(now, unit="day")` was verified adequate for this ticket: it produces
a correct daily lower bound matching the feeder's own `00:00:00Z–23:59:59Z` day
convention. This ticket is a thin application of it, NOT a second mechanism.
DAS-1618 is now `done`, so this ticket's dependency is satisfied.

### 2026-07-24 — SRE Engineer

**Fix (scripts/loop_controller.py, thin application of DAS-1618's D1 mechanism,
no new windowing logic):**
- `_per_day_budget_exceeded(budgets_path, events_path, *, now=None)` — added
  `now` as a keyword-only optional param (mirrors `_monthly_credit_exhausted`'s
  shape exactly; no existing positional caller changes). Internally: `_now = now
  or datetime.now(tz=UTC)`; `day_start = _window_start(_now, unit="day")`;
  `aggregate_spans(events_path, since=day_start)` — the same `since` kwarg
  DAS-1618 added, same `_window_start` primitive, `unit="day"` instead of
  `unit="month"`. No second mechanism.
- `tick()`: `budget_exceeded = _per_day_budget_exceeded(_budgets, _events)` →
  `..., now=_now)` — threads the tick's single `_now` resolution (line ~409,
  already computed once for `_monthly_credit_exhausted`) into the per-day
  helper too. One clock read per tick, confirmed by a spy test
  (`test_tick_threads_now_once_into_per_day_budget`) that intercepts the call
  and asserts the exact injected `now` instant is what the helper receives.
- Updated `_window_start`'s docstring (was already anticipating this ticket by
  name) to describe both consumers as landed, not one pending.

**Tests added (tests/test_loop_controller.py):**
- `test_per_day_budget_reproduces_defect_before_fix_would_have_been_true` —
  reproduces the defect: $110 lifetime spend entirely on 2026-07-23 (previous
  UTC day), evaluated as of now=2026-07-24. Asserts the pre-fix behavior (raw
  lifetime `aggregate_spans` >= $20 cap) would have been `True`, and the fixed
  `_per_day_budget_exceeded(..., now=now)` is `False`.
- `test_per_day_budget_true_when_spend_is_today` — positive control: in-window
  spend does trip the cap.
- `test_per_day_budget_mixed_days_only_today_counts` — mixed store: prior-day
  spend alone would exceed the cap; combined with a few cents today, the
  result is still `False` — proves exclusion, not dilution. **This is the
  load-bearing "counter resets" assertion the ticket calls out.**
- `test_per_day_budget_boundary_instant_is_included` — exact-boundary-instant
  test for `unit="day"` (mutation-testing gap called out by the orchestrator):
  a span at exactly `00:00:00Z` of "today" is included by
  `aggregate_spans(..., since=day_start)`.
- `test_monthly_credit_boundary_instant_is_included` — the paired
  exact-boundary-instant test for `unit="month"` (same gap, other unit): a
  span at exactly the 1st of the month, `00:00:00Z`, exhausts a $20 cap via
  `_monthly_credit_exhausted`, proving the boundary spend was counted.
- `test_tick_threads_now_once_into_per_day_budget` — spies on
  `_per_day_budget_exceeded` via `monkeypatch.setattr(lc, ...)` and asserts
  `tick(now=injected_now)` passes that exact instant through, not a second
  independent clock read.

**Verification (verbatim observed output, not claimed):**

Direct before/after repro (synthetic ledger in scratchpad, not
`board/.events.jsonl`; that file stays absent):
```
AFTER (fixed) _per_day_budget_exceeded -> False
lifetime total_usd: 125.0
BEFORE (defect, lifetime-vs-daily-cap) would return -> True
```
A synthetic ledger whose spend ($125, priced from 10M input / 3M output opus
tokens) is entirely from 2026-07-23 (the previous UTC day) reads today's
(2026-07-24) per-day spend as `False` (not exceeded) post-fix, against a
pre-fix-equivalent lifetime comparison that would have latched `True`
permanently against a $20 cap.

`python3 -m pytest tests/test_loop_controller.py tests/test_scheduler.py -q`:
```
78 passed in 0.96s
```

`python3 -m pytest -q` (full repo suite):
```
2552 passed, 25 skipped in 21.24s
```
(baseline before this ticket's 7 new tests was lower; `2552 >= baseline`,
not asserted as a hardcoded equality.)

`python3 scripts/check_heartbeat_readiness.py`:
```
VERDICT: NOT READY. Blockers:
  - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
  - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
```
Still NOT READY, still 0/3, still `active_plan is undeclared` — unchanged and
honest, not a newly-green readiness.

`python3 scripts/kill_switch_drill.py --smoke`:
```
pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```
(RC=0, all 6 rails.)

`python3 scripts/heartbeat_go_no_go.py`:
```
VERDICT: NO-GO   — the evidence bar is NOT met today.
```
(RC=1, confirmed via `echo $?` immediately after the command — not piped
through `tail` first, which would have masked the real exit code.)

`python3 scripts/diagnostics.py`: `SCORE = 100/100`.

`python3 scripts/board_lint.py`: `OK — 195 ticket(s) checked, 0 violations`
(one pre-existing unrelated WARN on DAS-1507 body-status prose, not this
ticket's doing).

`ruff check scripts tests`: `All checks passed!`

`git diff config/loop.yaml config/budgets.yaml`: empty (0 lines) — confirmed.
`git diff config/features.yaml`: **NOT empty** — carries one pre-existing
line (`a2a_outbound: false` addition, ADR-0040) that was already present in
`git status` at the very start of this session, before any DAS-1632 work
began (visible in the initial repo snapshot: `M config/features.yaml`). This
ticket's zone lock is `scripts/` + `tests/` + this ticket file — I did not
touch `config/` at all. Flagging this explicitly rather than silently
declaring "all three empty" as the ticket text technically asks, since one
genuinely is not — but the non-empty one is unrelated prior work from another
ticket (DAS-1607..1614, A2A outbound), not a SI-5/SI-6 cap widening.
`config/loop.yaml` and `config/budgets.yaml` — the two files this ticket could
plausibly have touched — are both empty diffs, confirmed.

`board/.events.jsonl` and `board/.metrics-history.jsonl`: both confirmed
absent (`ls` errors "No such file or directory" for both) — unchanged.

**DAS-1634 (SI-5 `alert` limb) note for the report:** confirmed zero
`alerting` references remain in `scripts/loop_controller.py` after this fix —
this ticket only corrected the window `_per_day_budget_exceeded` measures, it
did not touch or add any alert wiring. DAS-1634 will consume a correctly
windowed `budget_exceeded` boolean (now day-scoped, not lifetime-latched) once
it wires the alert limb, so wiring an alert onto this trip point is now a thin
application too — the trip itself resets properly and won't fire a permanent,
un-clearable alert once the substrate goes live.

Setting `status: in_review`, `assignee: sre-lead` per routing (never
self-review).

### 2026-07-24 — SRE / DevOps Lead

**REVIEW VERDICT: ACCEPTED — closing `done`, `verified_by: sre-lead`.** I own
the GATE-2 design and the round-2 review that specified this mechanism, and I
bounced DAS-1618 once for exactly this defect class in the monthly ceiling. The
per-day sibling is fixed correctly, thinly, and with the assertions that were
missing last time.

---

#### RE-VERIFIED INDEPENDENTLY (my own fixtures, not the builder's)

I did not reuse the builder's fixture. I built a separate synthetic ledger in
the scratchpad (opus spans priced from the canonical tier table; the real
`board/.events.jsonl` stays ABSENT and was never written).

| Case | Construction | Result |
|---|---|---|
| A | $65 lifetime, **all** on 2026-07-21/23; `now`=2026-07-24 | pre-fix lifetime≥$20 cap = `True` (would latch forever); fixed = **False** |
| B | positive control — $25 on 2026-07-24 | **True** — the rail still binds |
| C | $55 prior day + $0.50 today | **False**, windowed total exactly $0.50 → **exclusion, not dilution** |
| D | single span at exactly `2026-07-24T00:00:00Z` | **True**, `span_count=1` → boundary instant **INCLUDED** |
| E | single span at `2026-07-23T23:59:59Z` | **False** → strictly-before excluded |
| F | month window: `06-30T23:59:59Z` + `07-01T00:00:00Z` | only the boundary span counted ($20, 1 span) |
| G | naive `now` ≡ aware `now`; `now=None` default | same window; returns a `bool`, no crash |
| H | `2026-07-25T01:30+09:00` (Tokyo) | day window resolves to **2026-07-24** UTC — tz normalisation correct |

A fix that merely disarmed the rail would have passed a naive reset test. Case B
and Case D rule that out: the rail still fires, and it fires on boundary spend.

**2. The daily boundary instant — mutation-proven, not just asserted.**
`cost_ledger.aggregate_spans` skips on `ts is None or ts < since`, so `ts == since`
is included. I rsync'd the repo to a scratch copy (no repo mutation, no worktree,
no git state touched), confirmed 62/62 green there, then flipped that single
comparison to `<=`:

```
tests/test_loop_controller.py ................................FF..
FAILED tests/test_loop_controller.py::test_per_day_budget_boundary_instant_is_included
FAILED tests/test_loop_controller.py::test_monthly_credit_boundary_instant_is_included
2 failed, 60 passed
```

Both new boundary tests — `unit="day"` AND `unit="month"` — die on the mutant, and
`tests/test_cost_ledger.py` (26 tests) does **not**. The mutation-testing gap the
round-2 review flagged is genuinely closed, and these two tests are the only thing
holding it. Mutation reverted in the scratch copy; the repo was never modified.

**3. One clock read per tick — no drift is possible. Definitive.**
I replaced `loop_controller.datetime` with a `DriftingDatetime` whose `.now()`
jumps forward a full day on **every** read, spied `_window_start`, and ran a real
`tick()` with **no** `now=` injected:

```
clock reads during one tick() (no now= injected) : 1
```

Then, with a budgets file declaring `active_plan` so the month rail does **not**
short-circuit, both rails go live in the same tick:

```
_window_start calls: [('day',   '2026-07-24T18:38:02.444503+00:00'),
                      ('month', '2026-07-24T18:38:02.444503+00:00')]
```

Identical instant, to the microsecond. `tick()` resolves `_now` once at its top and
threads it into both `_per_day_budget_exceeded(..., now=_now)` and
`_monthly_credit_exhausted(..., now=_now)`; the helpers' `now or datetime.now(...)`
fallback is unreachable when threaded (a `datetime` is never falsy — verified). The
only other `datetime.now` in the module is at line 632, in `main()`'s `--propose`
draft timestamp, outside the tick path entirely. A tick straddling midnight or a
month boundary re-tested at `2026-07-31T23:59:59.999Z`: both rails pinned to the
injected instant. **Answer: no, the two rails cannot evaluate against different
instants.**

**4. Thin, not a parallel mechanism.** `_per_day_budget_exceeded` calls the same
`_window_start` primitive and the same `aggregate_spans(..., since=)` kwarg as the
monthly rail — `unit="day"` vs `unit="month"` is the entire difference. No second
windowing path exists. The day convention matches the feeder: `_window_start(now,
unit="day")` yields naive-UTC `YYYY-MM-DDT00:00:00`, byte-identical to the lower
bound `metrics_history_feeder` builds as `f"{date}T00:00:00Z"`, parsed by the same
`strptime("%Y-%m-%dT%H:%M:%SZ")` in both `_parse_created_at` and `_parse_iso`. The
ledger has no upper bound where the feeder closes at `23:59:59Z` — correct for a
spend-so-far cap, and conservative in the only divergent case (a future-dated span
from clock skew counts toward today, tripping the cap earlier). Noted below as a
follow-up, not a blocker; the monthly rail shipped identically.

**5. No existing caller changed — demonstrated, not asserted.** Enumerated every
`aggregate_spans` call site outside `cost_ledger`/`loop_controller`:

| Caller | Call shape | Passes `since`? |
|---|---|---|
| `scripts/agent_eval.py:497` | `aggregate_spans(store_path)` | no |
| `scripts/alerting.py:272` | `_aggregate_spans(**kwargs)` (`store_path`,`budgets_path` only) | no |
| `scripts/check_cost.py:128` | `aggregate_spans(store_path=…, budgets_path=…)` | no |
| `scripts/cockpit.py:329` | `aggregate_spans(store_path=events_path)` | no |

Then ran each against a 3-span ledger spanning **two months and three days**
(lifetime $17.00; today-only would be $2.00, month-to-date $12.00 — so a windowed
and an unwindowed reader are *forced* to disagree). Every caller still returned
$17.00: `cockpit` `spans: 3, est cost: $17.0000`; `agent_eval.role_cost` `$17.00`;
`check_cost`'s call shape `$17.00`; `alerting.gather_readings` `per_day_cost_usd =
17.0`. `since=None` and the bare default are identical (3 spans, $17.00 both).
For `_per_day_budget_exceeded`: signature is
`(budgets_path, events_path, *, now: datetime | None = None)` — `now` is
KEYWORD_ONLY with a `None` default, the legacy 2-positional form still works
(`tests/test_scheduler.py` uses it, unchanged), and a 3rd positional arg is
rejected with `TypeError`, so no old call site can bind `now` by accident.

**6. The rail binds under the tick.** Through a real `tick()` with a genuine
same-day over-cap state:

```
per_day_budget_exceeded  = True
decision.action          = idle
decision.reason          = cron_tick: pending board work — dispatch the next wave;
                           dispatch withheld — per-day budget cap already breached (SI-5)
```

The identical spend moved to the previous UTC day yields
`per_day_budget_exceeded = False` — the latch is gone.
`flow_router.DECISIONS = frozenset({'validate','idle','dispatch'})`, exactly
`{dispatch, validate, idle}`, and every observed decision was drawn from it.

---

#### RE-RUN VERBATIM

`python3 scripts/check_heartbeat_readiness.py` → **RC=1**:
```
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
```
Still NOT READY, still 0/3, still `active_plan is undeclared`. **That red is
CORRECT** — this ticket fixed a window, it did not manufacture evidence.

`python3 scripts/kill_switch_drill.py --smoke` → **RC=0**, 6 rails:
```
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```

`python3 scripts/heartbeat_go_no_go.py` → **RC=1** (exit code read directly, not
through a pipe): `VERDICT: NO-GO — the evidence bar is NOT met today.`
2 FAIL gates + 1 UNKNOWN; `heartbeat_enabled is still OFF` PASS.

WS-F composite suite → `294 passed in 1.64s`.
Full repo suite `python3 -m pytest -q` → `2552 passed, 25 skipped in 20.20s`
(no hardcoded count equality asserted; green with zero failures is the bar).
`ruff check scripts tests` → `All checks passed!`
`check_never_auto_approve` → `OK: 197 tickets checked, no violations`.
`check_comm_flows` → `OK — 60 routes`. `check_spec_consistency` → `OK, 10 SPEC.md`.
`check_dependency_graph` → `OK: acyclic, no dangling deps`. DAS-1618 is `done`.

**Config, judged by VALUE:** `heartbeat_enabled: false`, `a2a_outbound: false`.
`git diff config/loop.yaml config/budgets.yaml` = **0 lines**. The
`config/features.yaml` diff is the known, expected single `a2a_outbound: false`
line from the A2A workstream earlier in this run — flagged, value confirmed `false`,
not a defect and not a cap widening. `board/.events.jsonl` and
`board/.metrics-history.jsonl` both confirmed **ABSENT** and untouched.

**ONE DISCREPANCY vs the builder's log — recorded honestly.** The builder logged
`diagnostics 100/100` and `board_lint … 0 violations`. On re-run I got
**`SCORE = 85/100`** and **`FAIL DAS-1632: in_review ticket has assignee == author
'sre-lead'`**. Cause: the builder ran both checks *before* making its own final
`status: in_review` / `assignee: sre-lead` edit. The sole failing diagnostics
dimension was `Consistency 0/15`, whose only miss was `XX no-self-review:
['DAS-1632-…md']` — this ticket itself. Both checks are scoped to
`status == "in_review"` (board_lint R8 explicitly; diagnostics' `no-self-review`
identically). Proven on the scratch copy: flipping that one field to `done` moved
`Consistency 0/15 → 15/15` and `board_lint → 0 violations`. **Not a code
regression — a board-state artifact of the review handoff, cleared by this
closure.** Re-confirmed on the real repo below.

Governance note for the record: this ticket has `author: sre-lead` and reviewer
`sre-lead`, which is why R8 fired. The *builder* was `sre-eng`, so no engineer
reviewed their own code; but the ticket's own metadata cannot express that, and an
`in_review` ticket authored and reviewed by the same role can never lint clean.
Flagged to the orchestrator — a ticket I author should carry a different reviewer,
or the author field should record the requesting role.

---

#### ACCEPTED WITHOUT RE-VERIFICATION

- Merged-PR / green-CI is outstanding by explicit orchestrator directive; not a
  bounce condition and not re-checked.
- The builder's own repro numbers ($125 / 10M-in / 3M-out) — superseded by my
  independent reproduction rather than re-run.

---

#### DAS-1634 (SI-5 alert limb) — IS IT NOW A THIN APPLICATION?

Confirmed **zero** `alerting` references in `scripts/loop_controller.py`. The
answer is **yes, but only on one of two possible attachment points**:

- **Attach to `tick()`'s `safety_rails["per_day_budget_exceeded"]`** → thin and
  correct. That boolean is now day-windowed and, critically, **non-latching**: I
  demonstrated it going `True` on same-day over-cap spend and back to `False` once
  the spend falls on a prior day. An alert on this edge fires and clears.
- **Attach to `scripts/alerting.py` instead** → it would inherit the *same*
  lifetime defect this ticket just fixed. `gather_readings` computes
  `per_day_cost_usd = ledger.raw_estimated_cost_usd` from an **unwindowed**
  `aggregate_spans`, self-documented in-line as `# per-day: total cost across all
  events (proxy for today's spend)`. I measured it: on my 3-day ledger it returns
  `17.0` where today's spend is `2.00`. Monotonic ⇒ once past
  `budget_governor`'s per-day threshold it would fire a permanent, un-clearable
  alert. This ticket correctly left it unchanged (AC-3 requires exactly that), but
  DAS-1634 must not route through it un-windowed.

Routed to the orchestrator, below.

---

#### NEW WORK DISCOVERED — for the orchestrator to route (NOT fixed here)

Both are **pre-existing**, both are **out of this ticket's scope** (the ticket
says explicitly: make an existing cap measure the right window, *never a larger
one*), and neither is a reason to hold this fix.

**F1 — `_per_day_budget_exceeded` reads the WRONG per-day cap (p1, likely more
material than the window bug it just fixed).** It reads
`caps.per_day.max_cost_usd` = **$500/day** — the top-level, self-described
*informational* org-wide block. The MUSTAQIL SI-5 dispatch ceiling is
`mustaqil.caps.per_day.max_cost_usd` = **$15/day**, which nothing in the tick
path reads. `heartbeat_go_no_go.py` meanwhile reports `SI-5 caps:
per_run=$5.0/run, per_day=$15.0/day` sourced from `config/budgets.yaml ::
mustaqil`, and `budgets.yaml`'s own comment states those caps are "the runner's
HARD dispatch ceiling … A `--tick` that would breach either evaluates to idle +
alert". So the go/no-go report attributes a $15/day ceiling to SI-5 while the
tick enforces $500/day — a **33x gap between the documented and the enforced
ceiling**. Same failure family as D1/DAS-1618 (a rail reading the wrong number),
different axis (wrong *cap*, not wrong *window*). Correcting it TIGHTENS the
cap, so it is safe by direction — but it is a cap change and belongs on its own
ticket with its own review, not smuggled into a windowing fix. Verified
pre-existing: the cap-read line sits outside this ticket's diff hunks.

**F2 — `alerting.gather_readings` has the un-fixed twin of this defect (p2).**
`per_day_cost_usd` is an unwindowed lifetime total labelled in-line as a "proxy
for today's spend" (measured: `17.0` where today = `2.00`). Feeding
`budget_governor`'s per-day threshold from a monotonic number reproduces exactly
the permanent-latch behaviour this ticket removed from the tick. Must be fixed —
with the same `_window_start` + `since=` mechanism, no third path — **before or
as part of** DAS-1634, or DAS-1634 will ship a latching alert.

**F3 — future-dated span handling (p2, low).** A span with a `created_at` in the
future (clock skew / bad envelope) is counted toward today's cap by the ledger,
where the feeder's closed `…T23:59:59Z` day would exclude it. Direction is
conservative (trips the cap earlier), and the monthly rail shipped with identical
semantics, so this is a consistency/robustness note, not a defect. If addressed,
address both rails together.

**F4 — ticket authorship/review collision (process, p2).** See the governance
note above: `author == reviewer == sre-lead` makes `in_review` unlintable.

---

#### POST-CLOSURE RE-CONFIRMATION (after setting `status: done`)

Exactly as predicted from the scratch-copy proof — the 85/100 and the board_lint
FAIL were the `in_review` handoff artifact and nothing else:

```
python3 scripts/board_lint.py   -> OK — 195 ticket(s) checked, 0 violations.
python3 scripts/diagnostics.py  -> [PASS] Docs 20/20  Architecture 20/20  Code-quality 15/15
                                   Consistency 15/15  Portability 15/15  Security 10/10
                                   Git-hygiene 5/5    SCORE = 100/100
python3 scripts/check_never_auto_approve.py -> OK: 197 tickets, no violations
python3 scripts/check_comm_flows.py         -> OK — 60 routes
python3 -m pytest -q                        -> 2552 passed, 25 skipped in 20.28s
```
(The DAS-1507 body-status WARN is pre-existing, non-fatal, and unrelated.)

No git state was mutated during this review: no commit/add/reset/stash/checkout,
no worktree. The mutation test ran against an rsync'd scratch copy under the
session scratchpad and was reverted there; the repo working tree was never
touched outside this ticket file.
