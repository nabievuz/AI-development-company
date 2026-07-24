---
id: DAS-1551
title: WS-A Maintenance — scheduled health and eval of the tool edge
status: done
assignee: coo
author: ceo
dept: engineering
priority: p2
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [SC-004]
labels: [security]
zone: docs/06-maintenance
depends_on: [DAS-1550]
created: 2026-07-23
updated: 2026-07-24
---

## Description

**AADL Stage 6 — Maintenance (closes GATE-6 for WS-A).** Schedule recurring health /
eval of the governed tool edge so drift is caught. COO accountable; Support Lead
consulted.

- A recurring check for **allow-list drift** (a role or tool granted outside the
  documented allow-list) and a **redaction probe** (tool events still redacted).
- Wire it into the existing maintenance/eval cadence (the golden-eval / scheduled-run
  path), not a new daemon.
- Feed Founder-accepted learnings into the `daslab-learn` cadence (ADR-0029 G5) — a
  governed, Founder-reviewed compounding, not autonomous self-modification.

## Acceptance criteria
- [x] A scheduled health/eval check exists for allow-list drift + redaction and runs on the maintenance cadence.
- [x] A drift or redaction-probe failure surfaces as an alert / follow-up ticket (not silently).
- [x] Learnings routed to `daslab-learn` (Founder-reviewed), not applied autonomously.
- [x] Stage-board updated with GATE-6 closure. `board_lint`/validators green; merged PR, green CI. — validators green (below); **no merged PR** — accepted LOCAL-ONLY, consistent with DAS-1547/1548/1549/1550 disposition (COO's GATE-6-owner call, see closure log entry below).

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Maintenance, GATE-6). Allow-list drift + redaction health checks on the eval cadence.

### 2026-07-24 — Product Analyst
**AADL Stage 6 — Maintenance.** Added a scheduled health/eval check for the
governed tool edge and wired it into the **existing** Maintenance cadence —
no new daemon/process:

- **New script:** `scripts/ws_a_health_check.py` — two read-only checks:
  1. **Allow-list drift** — recompiles `board/.tool-allowlist.json` in-memory
     via `scripts/gen_subagents.compile_tool_allowlist()` (the same SSOT
     compiler CI's generate-and-diff already uses per DAS-1547 C1) and diffs
     against the tracked file. This targets the Maintenance cadence's own
     schedule, independent of a push happening, catching drift from any other
     source (hand-edit, stale checkout, out-of-band grant).
  2. **Redaction probe** — runs 6 known secret-shaped strings (JWT, Bearer
     token, DSN-with-credentials, Anthropic key, AWS key id, PEM private-key
     block) through `tools/mcp_bridges/redaction.py: safe_scrub` (ADR-0012 §2)
     and asserts each is redacted, plus a Tier-M control (a plain git-SHA
     string) that must NOT be over-redacted (ADR-0012 tuning note).
  Exit code 0 = healthy, 1 = a finding (drift and/or redaction miss).
- **Registered** as a new `ws-a-tool-edge-health` entry in
  `scripts/stage_gate.py:maintenance_schedule()["recurring_runs"]`, alongside
  the existing `health-tick` (WS4 heartbeat) and `golden-eval` (WS6) entries —
  same registration point, cadence `daily`, `command: ["python3",
  "scripts/ws_a_health_check.py", "--json"]`. Still DATA, not an installer
  (ADR-0027 SI-1) — nothing here schedules itself; the OS scheduler entry
  stays Founder-owned.
- **Maintenance doc:** `docs/06-maintenance/ws-a-tool-edge-health.md` —
  what's checked, cadence/registration, and the **alerting path**: a non-zero
  exit is never swallowed — it is attached as evidence to a follow-up
  `board/tickets/` ticket (`labels: [security]`, `dept: engineering`, RACI
  routing per DAS-1547/1549 precedent), never auto-remediated (allow-list and
  redaction-pattern fixes are `security_sensitive`/`governance_or_policy` —
  `check_never_auto_approve.py` rejects `approval: auto*` on either).
- **`daslab-learn` hook (ADR-0029 G5):** documented in the same maintenance
  doc — a *repeated/systemic* finding is a lesson candidate; it flows through
  the normal `daslab-learn` distillation of **Founder-accepted** feedback into
  a role's `## Learned` section (likely `security-lead` for allow-list/egress
  patterns, `sre-lead` for redaction patterns). This script does not write to
  any `## Learned` section itself and performs no self-modification — governed
  compounding only, per the ticket's explicit constraint.
- **Tests:** `tests/test_ws_a_health_check.py` (7 cases) — healthy-repo
  baseline, drift-detected (tampered/missing tracked file), redaction-miss
  detected, over-redaction-of-Tier-M-control detected, CLI exit code, and the
  `maintenance_schedule()` registration itself.

**Validators (exact, 2026-07-24):**
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0 — 180 ticket(s) checked, 0
  violations** (pre-existing DAS-1507 body-status WARN, unrelated/non-fatal).
- `python3 -m pytest tests/test_ws_a_health_check.py -q` → **7 passed**.
- `python3 -m pytest tests/test_ws_a_tool_bridge.py tests/test_ws_a_browser_tool_egress.py tests/test_ws_a_health_check.py -q` → **74 passed, 2 skipped** (unaffected by this change).
- `python3 -m pytest tests/test_stage_gate.py -q` → **24 passed** (maintenance-schedule change doesn't break existing gate-walk tests).
- `ruff check scripts/ws_a_health_check.py tests/test_ws_a_health_check.py scripts/stage_gate.py` → **All checks passed!**

**Files touched (only these, per the tight-footprint constraint):**
`scripts/ws_a_health_check.py` (new), `scripts/stage_gate.py` (added one
`recurring_runs` entry — no other edit), `docs/06-maintenance/ws-a-tool-edge-health.md`
(new), `tests/test_ws_a_health_check.py` (new), this ticket. No WS-A
implementation file, ADR, or other ticket was modified.

**LOCAL-ONLY note (AC #4):** per this run's explicit constraint, **no
git push/PR/commit/remote** — consistent with the accepted LOCAL-ONLY
disposition of every prior WS-A ticket (DAS-1547/1548/1549/1550). All content
is on-disk on the current checkout only. Whether GATE-6 closes on local green
evidence (as GATE-5 did) or requires a merged PR is the **COO's call** (GATE-6
accountable per the AI-agent-lifecycle policy) — flagging it rather than
deciding it, per my charter.

Setting `status: in_review`, `assignee: coo` (GATE-6 accountable; Support
Lead consulted per the policy's RACI row). This is the last WS-A REACH
ticket (DAS-1544 epic) — GATE-6 closure by the COO would close out the
program.

### 2026-07-24 — COO — GATE-6 CLOSED

Independently re-verified (exact, this run):
- `python3 -m pytest tests/test_ws_a_health_check.py -q` → **7 passed**.
- `python3 scripts/diagnostics.py` → **SCORE = 100/100**.
- `python3 scripts/board_lint.py` → **exit 0 — OK: 180 ticket(s) checked, 0
  violations** (pre-existing DAS-1507 body-status WARN only, unrelated).
- `grep -n "ws-a-tool-edge-health" scripts/stage_gate.py` → confirmed
  registered in `maintenance_schedule()["recurring_runs"]`
  (`config: docs/06-maintenance/ws-a-tool-edge-health.md`).
- `docs/06-maintenance/ws-a-tool-edge-health.md` §Alerting confirmed: a
  drift/redaction-miss is never swallowed — it is filed as a follow-up
  `board/tickets/` ticket (never auto-remediated, per
  `check_never_auto_approve.py`), and repeated/systemic findings route to
  `daslab-learn` as Founder-reviewed lessons (ADR-0029 §G5), not autonomous
  self-modification.

**Decision:** GATE-6 (Maintenance) is **ACCEPTED and CLOSED** on the
LOCAL-ONLY disposition, consistent with GATE-1 through GATE-5 for this
epic (DAS-1547/1548/1549/1550). Rationale: all functional AC are met and
independently verified (scheduled check exists + tested, wired into the
existing cadence with no new daemon, failure path is a non-silent alert/
follow-up ticket, learnings routed through governed `daslab-learn` review
only); the sole open item is the AC #4 "merged PR + green CI" clause, which
is a repo-hygiene formality this program has treated as satisfiable by
verified local-green evidence at every prior gate, not a maintenance-
readiness gap. No genuine gap found that would warrant holding this back
in review.

Setting `status: done`. **This closes the sixth and final AADL gate for
WS-A REACH (DAS-1544 epic) — all six gates (Planning, Design, Development,
Testing, Deployment, Maintenance) are now closed.** DAS-1544 is ready for
the orchestrator/CEO to mark done.
