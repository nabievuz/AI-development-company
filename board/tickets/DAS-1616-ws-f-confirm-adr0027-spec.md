---
id: DAS-1616
title: WS-F Planning — confirm ADR-0027 SI-1..SI-7 coverage and review SPEC-010
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1615
goal: mustaqil-ws-f-tempo
spec: 010-mustaqil-ws-f-tempo
implements: [FR-001]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-F).**

- Confirm **ADR-0027** is `Accepted` (it already is — ratified 2026-07-03, CTO
  decider) and remains the sole binding contract for the tempo substrate; no
  amendment needed unless this review finds a real gap.
- Review `docs/specs/010-mustaqil-ws-f-tempo/SPEC.md` (FR-001…FR-006,
  SC-001…SC-004); resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status `reviewed`.
- Inventory the already-shipped WS4 machinery this workstream verifies rather than
  rebuilds: `scripts/loop_controller.py`, `scripts/break_glass.py`,
  `scripts/check_loop_mode.py`, `scripts/check_heartbeat_readiness.py`,
  `docs/runbooks/heartbeat-go-live.md`, and the WS4 tickets that built them
  (DAS-1472, DAS-1473, DAS-1474, DAS-1475, DAS-1476, DAS-1477, DAS-1478, DAS-1538 —
  all `done`). Confirm `config/features.yaml` `heartbeat_enabled: false` and the
  never-flipped `ws_f_heartbeat` placeholder are both still OFF and unambiguous
  about which key is live (SI-7).
- No tool or scheduler is built in this stage — this fixes the contract WS-F's
  Design/Development/Testing children verify against.

## Acceptance criteria
- [x] ADR-0027 confirmed `Accepted`, SI-1..SI-7 unchanged as the binding contract;
      `docs/adr/README.md` row consistent (no edit needed unless a real gap surfaces).
- [x] SPEC-010 reviewed (Status `reviewed`), no unresolved clarification markers.
- [x] Inventory of already-shipped WS4 enforcement points recorded in the log, each
      confirmed present and its owning ticket confirmed `done`.
- [x] `heartbeat_enabled: false` and `ws_f_heartbeat` placeholder confirmed OFF and
      unambiguous (one live key, one inert alias) — no flip performed.
- [x] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-F Planning). Confirms ADR-0027 coverage; reviews SPEC-010;
inventories the already-`done` WS4 machinery this workstream verifies, not rebuilds.

### 2026-07-24 — CTO
**GATE-1 (Planning) CLOSED for WS-F TEMPO.** Governance/verification pass only — no
scheduler, runbook, readiness reporter, or kill-switch was authored or duplicated; no
flag was flipped; `docs/adr/` was **not** edited (no gap surfaced that requires an
ADR-0027 amendment at Planning — see "ADR-scope observation" below).

**1. ADR-0027 status.** `docs/adr/0027-scheduler-safety.md` line 3 reads
`**Status:** Accepted (**CTO — decider; RACI 3.1 A (ADR ratifier); AADL GATE-1 Planning
artifact — 2026-07-03**)`. The `docs/adr/README.md` row 36 is consistent (Accepted /
2026-07-03) and already enumerates SI-1…SI-7. **Confirmed sole binding contract for the
tempo substrate; unchanged, unamended.** SI-1…SI-7 headings verbatim:

- **SI-1** — Operator-invoked, NOT a daemon
- **SI-2** — `loop.yaml` stays `shadow` + `auto_apply: false` (check_loop_mode stays exit 0)
- **SI-3** — Break-glass kill-switch is honored
- **SI-4** — Quiet hours
- **SI-5** — Per-run and per-day budget caps (cost-ledger enforced)
- **SI-6** — Max-concurrent-waves cap
- **SI-7** — Never-auto-approve; live only on an explicit Founder flag-flip after a ≥ 3-day clean shadow window

**2. SI → enforcement-artifact coverage map (the load-bearing handoff to DAS-1617).**
Each row: invariant → the named artifact(s) present in the repo today → verdict.

| SI | Enforcement artifact(s) present today | Verdict |
|---|---|---|
| SI-1 | `tests/test_no_daemon.py` (AST scan for `while True` / `threading.Timer|Thread` / `sched` / asyncio `run_forever` / `time.sleep` in a loop, over the declared `SCHEDULER_FILES` set); one-shot `--tick` in `scripts/loop_controller.py`; `board/schedule.yaml` OS-scheduler entry is **documented only** (`installed: false`, nothing in-repo installs launchd/cron) | **PRESENT** — 43 tests pass |
| SI-2 | `config/loop.yaml` (`mode: shadow`, `auto_apply: false`); `scripts/check_loop_mode.py` (observed **exit 0**); `scripts/kill_switch_drill.py` rail `SI-2 check_loop_mode` (+ asserts the drill never edits `loop.yaml`); `tests/test_scheduler.py::TestCheckLoopModeStaysGreen`; `tests/test_check_loop_mode.py`; `tests/test_loop_controller.py::test_cli_does_not_mutate_loop_config` | **PRESENT** |
| SI-3 | `scripts/break_glass.py` `is_active()`; `scripts/loop_controller.py` SI-3 branch (`_tick` line ~332); `scripts/flow_router.py` `break_glass_active` dispatch gate; `scripts/kill_switch_drill.py` rail `SI-3 break_glass_kill_switch` (engage → IDLE, 60-min auto-expiry restores dispatch); `tests/test_break_glass.py`, `tests/test_scheduler.py::TestTickSafetyRails`, `tests/test_flow_router.py` | **PRESENT** |
| SI-4 | `board/schedule.yaml` `quiet_hours: {start: "22:00", end: "06:00", timezone: UTC}`; `scripts/loop_controller.py::_in_quiet_hours`; `scripts/flow_router.py` `in_quiet_hours` gate; `scripts/kill_switch_drill.py` rail `SI-4 quiet_hours`; `tests/test_scheduler.py::TestInQuietHours` (+ "quiet hours block dispatch, never validate") | **PRESENT** |
| SI-5 | `config/budgets.yaml` `caps.per_run` / `caps.per_day` **and** the stricter `mustaqil.caps.per_run|per_day` + `on_breach: idle_and_alert`; `scripts/loop_controller.py::_per_day_budget_exceeded`; `scripts/cost/cost_ledger.py`, `scripts/check_cost.py`, `scripts/alerting.py`; `scripts/kill_switch_drill.py` rail `SI-5 budget_caps` (per-day breach → IDLE, per-run ceiling present in the real SSOT); `tests/test_scheduler.py::TestPerDayBudget` | **PRESENT** for per-run/per-day. **GAP G1** on the monthly-credit outer cap — see §4 |
| SI-6 | `board/schedule.yaml` `max_concurrent_waves: 1`; `scripts/flow_router.py` in-flight detection (`run_start` with no `run_end` → dispatch degrades to IDLE citing SI-6); `scripts/loop_controller.py` line 57 SI-6 default; `scripts/kill_switch_drill.py` rail `SI-6 max_concurrent_waves`; `tests/test_flow_router.py`, `tests/test_scheduler.py` | **PRESENT** |
| SI-7 | `config/features.yaml` `heartbeat_enabled: false` + `scripts/feature_flags.py` `DEFAULTS` (asserted False by `tests/test_scheduler.py::TestHeartbeatFlag`, `tests/test_feature_flags.py`); `board/schedule.yaml` `never_auto_approve: true`; `scripts/flow_router.py` closed decision alphabet `{dispatch, validate, idle}` (structural — no `approve`/`answer` action exists); `scripts/kill_switch_drill.py` rail `SI-7 never_auto_approve` (auto-approval event scanner, zero-violations proof, scanner-has-teeth negative test); `scripts/check_never_auto_approve.py`; `scripts/check_heartbeat_readiness.py` (the ≥3-day bar); `docs/runbooks/heartbeat-go-live.md` (Founder-only flip procedure) | **PRESENT**; runbook **partial** on the two-clock wording — see **GAP G2** |

Evidence run (all local, read-only):
`python3 -m pytest tests/test_scheduler.py tests/test_no_daemon.py tests/test_flow_router.py
tests/test_kill_switch_drill.py tests/test_check_heartbeat_readiness.py
tests/test_check_loop_mode.py tests/test_break_glass.py tests/test_loop_controller.py -q`
→ **195 passed in 0.37s**.
`python3 scripts/kill_switch_drill.py --smoke` → `pass[000] ok: SI-3=ok SI-4=ok SI-5=ok
SI-6=ok SI-7=ok SI-2=ok` … `OK — every safety rail held on every pass (zero
gate/approval violations, loop off)` (exit 0).
`python3 scripts/check_loop_mode.py` → `OK: loop off — mode 'shadow', auto_apply false
(levers only, no controller).` (exit 0).

**3. WS4 provenance — every owning ticket confirmed `done`:** DAS-1472, DAS-1473,
DAS-1474, DAS-1475, DAS-1476, DAS-1477, DAS-1478, DAS-1538 (all `status: done`), plus the
`depends_on` DAS-1543 (`done`). Files confirmed present on disk: `scripts/loop_controller.py`,
`scripts/break_glass.py`, `scripts/check_loop_mode.py`, `scripts/check_heartbeat_readiness.py`,
`scripts/flow_router.py`, `scripts/kill_switch_drill.py`, `scripts/metrics_history_feeder.py`,
`board/schedule.yaml`, `config/loop.yaml`, `config/budgets.yaml`,
`docs/runbooks/heartbeat-go-live.md`. **WS-F verifies these; it rebuilds none of them.**

**4. Gaps recorded — DESIGN INPUT for DAS-1617, DEVELOPMENT INPUT for DAS-1618. Not fixed here.**

- **G1 (real, SI-5 / FR-004) — the monthly credit ceiling is not wired into the WS-F tick
  path.** `config/budgets.yaml` DOES carry the outer cap (see §5 below), and it IS enforced
  on the WS-B admission path (`scripts/ws_b_admission.py` reads
  `mustaqil.monthly_credit_ceiling.plan_credit_usd`; `scripts/ws_b_health_check.py` guards
  `on_exhaustion`/`metered_overflow` drift; `tests/test_ws_b_health_check.py`,
  `tests/test_ws_b_negative_paths.py`). But `scripts/loop_controller.py`,
  `scripts/flow_router.py` and `scripts/check_heartbeat_readiness.py` contain **zero**
  references to `monthly_credit_ceiling` — grep returns nothing. So the heartbeat's SI-5
  ceiling today is per-run + per-day only; FR-004's "additional hard dispatch ceiling the
  heartbeat honors" has **no enforcement point in the `--tick` path**. DAS-1617 designs the
  wiring (reuse `ws_b_admission`, do **not** author a second credit accountant); DAS-1618
  implements; `on_exhaustion: sanctioned_pause` must stay an idle+alert, never a failure or
  a false-green.
- **G2 (real, SC-004 / FR-003) — runbook wording on the two clocks.**
  `docs/runbooks/heartbeat-go-live.md` §4 (lines 63–65) correctly says the self-optimizing
  LADDER is "a **separate** gate (ADR-0027 SI-2)", but it never states the loop-promotion
  clock's **≥ 7 clean live day** figure alongside the **≥ 3-day** heartbeat clock, and §7
  (line 77) introduces a third, unlabeled "Once ≥7 rolling waves show T1 ≥ 0.60 / T2 ≤ 0.15"
  release criterion sitting adjacent to that same number — exactly the conflation SI-7
  ("two distinct clocks, do not conflate") forbids. The runbook also carries **no
  monthly-credit-ceiling addendum** (FR-003). Fix belongs in the existing runbook — **fold
  in, do not fork a second runbook**. NOT touched in this ticket: `docs/runbooks/` is outside
  this ticket's `zone: docs/adr` and was concurrently held by another workstream this wave.
- **G3 (by design, not a defect) — SI-1's external half has no repo-side artifact and cannot
  have one.** `tests/test_no_daemon.py` proves the *in-repo* scheduler files hold no daemon
  pattern; the cadence itself lives in a Founder-owned launchd/cron entry that this repo
  documents (`board/schedule.yaml`, `installed: false`) and deliberately never installs.
  Record as covered-by-construction; DAS-1617 should not invent an enforcement point for it.

**ADR-scope observation (CTO call — no amendment at GATE-1).** ADR-0027 SI-5's text names
only `caps.per_run` / `caps.per_day`; the monthly Claude-subscription credit ceiling is a
later MUSTAQIL-era outer cap introduced by DAS-1543, which SPEC-010 FR-004 asserts as an
additional heartbeat ceiling. That is an **extension, not a contradiction** — ADR-0027
stays `Accepted` and unedited. If DAS-1617/1618 wire the ceiling into the `--tick` path,
the clean record is an ADR-0027 addendum (or a small amending ADR) at that point, ratified
by the CTO. Flagging as design input, not blocking GATE-1.

**5. Monthly credit ceiling — present in `config/budgets.yaml` as an outer cap alongside
SI-5 (verbatim keys/values found):**
`mustaqil.caps.per_run` = `max_input_tokens: 2_000_000`, `max_output_tokens: 400_000`,
`max_cost_usd: 5.00`; `mustaqil.caps.per_day` = `max_input_tokens: 20_000_000`,
`max_output_tokens: 4_000_000`, `max_cost_usd: 15.00`; `mustaqil.on_breach: idle_and_alert`;
`mustaqil.monthly_credit_ceiling.plan_credit_usd` = `pro: 20`, `max_5x: 100`, `max_20x: 200`;
`mustaqil.monthly_credit_ceiling.on_exhaustion: sanctioned_pause`;
`mustaqil.monthly_credit_ceiling.metered_overflow: false`. The org-wide informational
`caps.per_run` (`max_cost_usd: 50.00`) / `caps.per_day` (`max_cost_usd: 500.00`) are also
present and are the looser shared gate — the `mustaqil.*` block is the stricter self-imposed
autonomy budget SI-5 calls for. The file also carries an open
`[NEEDS VERIFICATION at WS-B go-live]` note on the live plan's Agent-SDK credit terms —
carried forward, not resolvable at this stage. **Data present; enforcement in the tick path
is gap G1.**

**6. SPEC-010 review.** `docs/specs/010-mustaqil-ws-f-tempo/SPEC.md` Status is already
`reviewed`; no `[NEEDS CLARIFICATION]` marker exists anywhere in the SPEC directory or the
DAS-161x/162x tickets (the only string match is this ticket's own instruction prose).
FR-001…FR-006 and SC-001…SC-004 were read against ADR-0027 — **no contradiction found**.
FR-001 (verify-not-rebuild), FR-002 (fresh readiness run), FR-003 (fold into the existing
runbook), FR-005 (per-SI evidence), FR-006 (Founder-only flip, Deployment child stays
`blocked`) all restate or narrow SI-1…SI-7. FR-004 is the one **extension** beyond the
ADR text, handled above. `python3 scripts/check_spec_consistency.py` →
`OK: 10 SPEC.md file(s) checked, structure + ticket refs consistent.` (exit 0).

**7. Flags — confirmed OFF, unambiguous, NOT flipped.** `config/features.yaml`:
`heartbeat_enabled: false` (line 12, annotated as the live key consumed by
`loop_controller.py --tick`, Founder-only flip per SI-7) and `ws_f_heartbeat: false`
(line 28, annotated "PLACEHOLDER ONLY … this key is never the flip point"). One live key,
one inert alias — unambiguous. `config/loop.yaml` remains `mode: shadow` /
`auto_apply: false`. **No flag was flipped in this ticket. DAS-1622 stays `blocked` by
design (FR-006); untouched.**

**8. GATE-1 readiness baseline — `python3 scripts/check_heartbeat_readiness.py` (exit 1),
verbatim:**

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

**NOT READY at 0/3 clean days from 0 history rows is the honest, expected state** and is
recorded as-is. It does **not** block GATE-1 (Planning fixes the contract); it is precisely
the condition SPEC-010 P2/FR-006 anticipates, and it is why DAS-1622 (Deployment) is
`blocked` by design. Nothing here was massaged, and no readiness claim is made.

**9. Gates re-run (observed output, not claimed):**
- `python3 scripts/diagnostics.py` → **SCORE = 100/100** (Governance, Portability 15/15,
  Security 10/10, Git-hygiene 5/5 all PASS; incl. `ok spec-consistency`, `ok dependency-graph`).
- `python3 scripts/board_lint.py` → `OK — 180 ticket(s) checked, 0 violations.` (exit 0;
  one pre-existing non-fatal body-status WARN on DAS-1507, unrelated to WS-F).
- `python3 scripts/check_dependency_graph.py` → `OK: dependency graph acyclic, no dangling
  deps (118 ticket(s) declare depends_on).` (exit 0).
- `python3 scripts/check_spec_consistency.py` → `OK: 10 SPEC.md file(s) checked …` (exit 0).
- `python3 scripts/check_links.py` → `OK — no broken relative links in tracked Markdown.` (exit 0).
- **board_lint R9:** this ticket declares **no `project:` field** (grep `^project:` → no match).

**Decision.** GATE-1 CLOSED for WS-F TEMPO. ADR-0027 remains the sole binding, `Accepted`
contract; SI-1…SI-6 have named, currently-green enforcement points; SI-7 is enforced
structurally with the runbook wording gap G2 outstanding; G1 is the one substantive coverage
gap. Both G1 and G2 are handed to **DAS-1617 (Design, sre-lead)** as design input and
**DAS-1618 (Development)** as build input — neither is fixed, asserted away, or worked around
here. `status: done`; this unblocks exactly DAS-1617.
