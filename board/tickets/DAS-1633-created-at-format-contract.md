---
id: DAS-1633
title: Pin one created_at format contract so undated spans stop vanishing from budgets and evidence
status: done
assignee: backend-em
verified_by: backend-em
author: sre-lead
dept: engineering
priority: p1
parent: 
goal: platform-hardening
labels: [governance]
zone: scripts
depends_on: [DAS-1618]
created: 2026-07-24
updated: 2026-07-25
---

## Description

**Found by SRE Lead during the DAS-1618 round-2 re-review. Pre-existing and
repo-wide — deliberately not fixed at one seam, because fixing one seam is what
makes this class of bug survive.**

`dgox.events.validate_envelope` accepts **any non-empty string** as `created_at`.
But every downstream consumer — `cost_ledger`, `metrics_history_feeder`,
`wave_kpi`, `metrics_lib`, `trends` — silently requires exactly
`%Y-%m-%dT%H:%M:%SZ`. Nothing reconciles the two.

**The failure this produces.** A caller emitting a perfectly reasonable
`datetime.now(UTC).isoformat()` (which yields `+00:00`, not `Z`, and may carry
microseconds) writes an event that validates cleanly at the seam and is then
**silently skipped by every consumer**. The consequences compound in exactly the
two places that must not be wrong:
- that spend becomes **invisible to the budget ceiling** — the cap under-counts,
  i.e. fails OPEN;
- those waves become **invisible to the clean-day evidence** — the ≥3-day shadow
  window silently fails to accumulate.

And there is no signal anywhere: no error, no warning, no dropped-record count.
The system reports a smaller number with total confidence.

**Why the exclusion behavior itself is correct and must NOT be reverted.** The
DAS-1618 re-review adjudicated this: counting undated spans would make them count
in *every* window forever — reintroducing D1's permanent-latch failure by the back
door. Excluding them is right. The defect is that exclusion is **silent** and that
the write seam permits the ambiguity in the first place.

**Fix it uniformly, at the write seam AND with a visible count — never at one
consumer:**
- Pin the format at write time so an out-of-contract `created_at` cannot be
  emitted (validate in `validate_envelope`, not merely downstream).
- Surface a dropped/undated record count wherever records are skipped, so silent
  under-counting becomes visible.
- Decide explicitly what happens to events already written in a non-conforming
  shape, if any exist — migrate, or document why none can.

**Test the thing that would have caught this:** an event whose `created_at` is
`datetime.now(UTC).isoformat()` must either be rejected at the seam or counted by
consumers — never accepted and then silently dropped. A test asserting only that
well-formed events work would have passed against the buggy code.

⛔ Do NOT flip any feature flag. Do NOT relax the window filtering to "count
everything" — that reintroduces the D1 latch this repo just spent two rounds
removing.

## Acceptance criteria
- [x] `created_at` format contract enforced at the write seam so a non-conforming value cannot be emitted.
- [x] Every consumer that skips a record surfaces a count of what it skipped — silent drops eliminated.
- [x] A test proves an `isoformat()`-shaped `created_at` is either rejected at the seam or counted downstream, never accepted-then-dropped.
- [x] Existing non-conforming events handled explicitly (migrated, or documented as impossible).
- [x] No change to the exclusion semantics of window filtering (undated records still must not count in every window).
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-07-25 — Backend EM (review — ACCEPTED / merge decision GATE-3)

Reviewed backend-eng-2's write-seam fix. **Did not trust the builder's own
tests** — independently re-derived every load-bearing claim. Verdict: **accept.**

**Re-verified independently (my own scratch harness + monkeypatch, no file edits,
no git mutation):**
1. *The reject breaks no real producer.* Exercised all 10 `dgox.events.build_*`
   shapes through `validate_envelope` AND round-tripped each through
   `EventStore.append` to a scratch path — zero `created_at` rejections
   (`utcnow()` → `2026-07-24T19:37:34Z`, conforming). Then traced EVERY event
   producer in the repo: `dgox.events.utcnow()` (canonical Z), `result_cache.
   _utcnow()` (canonical Z, feeds `build_cache_hit`→append), `dispatch_emitter`
   (caller-supplied Z from `wave_runner` `TicketResult`, contract = Z; already
   gated by `validate_run_start/end`), the three drills (fixed canonical-Z
   literals). Grepped `isoformat(` across `scripts/` — the only `.isoformat()`
   producing `+00:00` is `e2e_run._utc_now()`, and it feeds a run-SUMMARY dict
   (`generated_utc`), never a DGO-X event `created_at`. **No production path
   raises. Reject was the correct call, not normalise** — a silent rewrite would
   have hidden the exact `+00:00`/microsecond drift this defect is about.
2. *Exclusion semantics genuinely unchanged.* On my own one-good/one-buggy
   scratch stream: the buggy (`isoformat()`) record is EXCLUDED from every
   window (raw_span_count==1; and it never leaks into a non-matching window —
   D1/DAS-1618 permanent-latch NOT reintroduced) AND is COUNTED as dropped.
   Both properties, not one.
3. *Drop count is real in all five consumers, not claimed.* Seeded the scratch
   stream and confirmed `cost_ledger.dropped_undated==1` (surfaced by
   `check_cost.py` L175-178), `metrics_history_feeder` `DropCounter.count==1`
   (CLI NOTE), `wave_kpi` stats `dropped_undated==1`, `metrics_lib`
   `_dropped_undated`==1 (concurrency_stats + review_efficiency), `trends.
   dropped_undated_run_ends==1` (CLI NOTE). All five delegate to the shared
   `dgox.created_at.parse_created_at` — no shadow `_parse_iso`/`strptime`
   survives (grepped each module); genuine consolidation, not five imports with
   one bypass.
4. *TDD claim re-derived.* Monkeypatched `events.is_valid_created_at` back to the
   pre-fix "non-empty string" check in-process: both write-seam assertions go RED
   (validate_envelope stops flagging the buggy shape; `EventStore.append` stops
   raising) while the builder round-trip STAYS GREEN (canonical Z is a non-empty
   string under either check). Exactly the 2 write-seam tests fail — the builder
   test is not testing the wrong thing.

**Re-ran verbatim (this review):**
- `pytest tests/test_created_at_contract.py -q` → **24 passed**.
- dgox/cost/metrics/wave_kpi/trends targeted suites → **202 passed** + **119
  passed, 1 skipped**.
- `pytest -q` (full repo) → **2602 passed, 25 skipped** (matches builder; no
  hardcoded count equality relied on — baseline `>= 2602`).
- `ruff check scripts tests` → **All checks passed!**
- `diagnostics.py` → **SCORE = 100/100**.
- `board_lint.py` → **OK, 198 ticket(s), 0 violations** (1 pre-existing non-fatal
  WARN on DAS-1507, unrelated).
- `check_heartbeat_readiness.py` → **NOT READY, exit 1** (correct red;
  pre-existing unrelated blockers: 0/3 clean days, undeclared active_plan).
- `kill_switch_drill.py --smoke` → **OK, exit 0** (SI-2..7 all ok, loop off).
- `heartbeat_go_no_go.py` → **NO-GO, exit 1** (same pre-existing blockers).
- `board/.events.jsonl` and `board/.metrics-history.jsonl` → **still ABSENT**
  before and after (nothing to migrate — acceptance #4 = documented-impossible
  holds; nothing written to the real streams during review).

**Accepted (builder's work, spot-confirmed not independently re-run):** the
prose of the SSOT module docstring and the follow-up flag on
`loop_controller._per_day_budget_exceeded`/`_monthly_credit_exhausted` being
left un-instrumented (pure bool evaluators) — a reasonable scope boundary; the
`cost_ledger.dropped_undated` count is available to a future ticket that wants
it threaded into the tick decision. Not a blocker.

All six acceptance criteria verified. Merge decision: GATE-3 **PASS**.
Note per orchestrator directive: merged-PR/green-CI remains outstanding
(LOCAL-ONLY run) and is explicitly NOT a bounce reason here.

Status → `done`; `verified_by: backend-em`.

### 2026-07-25 — Backend Engineer 2

**Root cause confirmed.** `scripts/dgox/events.py::validate_envelope` accepted
any non-empty string as `created_at`; `cost_ledger`, `metrics_history_feeder`,
`wave_kpi`, `metrics_lib`, `trends` each carried an independent local
`_parse_iso`/`_parse_created_at` requiring exactly `%Y-%m-%dT%H:%M:%SZ` and
silently excluded anything else. Traced the real-world blast radius:
`scripts/loop_controller.py::_per_day_budget_exceeded` /
`_monthly_credit_exhausted` call `cost_ledger.aggregate_spans(..., since=...)`
— an out-of-contract `created_at` there silently under-counts the SI-5 spend
ceiling (fails OPEN), and `metrics_history_feeder.filter_events_by_window`
under-counts the clean-day evidence window. Both numbers gate HEARTBEAT
go-live, as the ticket states.

**Fix (write seam, REJECT not normalise).** Added
`scripts/dgox/created_at.py` — the single source of truth: `CREATED_AT_FORMAT`,
`parse_created_at` (strict `strptime`, no `fromisoformat` coercion),
`is_valid_created_at`, `count_invalid` (shared counting helper), and
`DropCounter` (streaming counter for filters that skip one record at a time).
`dgox.events.validate_envelope` now calls `is_valid_created_at` and REJECTS a
non-conforming `created_at` (error message names DAS-1633) instead of the old
"non-empty string" check; `EventStore.append` already raised `ValueError` on
any envelope error, so this closes the write seam directly — nothing
non-conforming can be appended. Decision: reject, not normalise. Rationale
logged in the `validate_envelope` docstring — every real producer in
`events.py` already emits the canonical shape via `utcnow()` (which now
delegates to the same `CREATED_AT_FORMAT` constant), verified for all 10
`build_*` shapes in `tests/test_created_at_contract.py::
TestEveryBuilderStillRoundTrips`, and a silent rewrite would hide the exact
clock-format drift (`+00:00` / microseconds) this defect is about — a reject
is loud without breaking a single real caller.

**Uniform consumer fix (never at one seam).** `cost_ledger._parse_created_at`,
`metrics_history_feeder._parse_iso`, `wave_kpi._parse_iso`, `metrics_lib.
_parse_iso`, `trends._parse_iso` all now delegate to the shared
`dgox.created_at.parse_created_at` instead of five independent `strptime`
re-implementations — a future format change is a one-line edit, not five.
Dropped/undated counts surfaced (never silent again):
- `cost.cost_ledger.CostLedger.dropped_undated` (new field) — incremented for
  every span with a missing/non-conforming `created_at`; printed by
  `check_cost.py` when non-zero.
- `metrics_history_feeder.filter_events_by_window(..., drop_counter=)` (new
  optional param, `DropCounter`) — wired into the CLI (`--all` and windowed
  paths), which now prints a NOTE when records were excluded.
- `wave_kpi.busy_fraction_from_events` stats dict gained `"dropped_undated"`.
- `metrics_lib.concurrency_stats` and `.review_efficiency` dicts gained
  `"dropped_undated"` via a new shared `metrics_lib._dropped_undated` helper.
- `trends.py` gained `dropped_undated_run_ends()`, printed by the CLI.
All additions are additive (new dict keys / optional kwargs) — no existing
call site or return-shape assertion changed.

**Existing non-conforming events:** confirmed `board/.events.jsonl` and
`board/.metrics-history.jsonl` are both ABSENT (`find board -iname
'*.jsonl'` lists only `.tool-audit.jsonl`, `wave-ledger.jsonl`,
`.arcrift-outbox.jsonl` — none are the DGO-X event store or metrics-history
file, and `wave-ledger.jsonl`'s one `created_at` value is already canonical).
No counted waves have landed. Nothing to migrate — documented here, not
assumed.

**Test (TDD, watched it fail first).** New `tests/test_created_at_contract.py`
(24 tests). The load-bearing test is the exact shape from the ticket:
`_BUGGY_SHAPE = datetime.now(tz=UTC).isoformat()`.
- Before/after, verbatim: temporarily reverted `validate_envelope`'s
  `created_at` check to the pre-fix "non-empty string" version and re-ran —
  `TestWriteSeamRejectsBuggyShape::test_buggy_shape_rejected_by_validate_envelope`
  failed with `AssertionError: expected a created_at rejection for buggy
  shape '2026-07-24T19:29:53.955412+00:00'; got []` and
  `test_buggy_shape_rejected_by_event_store_append` failed with `Failed: DID
  NOT RAISE ValueError` — 2 failed, 22 passed. Restored the fix (edited back,
  no git operations used) and re-ran: `24 passed in 0.16s`.
- `TestEveryBuilderStillRoundTrips` — one test per `build_*` shape
  (routing_decision, agent_invocation, run_start, run_end, wave, checkpoint,
  cache_hit, span, ticket_completion, replanned), each built with
  `events.utcnow()` and asserted to produce zero `created_at` errors —
  demonstrated, not assumed, per the ticket's instruction.
- `TestDroppedCountIsObservable` — a scratch stream (never
  `board/.events.jsonl`) with one good + one buggy-shaped span/event proves
  the count is observable in all five consumers, e.g.
  `ledger.dropped_undated == 1` (lifetime) and `windowed.raw_span_count == 1`
  + `windowed.dropped_undated == 1` (windowed).
- `TestExclusionSemanticsUnchanged` — confirms an undated event still does
  NOT count in every window (D1/DAS-1618's fix not reintroduced): asserted
  across two disjoint windows and the pass-through (no-window) case.

**Verification (observed output, this run):**
- `python3 -m pytest tests/test_created_at_contract.py -q` → `24 passed`.
- `python3 -m pytest -q` (full repo suite) → `2602 passed, 25 skipped` (both
  runs, before and after the ruff fix below; baseline `collected >= 2602`
  going forward — no hardcoded equality relied on).
- `ruff check scripts tests` → one `I001` import-order finding in my own new
  test file, fixed; re-run → `All checks passed!`.
- `python3 scripts/diagnostics.py` → `SCORE = 100/100` (was 85/100 with the
  ruff finding present, purely from the not-yet-fixed import order in my new
  test file — confirmed by re-running after the fix).
- `python3 scripts/board_lint.py` → `OK — 198 ticket(s) checked, 0
  violations` (1 pre-existing non-fatal WARN on DAS-1507, unrelated).
- `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY`, exit
  1 (correct red — unrelated pre-existing blockers: 0/3 clean days,
  undeclared `active_plan`).
- `python3 scripts/kill_switch_drill.py --smoke` → `OK — every safety rail
  held on every pass`, `SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok`,
  exit 0.
- `python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO`, exit 1
  (unrelated pre-existing blockers, same as readiness check).
- `board/.events.jsonl` and `board/.metrics-history.jsonl`: confirmed still
  absent (`ls` → `No such file or directory` for both, checked before and
  after the change).
- `config/features.yaml`'s pre-existing unstaged `a2a_outbound: false` line
  confirmed untouched.

**Zone/scope discipline:** touched only `scripts/dgox/events.py` (edit),
`scripts/dgox/created_at.py` (new), `scripts/cost/cost_ledger.py`,
`scripts/check_cost.py`, `scripts/metrics_history_feeder.py`,
`scripts/wave_kpi.py`, `scripts/metrics_lib.py`, `scripts/trends.py`,
`tests/test_created_at_contract.py` (new), and this ticket file. Did NOT
touch `scripts/stage_gate.py` / `tests/test_stage_gate.py` (DAS-1631's
concurrent zone) or anything under `docs/`, `config/`, `tools/`. No feature
flag flipped. No git state mutated (no commit/add/reset/stash/checkout;
`git status`/`git diff` used read-only for verification and the before/after
demonstration above was done via direct file edits, not git).

**Not done here, flagged for follow-up (not a blocker for this ticket's
acceptance criteria, all met):** `loop_controller.py::_per_day_budget_exceeded`
/ `_monthly_credit_exhausted` — the exact call sites where the historical
under-count would have hit the SI-5 budget ceiling — are pure/failure-isolated
functions returning only a bool; they were left un-instrumented to avoid
widening `tick()`'s documented pure-evaluator contract. `cost_ledger.
dropped_undated` is available to them today if a future ticket wants that
count threaded into the tick decision dict or an operator-facing log line.

Status → `in_review`, assignee → `backend-em` (reviewer per ROUTING.md; never
self-review).

## Log
### 2026-07-24 — SRE / DevOps Lead
Raised in the DAS-1618 round-2 re-review; recorded by the orchestrator in the same
run. Explicitly routed as repo-wide new work rather than folded into DAS-1618,
whose scope was the monthly-ceiling window defect. Priority p1 because it silently
corrupts both the budget cap and the clean-day evidence trail that gate HEARTBEAT
go-live — the two numbers a Founder decision rests on.
