---
id: DAS-1640
title: Window the alerting spend reading and decide the future-dated span rule
status: done
assignee: cto
verified_by: cto
author: sre-lead
dept: engineering
priority: p2
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1632]
created: 2026-07-24
updated: 2026-07-25
---

## Description

**Both found by SRE Lead reviewing DAS-1632. Two remaining places the window
mechanism is missing or undecided. Item 1 BLOCKS DAS-1634.**

### 1. `alerting.gather_readings` carries the un-fixed defect (blocks DAS-1634)

`scripts/alerting.py :: gather_readings` computes `per_day_cost_usd` from an
**unwindowed** `aggregate_spans`, with an in-line comment calling it a *"proxy for
today's spend"*. Measured during the review: it reports **$17.00** where today's
actual spend is **$2.00**.

This is the same lifetime-vs-daily defect DAS-1632 just fixed in the tick rail,
surviving in the alerting path — and it matters now because **DAS-1634 wires the SI-5
alert limb**. The reviewer's finding is precise: attaching DAS-1634 to `tick()`'s
`safety_rails["per_day_budget_exceeded"]` is a thin, safe application (that boolean is
day-windowed and demonstrably non-latching — it goes True then back to False).
Attaching it to `scripts/alerting.py` instead would **inherit this un-fixed defect**,
so the alert would fire off a monotonic lifetime total that never resets.

Fix it with the SAME mechanism (`aggregate_spans(since=_window_start(now, unit="day"))`)
— not a second one. Then the alert limb can attach to either path safely.

### 2. Future-dated spans count toward today's cap — decide, don't drift

The window filter has a lower bound only, so a span dated in the FUTURE counts toward
today's cap, where the feeder's closed-day convention (`00:00:00Z–23:59:59Z`) would
exclude it. The behaviour is conservative (it can only make the rail fire earlier,
never later) and is **identical in the monthly rail**.

Make it a decision, recorded either way:
- **(a)** add an upper bound so both rails match the feeder's closed-day/month
  convention exactly; or
- **(b)** record the lower-bound-only behaviour as deliberate, with the reasoning
  (conservative direction, and a future-dated span is itself a data defect worth
  surfacing rather than silently discarding).

**Whichever you choose, apply it to BOTH rails or neither.** Two rails with different
window shapes is worse than either shape consistently applied. ADR-0042 SI-5.2 already
records the shipped filter as lower-bound-only — if you choose (a), that clause needs
a follow-up note, which is a CTO act; flag it rather than editing the ADR.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT change any cap VALUE or widen SI-5/SI-6.
Do NOT write to the real `board/.events.jsonl` — synthetic ledgers go in scratch.

**Reviewer note (ROUTING):** author is `sre-lead`; at `in_review` assign to **`cto`**,
not `sre-lead` — "manager is the author → climb one level". Assigning back to the
author trips the no-self-review lint.

## Acceptance criteria
- [x] `alerting.gather_readings` computes `per_day_cost_usd` over the correct daily window using the existing `_window_start` / `since=` mechanism — no second implementation; the "proxy for today's spend" comment removed or made true.
- [x] A test proves prior-day spend no longer inflates the alerting reading (the reviewer measured $17.00 vs a true $2.00).
- [x] An explicit recorded decision on future-dated spans — (a) upper bound added to BOTH rails, or (b) lower-bound-only recorded as deliberate with reasoning. Never one rail only.
- [x] If (a): the ADR-0042 SI-5.2 follow-up flagged for the CTO rather than edited here. — N/A: decision was (b), not (a); no ADR follow-up needed.
- [x] `check_heartbeat_readiness.py` still NOT READY; `kill_switch_drill --smoke` 6 rails green; no cap value changed.
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-24 — SRE / DevOps Lead
Both raised in the DAS-1632 review; recorded by the orchestrator in the same run.
Item 1 was found by asking where ELSE the just-fixed defect shape lives, rather than
stopping at the call site under review — and it is the difference between DAS-1634
being a thin application and DAS-1634 inheriting a latching bug.

### 2026-07-25 — SRE Engineer

**Item 1 — fixed.** `scripts/alerting.py :: gather_readings` now windows
`per_day_cost_usd` with `aggregate_spans(..., since=_window_start(now, unit="day"))`,
importing `_window_start` from `scripts/loop_controller.py` — the SAME mechanism
`_per_day_budget_exceeded` / `_monthly_credit_exhausted` already use, not a second
implementation. No import cycle: `loop_controller` never imports `alerting` at
module scope (only `ws_b_admission` does, lazily inside a function body), so a
top-level `from loop_controller import _window_start` in `alerting.py` is safe —
verified with a bare `import alerting` smoke run. `per_run_cost_usd` stays on a
separate, deliberately unwindowed `aggregate_spans` call (a run's total spend
doesn't reset at a calendar boundary, so windowing it would be wrong). The stale
"proxy for today's spend" comment is removed and replaced with a comment
documenting the fix and the shared mechanism.

Failure-isolation: if `_window_start` import ever fails, `per_day_cost_usd`
degrades to `None` (inert) rather than silently reverting to the lifetime read —
covered by `test_gather_readings_per_day_cost_none_when_window_start_unavailable`.

BEFORE/AFTER, observed on a scratch ledger (prior-day $15 opus spend +
today $2 opus spend, same shape as the reviewer's finding):
```
per_day_cost_usd (AFTER fix): 2.0
lifetime (BEFORE-fix equivalent): 17.0
```
This reproduces the reviewer's exact numbers ($17.00 -> $2.00). Pytest pin:
`tests/test_alerting_cost.py::test_gather_readings_per_day_cost_windowed_not_lifetime`.

**Item 2 — decision: (b), lower-bound-only is deliberate.** Reasoning:
1. Conservative direction — a future-dated span can only make a rail fire
   *earlier*, never later, and SI-5/SI-6 are safety ceilings where erring toward
   caution is the correct default.
2. A future-dated span is itself a data-quality defect (clock skew, a malformed
   `created_at`, or a bad write) — DAS-1633 established the precedent of
   *surfacing* anomalous timestamps (`dropped_undated`) rather than silently
   discarding them. Silently excluding a future-dated span via an upper bound
   would hide that same class of defect instead of surfacing it; a real
   `dropped_future_dated`-style counter would be the more consistent next step
   if this needs to become visible, but that is new scope beyond this ticket
   (flagging, not building, per the ticket's own framing of (b) as
   "record... with reasoning").
3. Implementing (a) would touch `aggregate_spans` (new `until=` param) AND both
   `loop_controller.py` rail callers AND `alerting.py` — a 3-site change against
   a currently-adjacent, not-yet-dispatched DAS-1641 that also touches
   `loop_controller.py`; (b) needs zero code change beyond the item-1 fix that
   was already required, so it stays minimal and doesn't create merge risk for
   DAS-1641 per the dispatch's own zone-lock note.
4. ADR-0042 SI-5.2 already documents the shipped filter as lower-bound-only —
   decision (b) is consistent with the ADR as written; no CTO follow-up on the
   ADR is needed (that would only apply to decision (a)).

Consistency proof: `test_future_dated_span_treated_identically_across_all_three_readers`
seeds one span dated `2027-07-24` (about a year in the future vs. a fixed
`now=2026-07-24`) and independently evaluates all three readers against it —
`alerting.gather_readings`'s `per_day_cost_usd`, `loop_controller._per_day_budget_exceeded`
(cap set to $1 so only the future span's inclusion decides the verdict), and
`loop_controller._monthly_credit_exhausted` (same shape, $1 plan credit). All
three count the future-dated span (asserted `verdicts == {True}`) — one shape
applied consistently, per the ticket's binding requirement.

**Verification (observed, not claimed):**
```
python3 scripts/check_heartbeat_readiness.py   -> VERDICT: NOT READY, exit 1
python3 scripts/kill_switch_drill.py --smoke   -> pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok; exit 0
python3 scripts/heartbeat_go_no_go.py          -> VERDICT: NO-GO, exit 1
PYTHONPATH=scripts python3 -m pytest tests/test_alerting.py tests/test_alerting_cost.py \
  tests/test_check_heartbeat_readiness.py tests/test_check_never_auto_approve.py \
  tests/test_cost_ledger.py tests/test_heartbeat_go_no_go.py tests/test_interrupt_roundtrip.py \
  tests/test_kill_switch_drill.py tests/test_loop_controller.py tests/test_no_daemon.py \
  tests/test_scheduler.py -q                   -> 366 passed in 2.01s  (WS-F composite; baseline
                                                    was 294 at DAS-1632 — 366 >= 294)
PYTHONPATH=scripts python3 -m pytest -q        -> 2605 passed, 25 skipped in 22.99s  (full repo suite;
                                                    baseline 2552 passed at DAS-1632 — 2605 >= 2552)
python3 scripts/diagnostics.py                 -> SCORE = 100/100
python3 scripts/board_lint.py                  -> OK: 198 ticket(s) checked, 0 violations (exit 0)
ruff check scripts tests                       -> All checks passed!
git diff config/loop.yaml config/budgets.yaml  -> empty
board/.events.jsonl, board/.metrics-history.jsonl -> both absent (unchanged)
```

Files touched: `scripts/alerting.py` (fix), `tests/test_alerting_cost.py` (4 new
tests: windowed-vs-lifetime, failure-isolation, future-dated-span consistency,
plus the pricing/span helpers they share). Zone lock respected — nothing under
`docs/`, `config/`, or `tools/`; `scripts/loop_controller.py` was READ, not
edited, so DAS-1641 (which touches its docstring + `kill_switch_drill.py`)
should still apply cleanly.

**DAS-1634 assessment:** yes — after this fix, DAS-1634 (wiring the SI-5 alert
limb) is now a thin attachment to a correctly-windowed, non-latching boolean at
BOTH attachment points. The tick rail (`tick()`'s
`safety_rails["per_day_budget_exceeded"]`) was already fixed by DAS-1632. The
alerting path (`alerting.gather_readings`'s `per_day_cost_usd`, consumed by
`budget_governor` in `evaluate_alerts`) is now windowed identically via the same
`_window_start` mechanism, and degrades to inert (`None`) rather than latching
on any failure. DAS-1634 can attach to either surface without inheriting a
lifetime-total defect.

**No escalation needed.** Item 2's decision (b) required no ADR edit and no
CTO follow-up (that branch only applies to decision (a), not taken).

status -> in_review, assignee -> cto (per the ticket's own routing note: author
is sre-lead, so in_review climbs one level to cto rather than looping back to
the author).

### 2026-07-25 — CTO (review — ACCEPT)

Reviewed as CTO (author is sre-lead → climbed one level; no self-review). All six
review focuses hold. **RE-VERIFIED independently** (my own scratch ledger + my own
constructions, not just the builder's tests) vs. **ACCEPTED on the builder's own
evidence**, separated below.

**Re-verified myself (independent constructions):**
1. *Windowing fix is real and reproduces the finding.* Own scratch ledger: prior-day
   $15 opus + today $2 opus → `gather_readings.per_day_cost_usd = $2.00` while the
   lifetime `aggregate_spans` genuinely sees $17.00. Reproduces the $17.00 → $2.00
   shape exactly. `per_run_cost_usd` reads $15.00 (the largest single run), unwindowed
   — correct (see 3).
2. *No second window impl, no import cycle.* `alerting._WINDOW_START is
   loop_controller._window_start` → True (same object, not a copy). `import alerting`
   and `import loop_controller` both clean. Grep confirms NO module-scope
   `import alerting` anywhere; the sole importer is `ws_b_admission.py:73`
   (`from alerting import budget_governor`), lazy inside a function body.
   `loop_controller` imports nothing from `alerting`. Cycle structurally impossible.
4. *None-degrade is genuinely inert, not silently wrong.* Forced
   `_WINDOW_START_AVAILABLE = False` → `per_day_cost_usd` degrades to `None` (NOT the
   lifetime read). Downstream `budget_governor` (line 121 `if raw_total is None …
   continue`) SKIPS the dimension — it never computes it as $0-under-budget and never
   suppresses other dimensions (a per_run breach still fires with per_day=None,
   per `test_governor_inert_missing_per_day_total`). Degrade is to *no signal*, never
   to a *wrong signal*. Absence-vs-zero trap avoided.
5. *Decision (b) consistent across ALL THREE readers.* My own construction (a span
   dated 2027-01-15, ~6 months future vs. fixed now=2026-07-24, distinct from the
   builder's ~1yr span): `alerting.gather_readings`, `_per_day_budget_exceeded`, and
   `_monthly_credit_exhausted` ALL count it (True/True/True). One shape applied
   consistently. Read ADR-0042 SI-5.2 clause 5 directly: it genuinely records the
   shipped filter as "lower bound only … a hypothetical future-dated span would be
   counted … Recorded here as shipped behavior rather than smoothed over." Decision
   (b) is consistent with the ADR as written — no ADR edit needed. Correct not to edit.

**Accepted on builder's reasoning (concurred, not re-derived):**
3. *`per_run_cost_usd` left unwindowed is correct, not an oversight.* A per-RUN figure
   (total spend of a single run — the max over `by_run`) and a per-DAY figure are
   different questions; a run's cumulative spend does not reset at a calendar boundary,
   so windowing it would be wrong. Concur — this is a deliberate, correctly-scoped
   asymmetry, not a missed site.

**Verbatim re-run (this session, my machine):**
```
check_heartbeat_readiness.py   -> NOT READY, exit 1   (active_plan undeclared blocker)
kill_switch_drill.py --smoke   -> pass[000] SI-3/4/5/6/7/2 = ok; exit 0  (6 rails)
heartbeat_go_no_go.py          -> NO-GO, exit 1  (exit code read directly)
WS-F composite suite           -> 366 passed  (>= 294 baseline; no hardcoded equality)
full repo suite (pytest -q)    -> 2605 passed, 25 skipped  (>= 2552 baseline)
diagnostics.py                 -> SCORE = 100/100
board_lint.py                  -> OK, 198 tickets, 0 violations (exit 0; only pre-existing
                                  DAS-1507 WARN, unrelated)
ruff check scripts tests       -> All checks passed!
git diff config/loop.yaml config/budgets.yaml -> EMPTY
board/.events.jsonl, board/.metrics-history.jsonl -> both ABSENT
tests/test_alerting_cost.py    -> 31 passed
```
No cap VALUE changed; no `heartbeat_enabled` flip; no config edit; zone respected
(only `scripts/alerting.py` + `tests/test_alerting_cost.py` touched;
`scripts/loop_controller.py` read, not edited).

**DAS-1634 unblock (explicit):** YES — DAS-1634 (SI-5 alert limb) is now a thin
attachment at BOTH attachment points. Tick rail
(`tick().safety_rails["per_day_budget_exceeded"]`) was fixed by DAS-1632; the alerting
path (`gather_readings.per_day_cost_usd`, consumed by `budget_governor` in
`evaluate_alerts`) is now windowed via the SAME `_window_start` primitive and degrades
to inert `None`, never a latching lifetime total. Both surfaces are correctly-windowed,
non-latching booleans/reads. DAS-1634 may attach to either without inheriting the
lifetime defect.

**No escalation.** Decision (b) needed no ADR edit and no CTO follow-up (that branch
applies only to decision (a), not taken). Merged-PR / green-CI remains outstanding by
standing orchestrator directive — not a bounce condition. Marking `status: done`,
`verified_by: cto`.
