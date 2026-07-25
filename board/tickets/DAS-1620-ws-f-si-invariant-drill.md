---
id: DAS-1620
title: WS-F Testing — SI-1..SI-7 verification drill, one enforcement point per invariant
status: done
assignee: qa-lead
verified_by: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-005]
labels: [governance, security]
zone: tests
depends_on: [DAS-1619]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-F, part 1).** Run the SI-1…SI-7
verification drill against DAS-1617's evidence map: re-run every named enforcement
artifact and confirm it currently passes. This is verification, not new test
authorship, except where DAS-1618 added a fix that itself needs coverage.

- **SI-1** (one-shot `--tick`, no in-process timer) — confirm `loop_controller.py`'s
  dispatch contract and its existing tests pass.
- **SI-2** (`loop.yaml` stays shadow) — `scripts/check_loop_mode.py` exits 0.
- **SI-3** (break-glass honored) — covered by DAS-1621 (this ticket cross-references,
  does not duplicate).
- **SI-4** (quiet hours) — the quiet-hours config/tests pass; an unset config
  correctly means "no quiet window."
- **SI-5** (budget caps) — `config/budgets.yaml` caps enforced; a per-run/per-day
  breach evaluates to idle + alert (`scripts/check_cost.py` / `scripts/alerting.py`).
- **SI-6** (max-concurrent-waves = 1) — covered by DAS-1621 (cross-referenced).
- **SI-7** (never-auto-approve + ≥3-day shadow) — `check_heartbeat_readiness.py`
  reports honestly; `check_never_auto_approve` passes; gate/interrupt-card semantics
  hold (no auto-approval path exists).

## Acceptance criteria
- [x] Every SI-1..SI-7 invariant has a re-run, currently-passing result recorded
      (test output or command transcript) in this ticket's log — no invariant
      asserted without a fresh run.
- [x] Any invariant that fails is NOT waved through — it is logged as a defect and
      routed back to DAS-1618/1619, and this ticket does not close until re-verified.
      (No SI failed this run; SI-5's alert limb is an open residual, not a failure
      — routed to DAS-1634, not waved through as green.)
- [x] `diagnostics.py` 100/100; full relevant test suite green; merged PR if code
      changed, else a recorded local-run transcript.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Testing, part 1). Re-verifies each SI-1..SI-7
enforcement point named in DAS-1617's evidence map; SI-3/SI-6 cross-referenced to
the dedicated kill-switch drill (DAS-1621) to avoid duplicate test authorship.

### 2026-07-24 — QA Engineer

Ran the SI-1..SI-7 verification drill exactly per `docs/design/ws-f-tempo-verification.md`
§2 (the load-bearing spec — no invented pass criteria). Every command below was
executed fresh in this ticket, local-only, read-only git, zone-locked to
`tests/` + this file. `board/.events.jsonl` and `board/.metrics-history.jsonl`
confirmed absent before and after — no synthetic state written to the real repo.

**Composite pre-check (§2.0):**
```
python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py \
  tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py \
  tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py \
  tests/test_loop_controller.py -q
→ 218 passed in 0.42s, exit 0
```
Pass predicate is `exit 0 ∧ 0 failed ∧ 0 errors ∧ collected >= 195` (never `==
195` — design §2.0 count discipline). 218 >= 195 baseline. **PASS.**

**SI-1 — one-shot, no daemon.**
- `python3 -m pytest tests/test_no_daemon.py -q` → `43 passed`, exit 0
  (includes `TestScannerCanary`, confirmed present — the scanner has teeth).
- `python3 scripts/loop_controller.py --tick --trigger cron_tick` → process
  **returned**, exit 0, printed exactly one decision
  (`[SHADOW-OBSERVE] tick: cron_tick -> IDLE`) plus the safety-rail block.
  Pass predicate is **termination**, not a string match, per design §2.1 — a
  `--tick` that hung would itself be the SI-1 violation. **PASS.**
- OS-scheduler half: **covered-by-construction (G3)** per design §5 — no
  launchd/cron inspector authored or invoked, none is possible in-repo, none
  was invented.

**SI-2 — loop.yaml stays shadow.**
`python3 scripts/check_loop_mode.py` → verbatim
`OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).`,
exit 0. **PASS.**

**SI-3 — break-glass.** Cross-referenced to DAS-1621 (dedicated kill-switch
drill ticket) — not duplicated here per the design's handoff (§7). Confirmed
present in this run's composite smoke line: `SI-3=ok`.

**SI-4 — quiet hours.** `board/schedule.yaml` declares
`quiet_hours: {start: "22:00", end: "06:00", timezone: UTC}`. Read
`loop_controller._in_quiet_hours` (lines ~213-238): an unset/empty/`start==end`
config explicitly returns `False` — "no quiet window" — documented in its own
docstring and enforced by an early-return guard before any time parsing;
malformed time strings are also failure-isolated to `False`. Confirmed this is
the correct direction (unset ⇒ never-quiet, not unset ⇒ always-quiet).
Composite smoke line: `SI-4=ok`. `pytest tests/test_scheduler.py` passed as
part of the composite run above. **PASS.**

**SI-5 — budget caps (idle half verified; alert half is an open residual).**
- `python3 scripts/kill_switch_drill.py --smoke` → `SI-5=ok` (per-day breach
  path).
- `python3 scripts/ws_b_admission.py` → `mustaqil budgets loaded: True`,
  `monthly_credit_ceiling: {'plan_credit_usd': {...}, 'on_exhaustion':
  'sanctioned_pause', 'metered_overflow': False}`, exit 0.
- Confirmed `grep -n "alerting" scripts/loop_controller.py
  scripts/flow_router.py scripts/kill_switch_drill.py` → **zero matches**. The
  ticket text's "idle + alert" wording predates this run; the alert limb does
  not exist on the `--tick` path. This is the known, already-ticketed
  residual (**DAS-1634**, recorded in ADR-0042 as not-ratified-complete). SI-5
  is recorded **idle half PASS, alert half OPEN RESIDUAL → DAS-1634** — not
  marked fully green, no alerting wired by this ticket.
- Verified the previously-flagged "monthly cap compared against lifetime
  total" defect (this run's round-1 finding) is fixed and covered: read
  `loop_controller._monthly_credit_exhausted` (lines 305-368) — it now derives
  `used_usd` from `cost_ledger.aggregate_spans(..., since=_window_start(now,
  unit="month"))`, a month-to-date window, not a lifetime total. Confirmed
  regression tests exist and pass:
  `test_monthly_credit_exhausted_reproduces_D1_before_fix_would_have_been_true`,
  `test_monthly_credit_exhausted_true_when_spend_is_in_current_month`,
  `test_monthly_credit_exhausted_mixed_months_only_current_counts` (all green
  in the full-suite run below).

**SI-6 — max-concurrent-waves = 1.** Cross-referenced to DAS-1621 — not
duplicated here. Confirmed present in composite smoke line: `SI-6=ok`.

**SI-7 — never-auto-approve + >=3-day shadow, honesty over exit code.**
- `python3 scripts/kill_switch_drill.py --smoke` →
  ```
  kill-switch-drill: running 1 pass(es) of the 6 safety rails...
  OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).
    pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok
  kill-switch-drill: OK — every safety rail held on every pass (zero
  gate/approval violations, loop off).
  ```
  exit 0. **PASS.**
- `python3 scripts/check_never_auto_approve.py --board board --config
  config/risk_taxonomy.yaml` → `OK: 195 tickets checked, no never-auto-approve
  violations.`, exit 0. **PASS.**
- `python3 scripts/check_heartbeat_readiness.py` →
  ```
  VERDICT: NOT READY. Blockers:
    - insufficient clean shadow window: 0/3 consecutive clean day(s)
    - monthly credit ceiling not enforceable: mustaqil.monthly_credit_ceiling.active_plan is undeclared
  ```
  exit **1**. Per design §2.2 the pass predicate here is **honesty
  (verdict ⟺ evidence on disk), not exit 0**. `0/3` clean days on-disk (no
  `board/.metrics-history.jsonl`) correctly renders `NOT READY`; this red is
  **CORRECT** and is **NOT** treated as a failing invariant, and nothing was
  changed to make it green. **PASS** against the honesty predicate. (Also
  confirms `check_heartbeat_readiness.assess()` — read directly, lines 79-118
  — requires flag-off AND window-met AND credit-precondition-met with no
  bypass path; a `READY` verdict under any of those three false is
  structurally impossible.)

**Adversarial pass (looked for a third defect, per instructions).** Reviewed
`ws_b_admission.check_credit_exhaustion` (fail-safe-inert on unknown plan, no
false-exhaustion), `loop_controller._monthly_credit_exhausted` (failure-isolated
to `False`, no false-pause), and `check_heartbeat_readiness.assess()` (whitelist
`ready` logic, no bypass). Re-ran `scripts/heartbeat_go_no_go.py` — verbatim
`VERDICT: NO-GO`, exit 1, with an explicit `[FAIL]`/`[UNKNOWN]` breakdown
(2 failing gates, 1 unknown = event log absent, correctly never counted as a
pass). This confirms the previously-found "GO on a corrupted budget config"
defect (round-2 finding) is fixed: the verdict function is a whitelist — GO
requires positive PASS evidence on every gating line, UNKNOWN never counts.
No new defect found this round; the two prior defects (monthly-cap-vs-lifetime,
corrupted-config GO) are both fixed and test-covered in the current tree.

**Full verification suite:**
- `python3 -m pytest -q` (full repo) → `2532 passed, 25 skipped`, exit 0.
- `python3 scripts/diagnostics.py` → `SCORE = 100/100`.
- `python3 scripts/board_lint.py` → `OK — 193 ticket(s) checked, 0
  violations.` (one non-fatal, pre-existing, unrelated body-status WARN on
  DAS-1507).
- `ruff check scripts tests` → `All checks passed!`

**Verdict.** All seven invariants verified against the design's stated
predicates; none failed. SI-1 in-repo half PASS + OS half covered-by-construction
(G3, not invented). SI-2 PASS. SI-3/SI-6 cross-referenced to DAS-1621 (not
duplicated). SI-4 PASS, unset-config direction confirmed correct. SI-5 idle
half PASS, alert half OPEN RESIDUAL → DAS-1634 (not waved through as green).
SI-7 PASS on the honesty predicate (exit 1 is correct and untouched). No new
test authored — DAS-1618's own suite already added 18 tests covering exactly
the credit-ceiling/readiness/readiness-CLI paths this drill exercises; no
genuine coverage gap found. Setting `status: in_review`, routing to
**qa-lead** (GATE-4 owner) per ROUTING.md.

### 2026-07-24 — QA Lead

GATE-4 review of the SI-1..SI-7 drill. I reviewed the **binding** — whether each
command genuinely constrains the invariant it claims — not the transcript. A
drill that runs seven commands and reports seven passes proves nothing unless
the predicates have teeth, so every load-bearing claim below was re-executed or
re-derived from source in this run, local-only, read-only git.

**A. Re-run independently (my own execution, exit codes checked).**

| Command | My result | Ticket's claim | Match |
|---|---|---|---|
| `check_loop_mode.py` | verbatim `OK: loop off — mode 'shadow', auto_apply false (levers only, no controller).`, **exit 0** | same | ✅ |
| `loop_controller.py --tick --trigger cron_tick` | process **returned**, elapsed 0s, **exit 0**, one decision `[SHADOW-OBSERVE] tick: cron_tick -> IDLE` + rail block | same | ✅ |
| `pytest tests/test_no_daemon.py -q` | `43 passed` | `43 passed` | ✅ |
| WS-F composite (8 files) | `218 passed in 0.41s`, exit 0 | `218 passed` | ✅ |
| `kill_switch_drill.py --smoke` | `SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok`, **exit 0** | same | ✅ |
| `check_never_auto_approve.py` | `OK: 195 tickets checked, no never-auto-approve violations.`, exit 0 | same | ✅ |
| `check_heartbeat_readiness.py` | `VERDICT: NOT READY` (0/3 clean days + undeclared `active_plan`), **exit 1** | same | ✅ |
| `heartbeat_go_no_go.py` | `VERDICT: NO-GO`, **exit 1**, 2 FAIL + 1 UNKNOWN | same | ✅ |
| `pytest -q` (full repo) | `2532 passed, 25 skipped` | same | ✅ |
| `diagnostics.py` | `SCORE = 100/100` | same | ✅ |
| `board_lint.py` | `OK — 193 ticket(s) checked, 0 violations` + the pre-existing DAS-1507 body-status WARN | same | ✅ |
| `ruff check scripts tests` | `All checks passed!` | same | ✅ |

`board/.events.jsonl` and `board/.metrics-history.jsonl` confirmed **ABSENT**
before the run, and again **after** the `--tick` — the drill wrote no synthetic
state into the real repo. Spot-checked exit codes: `check_heartbeat_readiness`
= 1 and `check_loop_mode` = 0 as claimed; `heartbeat_go_no_go` = 1 as claimed.

**B. The three counter-intuitive predicates — checked against the design, not
against intuition.** `docs/design/ws-f-tempo-verification.md` §2.0/§2.1/§2.2
state these verbatim; the builder applied all three correctly:

1. **SI-7 honesty, not exit 0.** Design §2.2 makes the predicate `verdict ⟺
   evidence-on-disk`. Exit 1 with `0/3 clean days` is the CORRECT reading of an
   absent `board/.metrics-history.jsonl`. Nothing was edited to make it green,
   and exit 1 was **not** logged as a failing invariant. I went further and
   proved the verdict cannot be faked: an exhaustive truth table over
   `assess()`'s three gates (`flag_on` × `window_met` × `active_plan` ×
   `credit_exhausted`, 32 combinations, using the suite's own `_clean_day()`
   helper so the positive case is genuinely reachable) yields **exactly 1 READY**
   — the all-gates-satisfied combination. Zero leaks. It is a strict
   conjunction with no bypass path.
2. **SI-1 termination, not string match.** Design §2.1: "verified by
   *termination*, not by a string: a `--tick` that did not return would be the
   daemon SI-1 forbids." I timed the process — it returned in 0s with exit 0.
   Termination is what was checked.
3. **No hardcoded suite counts.** Design §2.0 requires `exit 0 ∧ 0 failed ∧ 0
   errors ∧ collected ≥ baseline`, "never an equality on a hard-coded total…
   A drill that asserts `== 195` fails the moment the gap it was built to close
   is closed." The drill asserts `218 >= 195`. I grepped
   `kill_switch_drill.py`, `heartbeat_go_no_go.py`,
   `check_heartbeat_readiness.py` and their tests for `== 195`/`195`/`218`/`2532`
   equality assertions — **zero matches**. Note the design's own §2.1 line
   records `N = 182` for never-auto-approve where we now observe 195; the
   predicate is the OK-line + exit 0, not the count, so the drift is correct
   behaviour, not a miss.

**C. SI-4's direction — verified by execution, not by reading.** This is the
inverted-default that would read fine in a transcript, so I exercised
`loop_controller._in_quiet_hours` directly rather than trusting the docstring.
Unset key, explicit `None`, empty dict, empty strings, `start == end`, and a
malformed time string **all return `False`** — and I swept **all 1440 minutes of
the day** for both the unset and empty configs: quiet at *no* minute. The
direction is `unset ⇒ never quiet`, i.e. "no quiet window", which is correct;
the inverted reading (`unset ⇒ always quiet`) would have frozen the substrate so
it never dispatches. I also confirmed the predicate still **binds** when a real
window is set, so the `False` default is not vacuous: `22:00–06:00` returns
`True` at 23:00 and 03:00 (midnight wrap correct) and `False` at 12:00;
same-day `09:00–17:00` returns `True` at 12:00, `False` at 20:00.

**D. SI-5 correctly NOT marked fully green.** Confirmed `grep -n "alerting"
scripts/loop_controller.py scripts/flow_router.py scripts/kill_switch_drill.py`
→ **zero matches** (`scripts/alerting.py` exists as a module but is never
reached from the `--tick` path). The ticket records SI-5 as **idle half PASS,
alert half OPEN RESIDUAL**, not a blanket PASS. The residual is genuinely
tracked: `board/tickets/DAS-1634-si5-idle-and-alert-limb-unwired.md` exists
(`status: todo`, `assignee: sre-eng`) and `docs/adr/0042*.md:234` records it as
"**Recorded as an open residual, not ratified as complete.**" This is the
correct handling — a blanket SI-5 PASS would have waved through a known gap.

**E. SI-3/SI-6 are genuine deferrals, not silent skips.** The ticket labels both
"cross-referenced to DAS-1621 — not duplicated here" and cites only the smoke
line `SI-3=ok`/`SI-6=ok` as supporting evidence; it does **not** assert the full
drill was performed here. Verified `DAS-1621` is `status: todo`, `assignee:
qa-eng`, `depends_on: [DAS-1620]` — so it is blocked on this ticket by design and
the deferral is real. No false claim of verification.

**F. Adversarial pass — I re-verified both prior defects empirically and hunted
a third.**
- **D1 (monthly cap vs lifetime total) — genuinely fixed.** Not accepted on a
  code read: I built a synthetic span ledger **in the scratchpad** (never
  `board/.events.jsonl`) and ran it through the real
  `cost_ledger.aggregate_spans`. A June-only spend of **$100,000 reads $0.00
  month-to-date**; a July spend reads in full; a mixed June-$100k + July-$0.03
  ledger reads **$0.03** month-to-date against $100,000.02 lifetime. Under the
  old lifetime total the ceiling would have latched permanently once crossed.
  `_window_start(2026-07-24, month)` = `2026-07-01 00:00:00`. Also confirmed
  `_monthly_credit_exhausted` trips correctly on an injected `CreditState`:
  `$0`→False, `$100`→False, `$300`→**True** against the `max_20x` $200 cap.
- **D2 (`verdict()` whitelist) — genuinely fixed.** Probed
  `heartbeat_go_no_go.verdict()` with novel states, which is the exact failure
  mode a blacklist would miss: all-PASS→GO; one FAIL→NO-GO; one UNKNOWN→NO-GO;
  a novel `"SKIPPED"`→NO-GO; even lowercase `"pass"`→**NO-GO**; and an **empty
  gating list → NO-GO**. It is a true whitelist — UNKNOWN and any unrecognised
  state block GO.
- **My own third-defect hunt found no defect.** Two candidates chased to
  ground and dismissed: (i) `_window_start` returns a *naive* UTC datetime,
  which would raise `TypeError` against aware timestamps and be swallowed by
  `_monthly_credit_exhausted`'s broad `except` — but `cost_ledger._parse_created_at`
  also returns naive, and the producer `scripts/dgox/events.py:100` writes
  exactly `%Y-%m-%dT%H:%M:%SZ`, so producer and consumer agree and no exception
  path exists; (ii) `_in_quiet_hours` ignores `quiet_hours.timezone` — but
  `board/schedule.yaml:43` explicitly annotates that field "all comparisons are
  in UTC; this field is documentation only", so it is a declared convention,
  not silent drift.

**G. What I accepted rather than re-derived.** SI-1's **OS-scheduler half**
remains covered-by-construction (G3, design §5) — nothing in-repo installs or
inspects a launchd/cron entry, and I did not invent an inspector; it is
correctly reported as UNKNOWN in `heartbeat_go_no_go`, never as a pass. The
`SI-3`/`SI-6` full drills are DAS-1621's scope, not re-run here. The claim that
DAS-1618 added 18 tests covering the credit-ceiling/readiness paths I accepted
from the composite suite passing, without recounting them individually.

**Two observations for downstream, neither a bounce.** (1) When `since` is
given, `aggregate_spans` **excludes** a span with an unparseable `created_at`,
which under-counts spend and is therefore fail-open for a ceiling. My probe
confirmed it is safe *today* only because the sole producer
(`scripts/dgox/events.py:100`) writes exactly `%Y-%m-%dT%H:%M:%SZ` and
`_parse_created_at` strptimes that same literal-`Z` format — both naive UTC, so
no aware/naive `TypeError` exists on the path. On checking the board I found
this is **already tracked as DAS-1633** ("Pin one `created_at` format contract
so undated spans stop vanishing from budgets and evidence", `todo`,
`backend-eng-2`, found by SRE Lead in the DAS-1618 round-2 re-review), which
names this exact fail-open consequence repo-wide. So this is a **known tracked
residual, not a new finding** — recording it here only as independent
confirmation from the SI-5 side that the risk is real. (2) `heartbeat_go_no_go`'s FAIL on
`monthly_credit_ceiling.active_plan` being undeclared is the *same* residual
that makes `_monthly_credit_exhausted` inert in the tick — one root cause
surfacing in two reports, correctly, in both places.

**Decision — GATE-4 part 1 CLOSED.** Every SI has a fresh, currently-passing
result under the design's own predicate; no invariant was waved through; the one
known gap (SI-5 alert limb) is recorded as an open residual routed to DAS-1634
rather than painted green; SI-7's red is honest and untouched. Accepting as
**done**, `verified_by: qa-lead`. **DAS-1621 (WS-F Testing part 2 — kill-switch
and break-glass drill, SI-3/SI-6) is now unblocked.** Per orchestrator directive
the merged-PR/green-CI condition is outstanding org-wide and is not a bounce
reason here; the local-run transcripts above satisfy the third acceptance
criterion's "else" branch.
