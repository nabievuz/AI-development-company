---
id: DAS-1618
title: WS-F Development — close real gaps in the shadow and evidence tooling
status: done
assignee: sre-lead
verified_by: sre-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-002, FR-005]
labels: [governance, security]
zone: scripts
depends_on: [DAS-1617]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-F, part 1).** Fix only the
**real gaps** DAS-1617's evidence map surfaced — never rebuild `loop_controller.py`,
`break_glass.py`, or `check_heartbeat_readiness.py` from scratch.

- As of this ticket's creation, `check_heartbeat_readiness.py` reports **0/3
  consecutive clean days from 0 history rows** — the shadow window has not begun
  accumulating because waves are not yet landing as *counted* (merged PR + green CI
  + T7, per the anti-gaming regime) and/or `board/.metrics-history.jsonl` is not
  being fed daily. If DAS-1617 confirms this is the blocking gap, this ticket closes
  it: wire (or confirm wired) the counted-wave → metrics-history feed path
  (`scripts/metrics_history_feeder.py` or equivalent) so real shadow days can start
  accumulating once dispatch resumes.
- Fix any other SI-1…SI-7 evidence gap DAS-1617 flagged (e.g. a missing test, a
  stale reporter path) — each fix traces to one flagged gap, no speculative rework.
- Do **not** touch `config/loop.yaml`'s mode/`auto_apply`, do **not** flip
  `heartbeat_enabled`, do **not** widen SI-5/SI-6 caps.

## Acceptance criteria
- [x] Every gap DAS-1617 flagged in the evidence map is closed with a named fix,
      or explicitly re-classified (with reason) as out of WS-F's scope.
      *(D1 blocker resolved via option (A), the `since` kwarg. **Re-verified by the
      reviewer 2026-07-24 (round 2)**: D1 reproduced independently pre- and post-fix
      — a 2025-01-only store gives lifetime $50 ≥ $20 cap (old shape → exhausted)
      but windowed → `None` → `_monthly_credit_exhausted` `False`; positive control
      and mixed-month cases both correct. See Log.)*
- [x] The counted-wave → shadow-metrics feed path confirmed working (or fixed) so
      `check_heartbeat_readiness.py` can accumulate real clean-day rows once waves
      resume — verified by a dry-run / test, not asserted.
      *(Reviewer round 1 exercised the pipe end-to-end into a scratch history;
      round 2 re-confirmed `board/.events.jsonl` and `board/.metrics-history.jsonl`
      are both still ABSENT — no synthetic row in the real evidence trail.)*
- [x] No governance-or-policy file (`loop.yaml`, `features.yaml`'s `heartbeat_enabled`
      value) edited by this ticket.
      *(Re-verified by flag VALUE, not staging state: `heartbeat_enabled: false`,
      `ws_f_heartbeat: false`; `git diff` empty on `config/loop.yaml` and
      `config/budgets.yaml`; the sole `config/features.yaml` line is the unrelated
      concurrent-workstream `a2a_outbound: false`.)*
- [x] `diagnostics.py` 100/100 — **re-run by the reviewer**, not accepted on report.
      Full battery re-run verbatim in the Log (drill 6 rails, `check_loop_mode`,
      composite 244, callers 190, full suite 2480 passed / 25 skipped, `board_lint`,
      `ruff`). PR/merge/CI: local-only run by orchestrator directive — explicitly
      excluded from this judgement, to be carried at workstream close.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Development, part 1). Scoped to closing only the real
gaps DAS-1617's evidence map surfaces (the current 0/3-clean-day/0-history-row state
is the likely candidate) — no rebuild of existing WS4 machinery.

### 2026-07-24 — SRE Engineer

Implemented against `docs/design/ws-f-tempo-verification.md` §3 (G1) and closed
DAS-1617's headline evidence gap. Zone respected: only `scripts/` + `tests/` +
this ticket file touched; `config/features.yaml`, `config/loop.yaml`,
`config/budgets.yaml` all untouched (`git diff` empty on all three, verified
below). No flag flipped; `heartbeat_enabled` untouched.

**G1 — monthly credit ceiling wired into `--tick` (SI-5/FR-004).**
- `scripts/loop_controller.py`: added `_monthly_credit_exhausted(budgets_path,
  events_path, credit_state=None)` — a ~15-line thin adapter that calls
  `ws_b_admission.load_mustaqil_budgets()` / `check_credit_exhaustion()`
  **directly** (never `admit()` — fails closed on absent `model`; never
  `gated_admit()` — gated on the unrelated `ws_b_agent_sdk_runner` flag). No
  arithmetic of its own. Failure-isolated to `False` (mirrors
  `_per_day_budget_exceeded`). `tick()` now computes it and surfaces it in
  `safety_rails.monthly_credit_exhausted` (visible in shadow mode) and in
  `_print_tick`'s rail block. Added a test
  (`test_tick_never_calls_admit_or_gated_admit`) that monkeypatches both
  forbidden entrypoints to raise — proves the trap the design flagged is
  actually avoided, not just documented.
- `scripts/flow_router.py`: `TickContext` gained
  `monthly_credit_exhausted: bool = False` (defaulted — no existing caller
  affected). `_dispatch_blocked` gained exactly one clause, positioned after
  the SI-5 per-day clause and before the SI-6 in-flight clause:
  `"monthly subscription credit exhausted — sanctioned pause (SI-5/FR-004)"`.
  `route_from_store` gained `credit_exhausted: bool = False`; CLI gained
  `--credit-exhausted` (mirrors `--budget-exceeded`). `flow_router.DECISIONS`
  is untouched — still exactly `{dispatch, validate, idle}`
  (`frozenset({"dispatch","validate","idle"}) == fr.DECISIONS`, asserted by a
  new test). Verified: blocks dispatch only, never `validate`
  (`test_monthly_credit_exhausted_never_blocks_validate`); never raises/errors
  (`test_monthly_credit_exhausted_never_raises_or_errors`).
- `scripts/check_heartbeat_readiness.py`: the `active_plan` residual (design
  §3.5) resolved exactly as specified — **inert in the tick, blocking at the
  gate**. Added `_active_plan(budgets_path)` (reads
  `mustaqil.monthly_credit_ceiling.active_plan`; `None` on
  absent/malformed/unreadable — never guesses). `assess()` gained
  `active_plan` / `credit_exhausted` params; `ready` is now
  `(not flag_on) and window_met and credit_precondition_met`, with two
  **distinct** blocker strings (undeclared-plan vs exhausted-credit), each
  reported as its own line. `main()` wires `--budgets`/`--events` CLI args and
  calls `loop_controller._monthly_credit_exhausted` when a plan is declared.
  **I did NOT add `active_plan` to `config/budgets.yaml`** — that is a
  `config/` edit and my dispatch's zone lock forbids touching `config/` this
  round (another agent is concurrently on `config/risk_taxonomy.yaml`). This
  is a real, intentional residual, not an oversight — see "Routing" below.

**The counted-wave → metrics-history feed path — CONFIRMED WORKING, simply
UNFED (not broken).** `scripts/metrics_history_feeder.py` (DAS-1476, `done`)
already has 43 passing unit tests including an existing end-to-end proof
(`tests/test_metrics_history_feeder.py` lines ~519-592) that
`compute_window_row` → `append_history_row` → `loop_controller.clean_live_days`
round-trips correctly. I re-verified this myself with a synthetic dry-run in
my scratchpad (never touching the real `board/.metrics-history.jsonl` —
fabricating shadow days would corrupt the Founder's go-live evidence trail):
fed 3 synthetic days of 10 paired run_start/run_end events each through
`compute_window_row` + `append_history_row` into a scratch history file, then
read it back with `loop_controller._load_jsonl` — 3/3 rows appended and
read back correctly, oldest→newest, exactly the shape `clean_live_days`
expects. The real repo's `board/.events.jsonl` does not exist yet (only
`board/.wave-log` is present) — zero counted waves have landed under the
DGO-X event emitter since dispatch has been paused for this workstream's own
governance work. This is the honest, non-conflated finding: **the feeder pipe
is confirmed working; it has simply never had counted-wave input to consume.**
No fix was needed or made to `metrics_history_feeder.py`.

**Verification — observed output, verbatim:**

`python3 scripts/check_heartbeat_readiness.py` — BEFORE (stashed my changes,
re-ran):
```
HEARTBEAT go-live readiness (ADR-0027 SI-7 / §5 WS4) — evidence-gated report
==========================================================================
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  Founder-verified gates (this tool cannot check — confirm before flipping):
    - kill-switch drill passes: python3 scripts/kill_switch_drill.py --smoke
    - zero gate/approval violations in the event log (check_never_auto_approve + interrupts answered)
--------------------------------------------------------------------------
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
  Next: keep the scheduler in shadow (heartbeat_enabled: false) collecting
  counted waves; feed daily rows with metrics_history_feeder.py; re-run this check.
```
exit 1.

AFTER (my changes restored):
```
HEARTBEAT go-live readiness (ADR-0027 SI-7 / §5 WS4) — evidence-gated report
==========================================================================
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  XX monthly credit ceiling .. plan=undeclared  exhausted=False  (FR-004)
  Founder-verified gates (this tool cannot check — confirm before flipping):
    - kill-switch drill passes: python3 scripts/kill_switch_drill.py --smoke
    - zero gate/approval violations in the event log (check_never_auto_approve + interrupts answered)
--------------------------------------------------------------------------
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
  Next: keep the scheduler in shadow (heartbeat_enabled: false) collecting
  counted waves; feed daily rows with metrics_history_feeder.py; re-run this check.
```
exit 1 — the correct additional honest red, exactly as the dispatch
anticipated ("if your active_plan work adds a new readiness blocker, that is
a correct additional red").

`python3 scripts/kill_switch_drill.py --smoke`:
```
kill-switch-drill: running 1 pass(es) of the 6 safety rails...
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```
exit 0 — all 6 rails held (SI-5 now covers both per-day cap and the monthly
ceiling internally, still reported as one `SI-5=ok`).

`python3 scripts/check_loop_mode.py`:
`OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).`
exit 0.

Composite pre-check (§2.0 of the design), extended with the new tests:
```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py -q
```
→ `213 passed` (baseline was `195 passed` per the design; `213 ≥ 195`, per the
count-discipline rule — 18 new tests added, 0 removed, 0 failed).

`python3 scripts/diagnostics.py` → `SCORE = 100/100` (first run was 85/100 —
`ruff-clean` failed on 2 unsorted-import findings + 1 Yoda-condition test
assertion; fixed with `ruff check --fix` + one manual edit; re-ran clean).

`python3 scripts/board_lint.py` → `board_lint: OK — 185 ticket(s) checked, 0
violations.` (1 pre-existing non-fatal body-status WARN on unrelated
DAS-1507, not from this ticket).

`git diff config/features.yaml` / `git diff config/loop.yaml` / `git diff
config/budgets.yaml` → all three empty (confirmed after the full change set).

Full repo test suite: `python3 -m pytest tests/ -q` → `2470 passed, 25
skipped` (pre-existing skips, unrelated to this ticket).

**Files changed:** `scripts/loop_controller.py`, `scripts/flow_router.py`,
`scripts/check_heartbeat_readiness.py`, `tests/test_loop_controller.py`,
`tests/test_flow_router.py`, `tests/test_check_heartbeat_readiness.py`. No
worktree used (main checkout, per dispatch instructions); no commit made
(orchestrator commits at workstream close); no push, no PR (LOCAL-ONLY).

**Routing / escalation (both non-blocking for this ticket's own scope):**
1. **ADR-0027 addendum (design §3.7).** The credit-ceiling wiring landed here
   is a real extension of SI-5's enforcement surface. Per the design, "the
   clean record is an ADR-0027 addendum (or a small amending ADR) ratified by
   the CTO" — a CTO act, not mine. Routing to **SRE / DevOps Lead** (my
   reviewer) to carry forward to the CTO.
2. **`config/budgets.yaml` needs `mustaqil.monthly_credit_ceiling.active_plan`
   added** (a Founder-visible budget declaration, e.g. `active_plan: max_20x`
   — whichever plan is actually live) before the credit-ceiling precondition
   can ever be satisfied. I could not make this edit myself: it is a
   `config/` file, outside this ticket's `zone: scripts` and my dispatch's
   explicit zone lock (a different agent is concurrently on
   `config/risk_taxonomy.yaml` this wave). Until it lands,
   `check_heartbeat_readiness.py` will correctly report NOT READY on this
   precondition even with a clean shadow window — by design, not a bug.
   Routing to **SRE / DevOps Lead** to schedule as a follow-up ticket.

Status set to `in_review`, assignee `sre-lead` per `board/ROUTING.md` (SRE
Engineer → SRE / DevOps Lead). Not self-reviewed.

### 2026-07-24 — SRE / DevOps Lead

**REVIEW — BOUNCED (`in_review` → `in_progress`, assignee → `sre-eng`).** I am the
author of the GATE-2 design this ticket implements (`docs/design/ws-f-tempo-verification.md`),
so I reviewed the code against the spec rather than against the builder's report:
every claim below marked RE-VERIFIED was reproduced by running something myself.
The build is good work — both traps I flagged were genuinely avoided, the closed
decision alphabet held, and the honesty of the readiness reporter held. **One real
defect blocks close**, and it is a deviation from my own design that the builder's
log reported as "resolved exactly as specified".

---

#### D1 (BLOCKER) — the monthly ceiling is computed against LIFETIME spend, not month-to-date

Design §3.5 specifies the `used_usd` source verbatim: *"The month-to-date aggregate
over the same ledger is the analogous number and is the seam DAS-1618 uses — **same
reader, different window**."* The implementation uses the same reader **and the same
window**:

```python
# scripts/loop_controller.py::_monthly_credit_exhausted
ledger = aggregate_spans(events_path, budgets_path)
used_usd = ledger.raw_estimated_cost_usd if ledger is not None else 0.0
credit_state = CreditState(plan=active_plan, used_usd=used_usd)
```

`cost.cost_ledger.aggregate_spans` is documented as *"Aggregate **all** `span` events
from the DGO-X event store"* and takes no time bound; `dgox.events.iter_events`
filters on `ticket_id` / `run_id` / `event_type` only — there is no date filter
anywhere on that path. So `used_usd` is a **lifetime cumulative** total compared
against a **monthly** credit limit.

**Reproduced (scratch only — real config and real event store untouched):** an event
store containing *only* 2025-01 spans, i.e. **$0 spent this billing month**, against
a scratch `active_plan: pro` ($20/mo):

```
Store containing ONLY 2025-01 spans (zero spend this month):
   aggregate_spans lifetime total_usd = 110.0
   _monthly_credit_exhausted(plan=pro, limit=$20) -> True
```

**Why this is a blocker and not a nit.** The number is monotonic and never resets at
the billing-cycle boundary, so once it crosses the plan limit the ceiling **latches
permanently on**. Every subsequent tick returns `idle` citing `sanctioned_pause`; no
counted wave can ever land; `board/.metrics-history.jsonl` can never accumulate a
clean day; go-live becomes structurally unreachable. That is exactly the failure the
design §3.3 names and forbids — *"a fabricated pause would freeze the tick at `idle`
forever and prevent the shadow window from ever accumulating — a false-red that
blocks go-live is as damaging as a false-green."* A monthly ceiling that never resets
is not a monthly ceiling; it is a one-shot lifetime kill switch.

**Why it is not visible today, and why that makes it more dangerous, not less.** The
path is currently inert: `active_plan` is undeclared in `config/budgets.yaml`, so
`_monthly_credit_exhausted` returns `False` before it ever reads the ledger
(RE-VERIFIED). The defect activates the moment **DAS-1629** lands `active_plan` —
and DAS-1629 is a Founder-input config edit whose implementer has no reason to audit
this adapter. I will not close a latent freeze and hand the trigger to a ticket that
cannot see it.

**Two acceptable resolutions — builder's call, CTO ratifies whichever lands:**

- **(A) Give the reader a window.** Add an optional `since` / `window_start` kwarg to
  `cost_ledger.aggregate_spans` (defaulting to `None` = today's behaviour, so
  `_per_day_budget_exceeded` and every other caller are untouched) and pass the start
  of the current billing month. `metrics_history_feeder.filter_events_by_window` is
  the existing pure windowing precedent over the same `created_at` field — reuse its
  shape, do not fork it. This is a **window selection**, not credit arithmetic, so it
  does not breach §3.6.1's "no second credit accountant".
- **(B) Refuse to fabricate.** If a correct month-to-date figure genuinely cannot be
  obtained without new cost accounting (which §3.6.1 forbids), then do **not**
  substitute a lifetime number. Compute no derived `used_usd` at all: require an
  injected `credit_state`, keep the tick inert, and give the missing month-to-date
  source its own readiness blocker — the identical inert-in-the-tick /
  blocking-at-the-gate treatment `active_plan` already gets. Honest-and-inert beats
  approximately-right on a rail that can freeze the substrate.

Either way, add a test that pins the window: spend outside the current billing month
must NOT exhaust the ceiling.

**Related, NOT in this ticket's scope — do not fix here.** `_per_day_budget_exceeded`
carries the identical shape (all-time `raw_estimated_cost_usd` compared to a *per-day*
cap). It is pre-existing (predates DAS-1618) and the builder mirrored it faithfully,
which is how the defect propagated. Fixing it is a separate ticket against the SI-5
per-day rail; I am routing it, not folding it in.

---

#### D2, D3 (NITS — fix while in there, neither blocking on its own)

- `flow_router._dispatch_blocked`'s docstring still enumerates the gate order as
  *"SI-3 break-glass, SI-4 quiet hours, SI-5 per-day budget, SI-6 wave-in-flight"* —
  the new SI-5/FR-004 clause is missing from a docstring whose entire purpose is to
  pin the deterministic order.
- `loop_controller._print_tick` prints `monthly_credit_exhausted = ...`, breaking the
  aligned `=` column the other four rails share. Cosmetic; the rail block is a
  Founder-read surface.

---

#### RE-VERIFIED (I ran these; not accepted on report)

1. **Trap 1 — `admit()` / `gated_admit()` are never reached.** Monkeypatched both
   `ws_b_admission` entrypoints to raise `AssertionError`, then drove
   `_monthly_credit_exhausted` through all four arms (declared+over-limit,
   declared+no-spend, undeclared, missing-file). No forbidden entrypoint fired.
2. **Trap 2 — the ceiling survives `ws_b_agent_sdk_runner` being OFF.** Confirmed the
   flag's live state is `False`, then confirmed the ceiling still evaluates:
   ```
   PRECONDITION ws_b_agent_sdk_runner = False
   declared plan=pro + over-limit spend  -> exhausted = True
   declared plan=pro + no spend          -> exhausted = False
   ```
   The rail does not vanish when WS-B is off. This is the exact regression the design
   was written to prevent, and it is genuinely prevented.
3. **`DECISIONS` did not widen — asserted mechanically.**
   `frozenset({"dispatch","validate","idle"}) == flow_router.DECISIONS` → True.
   `sanctioned_pause` appears in `flow_router.py` only in two docstrings and one
   reason string; it is never an action. Confirmed the assertion has **teeth** by
   mutating `DECISIONS` to a 4-element set in a scratch copy: 8 tests went red,
   including the builder's own
   `test_monthly_credit_exhausted_is_a_reason_never_a_fourth_action` and
   `kill_switch_drill`'s `decision_alphabet_is_closed`.
4. **Blocks dispatch only, never `validate`, never raises.** Exhaustive sweep over all
   5 `TRIGGERS` × `pending_work` × run-count, comparing each context with and without
   exhaustion: 10 transitions, **all** `dispatch → idle`; **zero** cases where
   exhaustion suppressed a `validate`. Junk inputs (`None`, `"yes"`, `1`, `0`,
   `object()`) all returned a valid decision with no raise.
5. **Clause position — the answer is "it does not matter for the decision, only for
   the reason string."** Every `_dispatch_blocked` branch yields `idle`, so
   per-day+credit → SI-5 per-day reason, credit+in-flight → credit reason; the action
   is `idle` in every combination. Position is therefore load-bearing **only** for the
   deterministic reason string `TestDeterminism` pins — which is precisely what the
   design asked for (keep the two SI-5 clauses adjacent). Correctly placed.
6. **`active_plan` residual behaves as designed.** Undeclared plan + over-limit spend
   → `_monthly_credit_exhausted` returns `False` (inert, tick not frozen) while
   `check_heartbeat_readiness` raises the blocker. **`CreditState`'s `max_20x` default
   is NOT inherited**: `CreditState().plan == "max_20x"` but the undeclared path
   returns `False` *before* constructing a `CreditState` at all — the most permissive
   budget is never silently granted. Failure isolation confirmed on missing budgets
   file and missing events file (both `False`).
7. **Both readiness arms, driven from scratch fixtures.** With a hand-built 3-clean-day
   history: declared plan → `VERDICT: READY`, exit 0; the *same* history against the
   real (undeclared) config → `VERDICT: NOT READY`, exit 1, credit blocker only. The
   reporter is genuinely evidence-driven in both directions — the red is not hardcoded,
   and the new precondition genuinely blocks an otherwise-green window.
8. **The feed finding is correctly characterised — "working but unfed", not a
   euphemism.** I exercised the pipe myself rather than reading the builder's account:
   fed 3 synthetic days × 10 paired `run_start`/`run_end` events through
   `metrics_history_feeder.py --all` into a **scratch** history → `Appended 3 day
   row(s)`, 3 well-formed rows, oldest→newest. (First attempt emitted 0 rows because
   I used `timestamp`; the feeder keys on `created_at` — which is the field
   `dispatch_emitter.py` actually writes, so the feeder matches the real producer.)
   `wave_runner.py:859` calls `_de.emit_wave(...)`, so the producer is wired; it has
   simply not run. The gap is upstream and real: `board/.events.jsonl` **does not
   exist** (0 counted waves), `board/.metrics-history.jsonl` **does not exist**
   (0 rows). Both are gitignored, and `git status` on both paths is clean —
   **no synthetic row was written to the real evidence trail.** Confirmed
   `metrics_history_feeder.py` is unmodified and its 43 tests pass.
9. **BEFORE/AFTER readiness, verbatim.** Ran the pristine `HEAD` reporter
   (`git show HEAD:scripts/check_heartbeat_readiness.py`) against the live repo, then
   the working tree. BEFORE: one blocker (`0/3 consecutive clean day(s)`), exit 1.
   AFTER: identical, **plus** the `XX monthly credit ceiling .. plan=undeclared` line
   and the `active_plan is undeclared` blocker, exit 1. Still NOT READY. A newly-green
   readiness would have been the red flag; this is a correct additional honest red and
   matches the builder's transcript exactly.
10. **The 18 new tests earn their keep.** Counted 18 (5 readiness · 6 flow_router ·
    7 loop_controller), 0 removed. Mutation-tested on a full scratch copy of the repo
    (`DASLAB_ROOT` override — the real tree was never mutated):
    - credit check forced to always return "not exhausted" → **1 failed**
      (`test_monthly_credit_exhausted_with_explicit_credit_state_exhausted`);
    - `credit_precondition_met = True` (new blocker neutered) → **4 failed**;
    - `DECISIONS` widened by a 4th action → **8 failed**.
    All three mutations are caught. No test in the WS-F suites asserts a hardcoded
    total (`grep` for `195` / `== N` / `collected` → none), so the design's
    `collected >= baseline` count discipline is respected; the explicit
    `collected >= baseline` assertion itself is DAS-1620's to write.

#### Commands re-run — verbatim

```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py -q
    -> 213 passed in 0.40s          (baseline 195; 213 >= 195, 0 failed, 0 errors)

python3 scripts/kill_switch_drill.py --smoke
    kill-switch-drill: running 1 pass(es) of the 6 safety rails...
    OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
      pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
    kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
    [exit 0]

python3 scripts/check_loop_mode.py
    OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
    [exit 0]

python3 scripts/diagnostics.py
    SCORE = 100/100

python3 scripts/board_lint.py
    board_lint: OK — 187 ticket(s) checked, 0 violations.
    [exit 0]   (1 pre-existing non-fatal body-status WARN on unrelated DAS-1507)

ruff check scripts tests
    All checks passed!   [exit 0]

python3 -m pytest tests/ -q
    2471 passed, 25 skipped in 18.69s
```

`git diff config/features.yaml` / `config/loop.yaml` / `config/budgets.yaml` — all
three **empty**, re-confirmed at review close. No flag flipped; `heartbeat_enabled`
remains `false`; SI-5/SI-6 caps unwidened.

#### ACCEPTED without independent re-derivation (recorded so it is not mistaken for verified)

- That `metrics_history_feeder.py` needed no code change. I exercised it end-to-end
  and ran its 43 tests, but I did not audit its T1–T5/T7 computation against
  `metrics_lib` — that is DAS-1476's `done` scope, not re-litigated here.
- The builder's "first diagnostics run was 85/100, fixed with `ruff check --fix`"
  narrative. I verified only the end state (100/100, ruff clean).
- The merged-PR / green-CI leg of the DoD, outstanding by orchestrator directive
  (whole run is local-only; the orchestrator commits at workstream close). **Not** a
  bounce reason — explicitly excluded from this judgement.

#### Routing (orchestrator to dispatch — I cannot create tickets or spawn agents)

1. **Back to `sre-eng` on this ticket** for D1 (blocker) + D2/D3 (nits). Zone unchanged
   (`scripts`); resolution A touches `scripts/cost/cost_ledger.py`, which is inside it.
2. **DAS-1629 must not land before D1 is fixed.** Declaring `active_plan` while
   `used_usd` is a lifetime aggregate is the trigger that converts this latent defect
   into a permanent dispatch freeze. Recommend the orchestrator add
   `depends_on: [DAS-1618]` to DAS-1629, or hold it until this ticket is `done`.
   No action taken by me on DAS-1629 itself (not my ticket, WIP=1).
3. **NEW WORK DISCOVERED — needs a ticket:** `loop_controller._per_day_budget_exceeded`
   compares an all-time `aggregate_spans` total against the **per-day** cap
   (`caps.per_day.max_cost_usd`). Same class of defect as D1, pre-existing, on the
   SI-5 per-day rail — and it is *already live* in the tick path, unlike D1. Out of
   scope for DAS-1618. Routing to the orchestrator to file.
4. **ADR-0027 addendum (design §3.7)** — already ticketed as DAS-1630 (CTO act). It is
   gated on this ticket closing, so it now waits on the D1 fix. Note for the CTO: the
   addendum's SI-5 text should state the ceiling's **window** explicitly, since that is
   precisely what was ambiguous enough to be implemented wrongly here.

**Escalation to CTO:** none required. D1 is an implementation-conformance defect
inside my own charter (GATE-5 / scheduler-safety surface); routing items 2 and 3 are
orchestrator scheduling, not decisions above my authority.

Not self-reviewed in the prohibited sense: I authored the *design*, `sre-eng`
authored the *code*, and this review found a defect in the code against that design.

### 2026-07-24 — SRE Engineer (bounce fix: D1 blocker + D2/D3 nits)

**D1 fixed — chose resolution (A), "give the reader a window."** Added an
optional `since: datetime | None = None` kwarg to
`cost.cost_ledger.aggregate_spans` (defaults to `None` = today's behaviour
unchanged for every existing caller, confirmed below). When given, a span is
excluded unless its `created_at` >= `since`, parsed with the exact same
`%Y-%m-%dT%H:%M:%SZ` shape `metrics_history_feeder.filter_events_by_window`
already uses over the same envelope field — reused, not forked, per the
reviewer's note. This is a window-selection change, not credit arithmetic, so
it does not breach design §3.6.1 ("no second credit accountant").

Chose (A) over (B) because a correct month-to-date figure *is* obtainable
without new cost accounting — `created_at` is a load-bearing envelope field on
every event (`dgox/events.py` `_ENVELOPE_REQUIRED`), so windowing is a filter
on data already present, not new accounting. (B) would have been the right
call only if no such field existed.

**Shared primitive, built once for both D1 (here) and DAS-1632 (per-day,
separate ticket):** added `loop_controller._window_start(now, *, unit)` —
returns the naive-UTC start of the current calendar `"month"` or `"day"`
containing `now`. `_monthly_credit_exhausted` now computes
`since=_window_start(now, unit="month")` and passes it to `aggregate_spans`;
`tick()` threads its own `_now` through via a new `now=` kwarg so the window
boundary is deterministic per tick, not a fresh clock read inside the adapter.
`_per_day_budget_exceeded` is intentionally NOT touched here (DAS-1632's
scope) — but `_window_start(now, unit="day")` already exists for it to call
without inventing a second windowing shape.

**Verification — observed output, verbatim.**

Reproduction of the reviewer's exact scenario (store containing ONLY 2025-01
spans, evaluated as of `now=2026-07-24`, `active_plan=pro` / $20 cap):
```
Store containing ONLY 2025-01 spans (zero spend this month):
  PRE-FIX SHAPE  lifetime aggregate_spans total_usd = 125.0
  PRE-FIX SHAPE  _monthly_credit_exhausted(plan=pro, limit=$20) -> True
  AFTER-FIX      lc._monthly_credit_exhausted(plan=pro, limit=$20, now=2026-07-24) -> False
```
("PRE-FIX SHAPE" reproduces the buggy call exactly as it appeared in the
bounce log — `aggregate_spans(events_path, budgets_path)` with no window,
which is what `since=None`, the still-supported default, does — proving both
that the old shape really did exhaust wrongly, and that the new `since=None`
default is behaviourally identical to it, i.e. no existing caller's behavior
changed.)

New pinning tests (the load-bearing assertion: prior-period spend must NOT
count):
- `tests/test_cost_ledger.py::test_since_excludes_previous_month_spend` —
  lifetime aggregation of a 2025-01-only store is nonzero; windowed to
  2026-07 it is `None` (fully excluded).
- `tests/test_cost_ledger.py::test_since_includes_current_month_excludes_previous`
  — mixed store: windowed span_count=1 (only the in-window span), lifetime
  span_count=2; windowed cost strictly < lifetime cost.
- `tests/test_cost_ledger.py::test_since_none_is_lifetime_unchanged` — pins
  that `since=None` (default) matches pre-fix lifetime behaviour exactly.
- `tests/test_cost_ledger.py::test_since_excludes_missing_or_unparseable_created_at`
  — a windowed query never silently counts a span with no/garbage timestamp.
- `tests/test_loop_controller.py::test_monthly_credit_exhausted_reproduces_D1_before_fix_would_have_been_true`
  — same store/limit as the manual repro above, asserts the fixed adapter
  returns `False`, after first asserting the lifetime ledger alone would have
  exhausted a $20 cap (proves the fixture is live, not vacuous).
- `tests/test_loop_controller.py::test_monthly_credit_exhausted_true_when_spend_is_in_current_month`
  — positive control: in-window spend still correctly exhausts.
- `tests/test_loop_controller.py::test_monthly_credit_exhausted_mixed_months_only_current_counts`
  — prior-month spend alone would exhaust; adding it to a store with tiny
  in-window spend still returns `False` (excluded, not merely diluted).
- `tests/test_loop_controller.py::test_window_start_month_and_day` /
  `test_window_start_rejects_unknown_unit` — the shared primitive itself.

D2/D3 nits: `flow_router._dispatch_blocked`'s docstring now lists all five
gates in order (`SI-3, SI-4, SI-5, SI-5/FR-004, SI-6`); `loop_controller.
_print_tick`'s rail block `=` columns re-aligned (`break_glass_active`,
`in_quiet_hours`, `per_day_budget_exceeded`, `monthly_credit_exhausted` now
line up).

`python3 scripts/check_heartbeat_readiness.py`:
```
HEARTBEAT go-live readiness (ADR-0027 SI-7 / §5 WS4) — evidence-gated report
==========================================================================
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  XX monthly credit ceiling .. plan=undeclared  exhausted=False  (FR-004)
  Founder-verified gates (this tool cannot check — confirm before flipping):
    - kill-switch drill passes: python3 scripts/kill_switch_drill.py --smoke
    - zero gate/approval violations in the event log (check_never_auto_approve + interrupts answered)
--------------------------------------------------------------------------
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
  Next: keep the scheduler in shadow (heartbeat_enabled: false) collecting
  counted waves; feed daily rows with metrics_history_feeder.py; re-run this check.
```
exit 1 — unchanged from before this fix (correctly still NOT READY, still 0/3,
still the undeclared-`active_plan` blocker; a newly-green readiness here would
have been the red flag, not this).

`python3 scripts/kill_switch_drill.py --smoke`:
```
kill-switch-drill: running 1 pass(es) of the 6 safety rails...
OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
  pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
```
exit 0.

Composite pre-check + new suites:
```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py tests/test_cost_ledger.py -q
```
→ `244 passed` (previous composite baseline `213 passed`; `+31` — 26 from
`test_cost_ledger.py` newly included in this composite run plus 5 new
`test_loop_controller.py` D1 tests minus overlap; 0 failed).

Full repo suite: `python3 -m pytest tests/ -q` → `2480 passed, 25 skipped`
(prior baseline `2471 passed, 25 skipped`; +9 net new tests, 0 failed, 0
newly skipped).

`python3 scripts/diagnostics.py` → `SCORE = 100/100`.

`python3 scripts/board_lint.py` → `board_lint: OK — 189 ticket(s) checked, 0
violations.` (same pre-existing non-fatal body-status WARN on unrelated
DAS-1507, not from this ticket.)

`ruff check scripts tests` → `All checks passed!`

`git diff config/loop.yaml` / `git diff config/budgets.yaml` → both **empty**.
`git diff config/features.yaml` → carries one pre-existing, unrelated line
(`a2a_outbound: false`) from a concurrent WS-A2A workstream that was already
present in `git status` before this dispatch began (not authored by me this
round); `heartbeat_enabled` itself is untouched, still `false`. No flag
flipped by this fix; SI-5/SI-6 caps unwidened.

**Files changed this round:** `scripts/cost/cost_ledger.py` (`since` kwarg +
`_parse_created_at`), `scripts/loop_controller.py` (`_window_start` +
`_monthly_credit_exhausted(now=...)` + `_print_tick` alignment),
`scripts/flow_router.py` (`_dispatch_blocked` docstring), `tests/
test_cost_ledger.py` (4 new windowing tests), `tests/test_loop_controller.py`
(6 new tests: repro + positive control + mixed-months + `_window_start`
unit tests). No worktree used (main checkout); no commit made; no push, no PR
(LOCAL-ONLY).

**Routing (unchanged from the prior round, still standing):**
1. ADR-0027 addendum (design §3.7) — already ticketed as DAS-1630 (CTO act),
   gated on this ticket. Note for the CTO per the reviewer: the addendum's
   SI-5 text should now state the ceiling's window explicitly (the ambiguity
   that let D1 through in the first place).
2. `config/budgets.yaml` still needs `mustaqil.monthly_credit_ceiling.
   active_plan` declared (DAS-1629) — still correctly gated on this ticket per
   the reviewer's instruction ("DAS-1629 must not land before D1 is fixed");
   D1 is now fixed, so DAS-1629 may proceed once this ticket closes.
3. `_per_day_budget_exceeded`'s identical-shape defect is DAS-1632 — out of
   this ticket's scope by the reviewer's own routing; the shared
   `_window_start(now, unit="day")` primitive it needs already exists here.

Status set to `in_review`, assignee `sre-lead` per `board/ROUTING.md` (SRE
Engineer → SRE / DevOps Lead). Not self-reviewed.

### 2026-07-24 — SRE / DevOps Lead

**RE-REVIEW (round 2) — ACCEPTED (`in_review` → `done`, `verified_by: sre-lead`).**
I bounced this ticket for D1; `sre-eng` fixed it with option (A). Because the fix
lands in the *same class of code* that produced the original defect, I reviewed the
fix itself for window bugs rather than re-reading the builder's transcript. Every
claim marked RE-VERIFIED below was reproduced by running something myself, in
scratch only — the real config and the real evidence trail were never written to.

---

#### 1. D1 reproduced independently, pre- and post-fix — GENUINELY FIXED

Built my own scratch store and budgets (never the repo's) and drove the adapter:

```
=== R1: store with ONLY 2025-01 spans (zero spend in 2026-07) ===
  lifetime (since=None)          total_usd = 50.0
  windowed to 2026-07            ledger   = None
  _monthly_credit_exhausted(now=2026-07-24) -> False
  PRE-FIX SHAPE (since=None, lifetime vs $20 cap) would have been ->  True

=== R2: positive control — spend INSIDE current month still exhausts ===
  _monthly_credit_exhausted -> True

=== R3: mixed — huge prior-month + tiny current-month ===
  windowed usd = 0.025          (lifetime would be 50.0)
  _monthly_credit_exhausted -> False
```

Prior-period spend genuinely no longer counts. R2 is the load-bearing counter-check:
the rail was **not** neutered into always-False — in-window spend still exhausts.
R3 proves prior-month spend is *excluded*, not merely diluted. The latch is gone.

#### 2. `_window_start` boundary correctness — CORRECT on every axis I could break

| probe | result |
|---|---|
| month of `2026-07-24T12:34:56.000789Z` | `2026-07-01 00:00:00` (microseconds stripped) |
| exactly `2026-07-01T00:00:00Z` | `2026-07-01 00:00:00` (idempotent at the boundary) |
| year rollover `2026-01-01` | `2026-01-01 00:00:00` (not Dec) |
| month end `2026-03-31T23:59:59Z` | `2026-03-01 00:00:00` |
| leap day `2024-02-29` | `2024-02-01 00:00:00` |
| naive input | `2026-07-01 00:00:00` (assumed UTC, per docstring) |
| `2026-08-01T01:00:00+05:00` | `2026-07-01 00:00:00` — **correct**: that instant is `2026-07-31T20:00Z`, so it belongs to JULY. Offset normalisation happens before truncation, not after. |
| `unit` ∈ {`week`,`MONTH`,`""`,`Day`,`None`} | `ValueError` every time — no silent fallback to a wider window |

**Inclusive/exclusive at the exact instant — the right choice, verified directly.**
The comparison is `if ts is None or ts < since: continue`, i.e. effectively `ts >= since`.
Driven through `aggregate_spans` at the seam:

```
since = 2026-07-01 00:00:00
  span created_at=2026-06-30T23:59:59Z -> excluded
  span created_at=2026-07-01T00:00:00Z -> INCLUDED
  span created_at=2026-07-01T00:00:01Z -> INCLUDED
```

`>=` is correct: the first instant of a month belongs to that month, and the prior
month closes at `23:59:59`. No instant is double-counted and none falls in a gap.

**Naive/aware — no mismatch, and no silent misbehaviour.** `_parse_created_at`
(`strptime %Y-%m-%dT%H:%M:%SZ`) yields a **naive** datetime; `_window_start`
explicitly `.replace(tzinfo=None)` after normalising to UTC, so both sides of the
comparison are naive-UTC. Confirmed `_window_start(...).tzinfo is None`. I probed
the mismatch deliberately: passing an *aware* `since` straight to `aggregate_spans`
raises `TypeError: can't compare offset-naive and offset-aware datetimes` — it
**fails loud, never silently mis-windows**. No in-repo path can produce it
(`_window_start` is the only `since` source and always returns naive), and
`_monthly_credit_exhausted`'s failure isolation would catch it as `False` anyway.
Same naive-only contract as the mandated precedent `filter_events_by_window`.
Recorded as a sharp edge for future callers, not a defect.

#### 3. Missing / unparseable `created_at` — I interrogated the exclusion choice. **EXCLUSION IS CORRECT HERE.** Definite answer, with the reasoning:

The concern is real and correctly stated: dropping an unparseable span UNDER-counts
month-to-date spend, which fails **open** on a budget cap. Measured, the drop is
real and not only for garbage — a *valid but non-canonical* ISO string is dropped too:

```
created_at='2026-07-20T10:00:00.123456Z'  lifetime=25.0  windowed=None
created_at='2026-07-20T10:00:00+00:00'    lifetime=25.0  windowed=None
created_at='garbage' / ''                 lifetime=25.0  windowed=None
```

and `dgox.events.validate_envelope` only checks `created_at` is a **non-empty
string** — it never pins the format, and every builder takes `created_at` as a
caller-supplied argument. So a future caller writing the obvious
`datetime.now(UTC).isoformat()` would emit silently-undated spend.

I still judge exclusion right at **this** seam, for four reasons:

1. **The alternative is strictly worse on this exact rail.** Counting an undated
   span as "in window" makes it count in *every* window forever — that is D1's
   permanent latch reintroduced through the back door. One malformed span would
   freeze the tick at `idle` for good. Trading a bounded under-count for an
   unbounded permanent freeze is a bad trade on the rail that gates go-live.
2. **It is the precedent I mandated.** `metrics_history_feeder.filter_events_by_window`
   documents verbatim "An event with a missing or unparseable `created_at` is
   excluded"; `wave_kpi`, `metrics_lib`, `trends`, and `break_glass` all parse with
   the identical strict format. My own bounce said "reuse its shape, do not fork it."
   A different exclusion policy here would give "in window" two meanings in one repo.
3. **The hazard is not new and is not this ticket's.** The same silent drop already
   governs T1–T5/T7 — i.e. the clean-day *evidence* itself. Making the budget rail
   strict while the evidence feeder stays permissive would be incoherent, and would
   hide the larger problem behind a locally-tidy fix.
4. **Nothing is under-counted today.** `active_plan` is undeclared, so
   `_monthly_credit_exhausted` returns `False` *before* it ever reads the ledger
   (RE-VERIFIED). There is no live fail-open to close.

The right treatment — pin the `created_at` format at write time and/or surface a
count of dropped/undated events so the under-count is *detectable* rather than
silent — must be applied uniformly across `cost_ledger` **and**
`metrics_history_feeder`. **Routed as new work (item 3 below), not a bounce.**

#### 4. `since=None` preserves every existing caller — DEMONSTRATED, not asserted

Signature: `aggregate_spans(store_path=None, budgets_path=..., *, since: datetime | None = None)`.
`since` is **KEYWORD_ONLY** (verified via `inspect`), so no positional caller can
ever drift into it. Static enumeration of every call site in `scripts/`:

```
scripts/agent_eval.py:497       positional=1 kwargs=[]                         since passed: False
scripts/alerting.py:272         positional=0 **kwargs=True                     since passed: False
scripts/check_cost.py:128       positional=0 kwargs=[budgets_path,store_path]  since passed: False
scripts/cockpit.py:329          positional=0 kwargs=[store_path]               since passed: False
scripts/loop_controller.py:296  positional=1 kwargs=[]                         since passed: False   (_per_day_budget_exceeded)
scripts/loop_controller.py:362  positional=2 kwargs=[since]                    since passed: True    (the new caller)
```

The one `**kwargs` site (`alerting.py`) builds its dict literally from `store_path`
plus an optional `budgets_path` — read the source, `since` is unreachable.

Behavioural proof: I loaded `git show HEAD:scripts/cost/cost_ledger.py` alongside
the working-tree module and compared full ledger snapshots on the same 6-span store
(raw totals, all four axes `by_ticket`/`by_run`/`by_tier`/`by_agent`, `unknown_tiers`,
and the `None`-on-empty path):

```
  positional (store, budgets)        HEAD == WORKING_TREE -> True
  kwargs store_path/budgets_path     HEAD == WORKING_TREE -> True
  explicit since=None                HEAD == WORKING_TREE -> True
  empty store HEAD/NEW               -> None None
```

All consumer suites green together: `test_cost_ledger`, `test_alerting`,
`test_alerting_cost`, `test_cockpit`, `test_cockpit_html`,
`test_cockpit_roundtrip_e2e`, `test_agent_eval`, `test_metrics_history_feeder`
→ **190 passed**.

#### 5. `_window_start` genuinely serves DAS-1632 — ADEQUATE, no second mechanism needed

`unit="day"` produces a correct daily lower bound at the exact instant:

```
since = 2026-07-24 00:00:00
  2026-07-23T23:59:59Z -> excluded
  2026-07-24T00:00:00Z -> INCLUDED
  2026-07-24T23:59:59Z -> INCLUDED
```

It is midnight-UTC of the UTC calendar day, which matches
`metrics_history_feeder`'s own day convention (`00:00:00Z–23:59:59Z`) — so the
per-day cap and the daily evidence rows will agree on what "a day" is. DAS-1632 is
therefore a thin application: pass `since=_window_start(now, unit="day")` at
`loop_controller.py:296`. **One note for its implementer:**
`_per_day_budget_exceeded(budgets_path, events_path)` currently takes no `now`, so
it will need `now` threaded from `tick()`'s `_now` exactly as
`_monthly_credit_exhausted` now does — mechanical, but it is the whole diff beyond
the kwarg. A lower-bound-only window is the correct shape for a "spend so far this
period" check; no upper bound is wanted.

#### 6. Nothing else regressed — RE-VERIFIED mechanically

- `flow_router.DECISIONS == frozenset({dispatch, validate, idle})` → **True**.
- Exhaustive sweep over all 5 `TRIGGERS` × `pending_work ∈ {0,1,5}` × three event
  streams, each context run with and without exhaustion: **16 transitions, every
  one `dispatch → idle`; 0 cases where a `validate` was suppressed.** Every returned
  action stayed inside `DECISIONS`.
- **`CreditState`'s `max_20x` default still never inherited.** `CreditState().plan`
  is `max_20x`, but with `active_plan` undeclared and **$2,500 of in-window spend**
  the adapter returns `False` — it exits before constructing a `CreditState` at all.
  The same store with `plan=pro` declared returns `True`, proving the fixture is live.
- Failure isolation intact: missing budgets / missing events / both missing / the
  real repo config → `False` in every case. `now=None`, naive `now`, aware `now`
  all return a bool without raising.
- **Tick inert, not frozen** (`python3 scripts/loop_controller.py --tick`):
  `[SHADOW-OBSERVE] tick: cron_tick -> IDLE`, reason `nothing pending, no checkpoint
  due` — idling for the *correct* reason, with `monthly_credit_exhausted = False`.
  D3 confirmed fixed: the four rails are `=`-aligned. D2 confirmed fixed:
  `_dispatch_blocked`'s docstring now reads `SI-3, SI-4, SI-5 per-day, SI-5/FR-004
  monthly credit ceiling, SI-6` — matching the code's branch order exactly.

#### 7. Readiness still honest — NOT READY, and the evidence trail is still empty

`python3 scripts/check_heartbeat_readiness.py` (verbatim, exit 1):

```
  heartbeat_enabled ........ false (shadow)
  XX clean shadow window ..... 0/3 consecutive clean day(s)  (from 0 history row(s))
  XX monthly credit ceiling .. plan=undeclared  exhausted=False  (FR-004)
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s) (T1>=0.60, T2<=0.15, T7 holds)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
```

Both blockers still present, 0/3 clean days, 0 history rows. **`board/.events.jsonl`
exists = False; `board/.metrics-history.jsonl` exists = False** — no synthetic row
was written to the real evidence trail by either the builder or me.

Flags judged by VALUE, not staging state: `heartbeat_enabled: false`,
`ws_f_heartbeat: false`. `git diff config/loop.yaml` and `git diff
config/budgets.yaml` both empty; `config/features.yaml`'s only line is the
unrelated concurrent-workstream `a2a_outbound: false`. SI-5/SI-6 caps unwidened.

#### 8. The new tests have teeth — mutation-tested on a scratch copy of the repo

The real tree was never mutated (full copy under my scratchpad):

| mutation | caught |
|---|---|
| `aggregate_spans` ignores `since` (revert to lifetime) | **5 failed** — 3 in `test_cost_ledger`, 2 in `test_loop_controller` (incl. the D1 repro test) |
| `_window_start` month → previous month (off-by-one) | **1 failed** (`test_window_start_month_and_day`) |
| `_window_start` month silently degrades to day | **2 failed** |
| unknown `unit` silently falls back to month instead of raising | **1 failed** (`test_window_start_rejects_unknown_unit`) |
| boundary made exclusive (`ts <= since`, drops the 1st at 00:00:00) | **NOT caught** — see residual below |

**Residual (not a bounce):** no test pins the *exact* boundary instant, so an
exclusive-comparison regression would pass CI. I verified the behaviour is correct
by direct probe (§2), and the mandated precedent `filter_events_by_window` is
equally untested at its own boundary — so this is not a coverage regression against
precedent. Routed to DAS-1632, which will exercise the same seam via `unit="day"`
and is the coherent place to pin both boundaries at once.

#### Commands re-run by me — verbatim

```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py tests/test_cost_ledger.py -q
    -> 244 passed in 0.96s

python3 -m pytest tests/test_cost_ledger.py tests/test_alerting.py \
  tests/test_alerting_cost.py tests/test_cockpit.py tests/test_cockpit_html.py \
  tests/test_cockpit_roundtrip_e2e.py tests/test_agent_eval.py \
  tests/test_metrics_history_feeder.py -q
    -> 190 passed in 0.75s        (every aggregate_spans consumer)

python3 scripts/kill_switch_drill.py --smoke
    kill-switch-drill: running 1 pass(es) of the 6 safety rails...
    OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
      pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
    kill-switch-drill: OK — every safety rail held on every pass (zero gate/approval violations, loop off).
    [exit 0]

python3 scripts/check_loop_mode.py
    OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
    [exit 0]

python3 scripts/check_heartbeat_readiness.py
    VERDICT: NOT READY (2 blockers, as quoted in §7)   [exit 1]

python3 scripts/diagnostics.py
    SCORE = 100/100

python3 scripts/board_lint.py
    board_lint: OK — 189 ticket(s) checked, 0 violations.
    [exit 0]   (1 pre-existing non-fatal body-status WARN on unrelated DAS-1507)

ruff check scripts tests
    All checks passed!   [exit 0]

python3 -m pytest tests/ -q
    2480 passed, 25 skipped in 20.53s
```

#### ACCEPTED without independent re-derivation (recorded so it is not mistaken for verified)

- `metrics_history_feeder.py`'s T1–T5/T7 computation against `metrics_lib` — I ran
  its suite and exercised the pipe in round 1, but did not re-audit the metric math.
  That is DAS-1476's `done` scope.
- The builder's account of *which* files it edited this round. I reviewed the diffs
  of `cost_ledger.py`, `loop_controller.py`, and `flow_router.py` directly; I did not
  attempt to separate this round's test edits from round 1's within the same files.
- The exact test counts quoted in the builder's log (`+31`, `+9 net`). I re-ran the
  suites and confirmed the end state and that nothing failed or newly skipped.
- The merged-PR / green-CI leg of the DoD — outstanding by orchestrator directive
  (local-only run). **Explicitly excluded from this judgement**, per dispatch.

#### Verdict

D1 is genuinely fixed, the fix is correct at its boundaries, it preserves every
existing caller demonstrably, and it leaves DAS-1632 a thin application rather than
a second mechanism. D2 and D3 are closed. Readiness is still honestly red and the
real evidence trail is still empty. **`status: done`, `verified_by: sre-lead`.**

#### Routing (orchestrator to dispatch — I cannot create tickets or spawn agents)

1. **DAS-1629 (`config/budgets.yaml` `active_plan`) is now UNBLOCKED.** My round-1
   hold ("must not land before D1 is fixed") is lifted: declaring `active_plan` no
   longer arms a permanent dispatch freeze. It remains a Founder-visible budget
   declaration, so it stays a Founder decision, not an agent one.
2. **DAS-1630 (ADR-0027 addendum, CTO act) is unblocked** — this ticket is `done`.
   Standing note for the CTO: the addendum's SI-5 text must state the ceiling's
   **window** explicitly. That ambiguity is exactly what let D1 through.
3. **NEW WORK DISCOVERED — needs a ticket: undated spend is silently invisible.**
   `dgox.events.validate_envelope` accepts any non-empty string as `created_at`,
   while `cost_ledger._parse_created_at`, `metrics_history_feeder._parse_iso`,
   `wave_kpi`, `metrics_lib`, and `trends` all require exactly
   `%Y-%m-%dT%H:%M:%SZ` and **silently drop** anything else. A caller emitting
   `datetime.now(UTC).isoformat()` would produce spend invisible to the budget
   ceiling *and* metrics invisible to the clean-day evidence, with no signal
   anywhere. Fix uniformly: pin the format at write time in `validate_envelope`
   and/or surface a dropped/undated count from both the ledger and the feeder.
   Zone `scripts`. Not folded into this ticket — it is pre-existing, repo-wide, and
   would fork the window semantics if fixed at one seam only.
4. **Note onto DAS-1632** (already `todo`, `depends_on: [DAS-1618]`, now satisfied):
   (a) `_per_day_budget_exceeded` needs `now` threaded from `tick()`'s `_now`, same
   as `_monthly_credit_exhausted`; (b) add the exact-boundary-instant test that this
   round's mutation testing showed is missing for **both** `unit="month"` and
   `unit="day"` — pin that a span at exactly the window start is INCLUDED.

**Escalation to CTO:** none required. This was implementation-conformance review
inside my own charter (GATE-5 / scheduler-safety surface); all four routing items
are orchestrator scheduling or an already-ticketed CTO act.

Not self-reviewed in the prohibited sense: I authored the *design*, `sre-eng`
authored the *code*, and this round verified the code against that design.
