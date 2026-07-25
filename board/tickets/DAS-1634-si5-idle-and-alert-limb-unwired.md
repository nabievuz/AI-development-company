---
id: DAS-1634
title: Wire the alert limb of the SI-5 budget rails so a sanctioned pause is not silent
status: done
assignee: sre-lead
verified_by: sre-lead
author: cto
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-004]
labels: [governance]
zone: scripts
depends_on: [DAS-1640]
created: 2026-07-24
updated: 2026-07-25
---

## Description

**Found by the CTO while ratifying ADR-0042 against the shipped code (DAS-1630).
Pre-existing — predates DAS-1618 and was outside its scope. Recorded in ADR-0042 as
an OPEN RESIDUAL, explicitly not ratified as complete.**

SI-5 / FR-004 specifies **"idle + alert"** on a budget-rail trip. The `idle` half is
wired and now correct. The **alert half does not exist**: `scripts/loop_controller.py`
contains no `alerting` reference at all — not for the monthly credit ceiling, and not
for the pre-existing per-day cap.

**Why a silent pause is the wrong failure.** When a budget rail trips, the substrate
stops dispatching. With no alert, that stop is indistinguishable from a quiet night:
no ticket moves, no wave lands, and nothing anywhere says why. The clean-day counter
simply fails to advance, and the ≥3-day shadow window silently stalls. The operator
learns about it by noticing an absence — which is exactly the observability failure
the tempo substrate is supposed to eliminate. A rail that fires without telling
anyone is only half a safety mechanism.

**Reuse the existing alerting path — do not author a second one.** The repo already
has alerting machinery (`scripts/alerting*`, and the cost-breach alerting landed by
DAS-1461). Find it, read it, and route the budget-rail trip through it. A parallel
notifier would fragment exactly the signal this ticket exists to consolidate.

Cover **both** rails in one mechanism — the monthly credit ceiling and the per-day
cap. DAS-1632 fixes the per-day window; this ticket makes both audible. It is
sequenced behind DAS-1632 so the alert fires on a correctly-measured trip rather
than on the current lifetime-total false positive.

**Distinguish the two states in whatever the alert says.** `sanctioned_pause` on a
genuine ceiling hit is expected, healthy behavior — the system working. That must not
read the same as an unexpected stall. An alert that cries wolf on normal operation
gets muted, and then the real one is missed too.

⛔ Do NOT flip `heartbeat_enabled`. Do NOT widen the SI-5 or SI-6 caps. Do NOT change
the `idle` decision semantics — `sanctioned_pause` stays a reason string and
`flow_router.DECISIONS` stays the closed alphabet `{dispatch, validate, idle}`
(ADR-0042 SI-5.3; that closure is SI-7's structural enforcement).

## Acceptance criteria
- [x] A budget-rail trip (monthly ceiling AND per-day cap) emits an alert through the EXISTING alerting path — no second notifier.
- [x] The alert distinguishes an expected `sanctioned_pause` from an unexpected stall.
- [x] A test proves the alert fires on a trip and does NOT fire on a normal tick — both directions.
- [x] `DECISIONS` unchanged; `idle` semantics unchanged; no cap widened.
- [x] `check_heartbeat_readiness.py` still honest (NOT READY, 0/3 clean days); `kill_switch_drill --smoke` 6 rails green.
- [x] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; `git diff config/features.yaml|loop.yaml|budgets.yaml` all empty; no `project:` field (R9).

## Log
### 2026-07-24 — CTO
Discovered while ratifying `docs/adr/0042-adr0027-addendum-monthly-credit-ceiling.md`
against the shipped `loop_controller.py` / `flow_router.py` (DAS-1630). Recorded in
ADR-0042 as an open residual rather than ratified as satisfied — the addendum
documents what the code does, and the code does not alert. Recorded by the
orchestrator in the same run and sequenced behind DAS-1632 so the alert fires on a
correctly-windowed trip.

### 2026-07-24 — Orchestrator (orchestrator-recorded)
Dependency retargeted `DAS-1632` → `DAS-1640` after the DAS-1632 review (SRE Lead).
DAS-1632 is `done`, so the window half is settled — but the reviewer established
precisely which attachment point makes this ticket thin:

- Attaching to `tick()`'s `safety_rails["per_day_budget_exceeded"]` is SAFE: that
  boolean is now day-windowed and demonstrably **non-latching** (the reviewer showed
  it going `True` then back to `False`).
- Attaching to `scripts/alerting.py` instead would **inherit an un-fixed defect** —
  `alerting.gather_readings` still computes `per_day_cost_usd` from an unwindowed
  `aggregate_spans` (measured $17.00 where today's true spend is $2.00). The alert
  would fire off a monotonic lifetime total that never resets, which is the exact
  failure this run spent two rounds removing from the tick rail.

DAS-1640 fixes that alerting path, so this ticket now waits on it. Whichever
attachment point is chosen, verify the boolean it reads actually resets.

### 2026-07-25 — SRE Engineer

DAS-1640 is landed (`alerting.gather_readings`'s `per_day_cost_usd` is now
day-windowed via the same `_window_start` primitive `loop_controller` uses).
Wired the alert limb.

**Design.** Attached at `loop_controller.tick()`, after `decision` is already
computed via `route_from_store()` — the SI-5 booleans (`budget_exceeded`,
`credit_exhausted`) it already reads for the router are reused verbatim, no
new reader. Added ONE new pure function, `alerting.sanctioned_pause_alert(per_day_budget_exceeded, monthly_credit_exhausted) -> dict | None`
(`scripts/alerting.py`), which returns `None` when both rails are cold and
otherwise an alert dict in the EXACT shape `evaluate_alerts()` already
produces (`{severity, metric, message}`) — same schema, same module, no
second notifier, no second print path. `tick()` calls it via a lazy
`import alerting` inside the function body (mirrors the existing lazy
`feature_flags`/`break_glass`/`flow_router` imports) — lazy specifically
because `alerting.py` imports `loop_controller._window_start` at module top
level, so a top-level `import alerting` in `loop_controller.py` would be a
load-time cycle; the lazy import inside `tick()` runs only after
`loop_controller` is already fully loaded, so there is no cycle. The result
dict gained one new key, `"alert"`, populated after `decision`/`promotion`/
`safety_rails` are already finalized — the alert can only ever describe the
decision, never influence it. `_print_tick()` prints the alert line when
present.

**Design-tension resolution (severity distinction, spelled out).**
`evaluate_alerts()`'s existing COST alert (DAS-1461, `budget_governor`
breach against the org-wide informational cap) is `critical` — appropriate,
because that path means someone is spending more than intended. A
`sanctioned_pause` at the substrate's OWN `mustaqil` SI-5 ceiling is the
opposite: the rail doing exactly its job. `sanctioned_pause_alert()` returns
severity `"info"` and metric tag `"SI-5"` (vs. `"COST"`), which gives a
reader two independent, non-collapsing signals:
  1. **Severity** — `"info"` sits outside `filter_quiet()`'s `ANOMALY` set
     (`{"warning", "critical"}`), so Quiet Mode and `--fail-on-critical` (the
     CI gate) never surface a sanctioned pause and can never be trained to
     mute it alongside a real breach — the two paths are structurally
     disjoint in the same filter that would otherwise conflate them.
  2. **Metric tag + message text** — `"SI-5"` vs `"COST"`, and the message is
     explicit: `"sanctioned_pause — substrate paused at its ... as designed;
     expected/healthy, not a breach or unexpected stall"`. An unexpected
     stall (e.g. an exception degrading `route()` to idle, or break-glass/
     quiet-hours) never gets a `sanctioned_pause` alert at all — only a
     per-day/monthly rail trip does — so a reader sees this alert's presence
     as itself informative: "the substrate paused BECAUSE of SI-5, not for
     an unknown reason."

**Verification — observed, not claimed (2026-07-25):**

1. Full test suite: `python3 -m pytest -q` → `2612 passed, 25 skipped`.
2. WS-F composite suite (per `docs/design/ws-f-tempo-verification.md` §2.0):
   `python3 -m pytest tests/test_no_daemon.py tests/test_check_loop_mode.py tests/test_break_glass.py tests/test_scheduler.py tests/test_flow_router.py tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py tests/test_loop_controller.py -q`
   → `270 passed` (baseline was 195; predicate is `collected >= baseline`, satisfied — the growth is exactly this ticket's new tests plus other in-flight work, never a hardcoded equality).
3. `tests/test_loop_controller.py::test_alert_wiring_does_not_change_the_decision` —
   byte-identical dispatch proof: same tick inputs (a per-day trip), run once
   normally and once with `alerting`'s import forced to raise
   (`builtins.__import__` monkeypatched to reject `import alerting` only),
   asserts `without_alert["decision"] == with_alert["decision"]` AND
   `safety_rails`/`promotion`/`mode` all equal, while `alert` differs
   (`None` vs. populated) — PASSED. This is the mechanical proof the alert
   changes observability only.
4. Per-day trip emits the alert:
   `tests/test_loop_controller.py::test_tick_emits_alert_on_per_day_trip` —
   `mustaqil.caps.per_day.max_cost_usd=1`, ~$65 opus spend today → observed
   `r["alert"] == {"severity": "info", "metric": "SI-5", "message": "sanctioned_pause — substrate paused at its per-day budget cap (SI-5) as designed; expected/healthy, not a breach or unexpected stall"}` — PASSED.
5. Monthly trip emits the alert:
   `tests/test_loop_controller.py::test_tick_emits_alert_on_monthly_trip` —
   `active_plan=pro` ($20 cap), ~$65 opus spend this month → observed
   `r["alert"]["metric"] == "SI-5"`, message contains `"monthly credit
   ceiling"`, `severity == "info"` (never `"critical"`) — PASSED.
6. Severity distinction against the real critical COST path:
   `tests/test_loop_controller.py::test_sanctioned_pause_alert_severity_distinct_from_critical_cost_breach`
   — `alerting.sanctioned_pause_alert(True, False)["severity"] == "info"` vs.
   a real `alerting.evaluate_alerts()` COST breach returning
   `severity == "critical"`; `filter_quiet([sanctioned]) == []` (dropped) while
   `filter_quiet([cost_breach]) == [cost_breach]` (kept) — PASSED, proving
   the two are mechanically distinguishable, not just differently worded.
7. `flow_router.DECISIONS` closed alphabet, asserted mechanically:
   `python3 -c "import sys; sys.path.insert(0,'scripts'); import flow_router; assert flow_router.DECISIONS == frozenset({'dispatch','validate','idle'})"`
   → printed `DECISIONS OK: frozenset({'validate', 'dispatch', 'idle'})`, no
   `AssertionError`.
8. `python3 scripts/check_heartbeat_readiness.py` → `VERDICT: NOT READY.`
   (`0/3 clean shadow window`, `monthly credit ceiling` plan undeclared),
   exit `1` — correct red, unchanged by this wiring.
9. `python3 scripts/kill_switch_drill.py --smoke` →
   `pass[000] ok: SI-3=ok SI-4=ok SI-5=ok SI-6=ok SI-7=ok SI-2=ok`, exit `0`.
10. `python3 scripts/heartbeat_go_no_go.py` → `VERDICT: NO-GO` (2 gates
    failing, 1 UNKNOWN — clean shadow window and monthly-credit
    enforceability, plus the absent event log), exit `1` read directly.
11. `python3 scripts/diagnostics.py` → `SCORE = 100/100` (first pass hit
    `85/100` on a ruff SIM300 Yoda-condition finding in my own new test;
    fixed with `ruff check --fix tests/test_loop_controller.py`, re-ran clean).
12. `ruff check scripts tests` → `All checks passed!`
13. `python3 scripts/board_lint.py` → `OK — 198 ticket(s) checked, 0
    violations.` (one unrelated pre-existing WARN on DAS-1507 body prose,
    non-fatal, not from this ticket).
14. `git diff config/*.yaml` — non-empty overall (a2a-goal work already
    in-flight on this branch touches `features.yaml`/`rbac.yaml`/
    `tenant_boundary.yaml`/`risk_taxonomy.yaml`, pre-existing per the branch's
    starting `git status`, none of it mine — I never opened `config/`).
    Scoped to this ticket's constraint: `git diff config/loop.yaml
    config/budgets.yaml` → 0 lines (empty), confirmed with `wc -l`. No cap
    widened, no flag flipped, `heartbeat_enabled` untouched.
15. `board/.events.jsonl` and `board/.metrics-history.jsonl` — confirmed
    still absent (`ls` → `No such file or directory` for both).

**Files touched (zone: `scripts` + `tests` + this ticket, honored):**
- `scripts/alerting.py` — added `sanctioned_pause_alert()` (pure, no I/O).
- `scripts/loop_controller.py` — `tick()` gained the lazy `alerting` call +
  `result["alert"]`; `_print_tick()` gained one conditional print line. No
  other function touched — kept minimal per the DAS-1641 zone-sharing note.
- `tests/test_loop_controller.py` — 9 new tests (alert-present/absent on
  normal/per-day/monthly ticks, byte-identical-dispatch proof, severity
  distinction against a real cost breach, `sanctioned_pause_alert(False,
  False) is None`, `DECISIONS` closure).
- `board/tickets/DAS-1634-si5-idle-and-alert-limb-unwired.md` — this file.

**ADR-0042 SI-5 status (flagging for CTO, not editing the ADR — out of
zone).** With this landed, both SI-5 alert-limb halves the addendum
describes now exist in code: `idle` (pre-existing, correct) and `alert`
(this ticket, routed through the existing `alerting.py` machinery, severity-
distinct from a real breach). As far as this ticket's scope goes, the
open residual recorded in ADR-0042 is closed in the code. Two things remain
genuinely outside my authority/zone and are the CTO's to judge: (a) whether
the ADR-0042 text itself should be updated to ratify this as satisfied
(a docs/adr edit — not my zone), and (b) the alert is currently observable
only via `tick()`'s returned dict / stdout print — nothing yet *consumes*
it (no log line to `board/.events.jsonl`, no external notification channel).
Whether "audible" for FR-004 purposes requires a persistence/consumption
step beyond stdout is a product/ops call, not something I judged unilaterally
in-scope for this ticket (the ticket's acceptance criteria ask only that the
alert "fires through the existing alerting path," which it now
mechanically does).

Status set to `in_review`, assignee `sre-lead` (reviewer, per ROUTING.md;
never self-review).

### 2026-07-25 — SRE / DevOps Lead (REVIEW — accepted, done)

Reviewed as the reviewer (builder was sre-eng, reports to me). I did not
rubber-stamp the two subtleties the builder flagged; I re-derived every
mechanical claim on my own scratch fixtures, not the builder's helpers.

**RE-VERIFIED (run by me, 2026-07-25 — verbatim):**
- Independent scratch harness (own budgets.yaml + own event ledger, own
  `now`): per-day trip → `decision.action=idle`, `alert=info/SI-5`; monthly
  (pro, $20) trip → `idle`, `info/SI-5`, message contains "monthly credit
  ceiling"; both rails cold → `alert=None`; `sanctioned_pause_alert(False,
  False) is None`. Neither rail ever emits `critical`.
- **Byte-identical dispatch, re-derived my own way:** ran the SAME per-day
  tick twice — once normally, once with `builtins.__import__` forced to reject
  `import alerting` — and asserted every non-`alert` result key
  (`decision`/`safety_rails`/`promotion`/`mode`) is byte-identical; only
  `result["alert"]` differs (`populated` vs `None`). The alert can never
  change a dispatch decision → SI-7 structural closure intact.
- **Lazy import is sound / inert on failure:** `import loop_controller` then
  `import alerting`, AND the reverse order (`alerting` first, which imports
  `loop_controller._window_start` at module top) both succeed in clean
  processes — no load-time cycle. A forced `alerting` ImportError inside
  `tick()` degrades to `alert=None` (no crash) — a monitoring add-on cannot
  crash the tick.
- `flow_router.DECISIONS == frozenset({dispatch, validate, idle})` asserted
  mechanically. No fourth decision.
- Gates: `check_heartbeat_readiness.py` → NOT READY, exit 1;
  `kill_switch_drill.py --smoke` → 6 rails green, exit 0;
  `heartbeat_go_no_go.py` → NO-GO, exit 1 (read directly); WS-F composite →
  270 passed; full repo suite → **2612 passed, 25 skipped**;
  `diagnostics.py` → **100/100**; `board_lint.py` → 198 checked, 0 violations
  (the DAS-1507 body-prose WARN is pre-existing/unrelated); `ruff check
  scripts tests` → clean. `git diff config/loop.yaml config/budgets.yaml` → 0
  lines; `board/.events.jsonl` and `board/.metrics-history.jsonl` both absent.
  No hardcoded suite-count equality used (predicate is `collected >=
  baseline`).

**ADJUDICATED (the two flagged subtleties — my verdicts, not the builder's):**

1. **Severity `info` does NOT reintroduce the silence — ACCEPT.** I chased the
   concern one step past the builder. `filter_quiet` (ANOMALY = `{warning,
   critical}`) is applied in exactly ONE place: `alerting.main()`, over
   `evaluate_alerts()` output. `sanctioned_pause_alert` is produced ONLY inside
   `loop_controller.tick()` and printed **unconditionally** by `_print_tick`
   (verified: the alert line emits with no quiet gate) — it never flows through
   `alerting.main()`/`filter_quiet` at all (grep confirms no such routing). So
   the surface an operator actually watches for the heartbeat — the `--tick`
   stdout / returned dict, which IS the heartbeat's reporting surface — shows
   the sanctioned pause on every rail trip, quiet-mode-independent. The `info`
   severity is doing the right and necessary job on the *other* surface (the
   alerting cockpit): it keeps a healthy, expected ceiling-hit OUT of the
   anomaly set so it can never be conflated with a real breach nor trip
   `--fail-on-critical` (CI). A sanctioned pause SHOULD NOT page. The tension
   was genuinely resolved, not moved: the two surfaces are distinct and the
   tick surface has no quiet filter. Not a bounce.

2. **"Audible" vs. "returned in a dict" — ACCEPT for this ticket, with a
   routed follow-up for the persistence sink.** The literal AC ("emits an
   alert through the EXISTING alerting path — no second notifier") is
   mechanically satisfied: same module, same `{severity,metric,message}` shape,
   no second notifier or print path. The genuine residual the builder honestly
   flagged — the alert currently lives only in `tick()`'s return + stdout,
   nothing persists it to `board/.events.jsonl` or a monitored channel — is
   real but is NOT a defect in this ticket, and I own this call as the SRE Lead
   over this surface: (a) persistence must NOT be bolted into `tick()`, which
   is a pure non-mutating evaluator (SI-2 "never mutates anything") — a jsonl
   write inside `tick()` would breach that invariant; (b) the entire
   `alerting.py` surface is by design trigger-gated and not yet wired to a live
   sink, so this alert is at exact parity with the rest of the machinery —
   produced in canonical shape, ready to be consumed once a live channel
   exists; (c) the heartbeat is OFF (shadow) — there is no live scheduler
   consuming ticks yet, so the consumption sink is downstream go-live work. The
   sink belongs in a separate consumer OUTSIDE `tick()`. Routed as a follow-up
   (see below), not a bounce.

**ADR-0042 SI-5 residual — status.** With this landed, the SI-5 alert-limb
residual recorded in ADR-0042's Reconciliation table (row 3: "loop_controller
contains no `alerting` call … Recorded as an open residual, not ratified as
complete") is **closed IN CODE**: both halves the addendum names — `idle`
(pre-existing) and `alert` (this ticket, through the existing `alerting.py`
machinery, severity-distinct from a real breach) — now exist and are
verified. Two items remain, both explicitly OUTSIDE this ticket's zone
(`scripts`), routed not decided:
  - **(CTO) ADR-0042 text note.** The Reconciliation row 3 and the
    Consequences "unwired alert limb (routed)" line should be updated to record
    the limb as now wired. A `docs/adr` edit is the CTO's (ADR ratifier, RACI
    3.1 A) — escalated to CTO, not edited by me.
  - **(follow-up ticket) persistence/consumption sink.** New work: route the
    `sanctioned_pause` alert into a channel monitored when nobody is watching
    tick stdout (e.g. append to `board/.events.jsonl` from a consumer, or a
    real notification channel), implemented OUTSIDE `tick()` to preserve SI-2's
    no-mutation invariant. Recorded here + in my report for the orchestrator to
    route (I cannot create the ticket file myself).

VERDICT: **DONE.** All acceptance criteria hold (re-verified above). The
SI-5/FR-004 alert limb is closed in code; the ADR-text ratification and the
persistence sink are routed as new work, not blockers on this ticket.
(Merged-PR/green-CI outstanding by orchestrator directive — not a bounce
ground.)
