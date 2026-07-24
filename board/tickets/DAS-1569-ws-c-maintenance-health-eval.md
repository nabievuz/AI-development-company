---
id: DAS-1569
title: WS-C Maintenance — scheduled health and eval of the loop and sandbox edge
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [SC-005]
labels: [governance]
zone: docs/06-maintenance
depends_on: [DAS-1568]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-C).** Schedule recurring health / eval
of the durable loop + per-task sandbox so drift is caught. COO accountable; Support Lead
consulted.

- A recurring **checkpoint-reconcile drift** check (graph state stays a faithful mirror of
  `board/tickets/`; no forked durable truth vs the ADR-0023 run-model / ADR-0031/0032
  ledger) and a **sandbox isolation probe** (a worker node still cannot reach the host /
  repo / another task / an unscoped credential).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [x] A scheduled health/eval check exists for checkpoint-reconcile drift + sandbox isolation and runs on the maintenance cadence. — `scripts/ws_c_loop_health_check.py`, registered as `ws-c-loop-health` (daily) in `scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]`.
- [x] A drift or isolation-probe failure surfaces as an alert / follow-up ticket (not silently). — documented in `docs/06-maintenance/ws-c-loop-health.md` §Alerting; non-zero exit → follow-up `board/tickets/` ticket per `governance/policies/raci.md`, never auto-remediated.
- [x] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously. — `docs/06-maintenance/ws-c-loop-health.md` §Founder-reviewed learnings (ADR-0029 G5); the check never writes to any role's `## Learned` section itself.
- [x] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI. — validators green (below); **LOCAL-ONLY this run** per dispatch constraint (no push/PR/commit) — merged-PR/green-CI carried by whoever lands the LOCAL-ONLY WS-C branch, same disposition as DAS-1568.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Maintenance, GATE-6). Checkpoint-reconcile drift + sandbox
isolation health checks on the eval cadence; learnings routed to daslab-learn.

### 2026-07-24 — Product Analyst
Delivered `scripts/ws_c_loop_health_check.py` (AADL Stage-6 / GATE-6, final WS-C ticket).
Three READ-ONLY checks, each reusing the real modules' own logic verbatim (no parallel
reconciliation/wall/ban logic written):

1. **Board-canonical drift** — builds a real `dgox.state.GraphState`, projects it via
   `scripts/dgox/langgraph_loop.py:project`, injects a divergence into the projected
   channels (simulating a stale/forked checkpoint), calls the real
   `langgraph_loop.reconcile` unmodified, and asserts the board value still wins: the
   divergence is detected, `board_state` still carries the ORIGINAL board value (never
   the projected/checkpoint value), and the event still carries
   `rule: board_wins_reconciliation`. A checkpoint-wins regression is a finding.
2. **Sandbox-wall drift** — drives the real `tools/sandbox/local_stub.py:LocalStubSandbox`
   through live probes of all four fail-closed walls (host escape via `..`/absolute
   path/embedded NUL byte; cross-task via an unregistered handle; unscoped credential via
   a mis-scoped `ScopedSecret`; non-allow-listed egress via an unlisted host) — each must
   still deny.
3. **Import-ban carve-out drift** — reuses `scripts/check_import_ban.py`'s own
   `SANCTIONED_IMPORT_PATHS`, `_is_sanctioned_import`, `BANNED`, and `check()` to assert
   the ADR-0035 carve-out is still exactly `langgraph` under `scripts/dgox/` only (denied
   elsewhere, including core `requirements*.txt`), the other 4 donor libs have no
   carve-out anywhere, and a live repo scan is clean.

Registered as `ws-c-loop-health` (daily, `python3 scripts/ws_c_loop_health_check.py
--json`) in `scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]`, alongside
`health-tick`/`golden-eval`/`memory-hygiene`/`ws-a-tool-edge-health`/`ws-b-runner-health`/
`ws-d-lens-health` — no new scheduling mechanism. Documented
`docs/06-maintenance/ws-c-loop-health.md`: what's checked, cadence, the alert →
follow-up-ticket path (never auto-remediated), and the `daslab-learn` (ADR-0029 G5)
Founder-reviewed hook — this check does not itself write to any `## Learned` section.

Added `tests/test_ws_c_loop_health_check.py` (17 tests): healthy-repo end-to-end, each
check's happy path, and an injected-regression test per finding class (checkpoint wins,
undetected divergence, missing reconciliation event; each of the 4 wall leaks; widened
carve-out path, another lib gaining a carve-out, shrunk BANNED set, live import-ban
violation) plus a CLI-exit-code test and a `maintenance_schedule()` registration test.

Verified — STAGED state (`git add -A` first): `python3 scripts/diagnostics.py` →
**100/100**; `python3 scripts/board_lint.py` → **exit 0** (180 tickets, 0 violations, 1
pre-existing unrelated WARN on DAS-1507); `python3 scripts/check_import_ban.py` → **exit
0**; `python3 -m pytest tests/test_ws_c_loop_health_check.py -q` → **17 passed**; the
broader `-k "stage_gate or ws_c or ws_b or ws_a or ws_d"` sweep → **292 passed, 4
skipped**; `ruff check scripts/ws_c_loop_health_check.py tests/test_ws_c_loop_health_check.py
scripts/stage_gate.py` → clean. No `/Users`/`/home` literals in any new file.

Touched only: `scripts/ws_c_loop_health_check.py` (new), `scripts/stage_gate.py`
(registration only — the `maintenance_schedule()` list, no other edit),
`docs/06-maintenance/ws-c-loop-health.md` (new), `tests/test_ws_c_loop_health_check.py`
(new), this ticket file. Did NOT modify `scripts/dgox/`, `tools/sandbox/`,
`scripts/check_import_ban.py`, config, or any ADR — read/reused only.

**LOCAL-ONLY** per dispatch constraint — no git commit/push/PR this run; the branch/PR
step is left to whoever carries this to `done` per the git rules (one issue = one
branch = one PR, never commit to main). This is the final WS-C ticket
(DAS-1561 epic) — routing to **coo** (GATE-6 accountable per RACI) for GATE-6 closure
review; never self-review.

### 2026-07-24 — COO
**GATE-6 (Maintenance) CLOSED for WS-C LOOP.** Independently re-ran all four verifications
(not trusting the Product Analyst's log alone):
- `python3 -m pytest tests/test_ws_c_loop_health_check.py -q` → **17 passed**.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0** (180 tickets, 0 violations, 1 pre-existing
  unrelated WARN on DAS-1507 — not introduced by this ticket).
- `python3 scripts/check_import_ban.py` → **exit 0**.
- Confirmed `"name": "ws-c-loop-health"` registered in
  `scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]` (line 484), config
  pointing at `docs/06-maintenance/ws-c-loop-health.md` (line 488).
- Confirmed `docs/06-maintenance/ws-c-loop-health.md` has `## Alerting — a failure is
  never silent` (line 83) and `## Founder-reviewed learnings → daslab-learn (ADR-0029
  G5)` (line 109), matching the acceptance criteria on drift-alerting and
  Founder-reviewed learning routing.

All four acceptance criteria are satisfied and independently confirmed. Decision:
**Accept on LOCAL-ONLY disposition**, consistent with GATE-1..5 for WS-A/B/C/D — the
branch/PR/merge step is deferred to whoever lands the LOCAL-ONLY WS-C branch, same as
every prior WS-C gate. No genuine gap found; no escalation needed.

Setting `status: done`. This closes **GATE-6 — Maintenance**, the sixth and final AADL
gate for WS-C LOOP. All six AADL gates (Planning → Design → Development → Testing →
Deployment → Maintenance) for WS-C LOOP are now closed. Epic **DAS-1561** is ready for
the orchestrator to mark done.

Did not touch any file besides this ticket. No push/PR/commit performed (LOCAL-ONLY).
</content>
