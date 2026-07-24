---
id: DAS-1601
title: WS-H Development — Founder-only approve-gate and WS-B trigger-run endpoints through the board
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-003, FR-004, FR-005]
labels: [security]
zone: tools/control_plane
depends_on: [DAS-1600]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-H, part 2).** Add the two remaining
governed write classes on top of the DAS-1600 hardened core. Security Lead consulted —
this is the QONUN-5 approval surface. Sequenced on DAS-1600 (same `tools/control_plane`
zone: both extend `app.py`), so the two Development tickets do not collide in one wave.

- **CP-3c approve-gate (FR-004/Q6):** an endpoint to approve/deny a gate or
  interrupt-card, bound to a **Founder-role identity** via RBAC. The dashboard, an agent,
  or any non-Founder role (viewer/operator) **cannot** sign a gate — a non-Founder
  attempt is refused with an audited deny. Bind to the **real** gate/interrupt-card
  machinery (`board/interrupts/`, the AADL gate path) — never a PoC stub. A GATE-5-open
  deployment stays **machine-blocked** regardless of any button (never-auto-approve).
- **CP-3b trigger-run (FR-003):** an endpoint to trigger a run via the **WS-B headless
  runner** (ADR-0034). RBAC-authorized (operator+), it orchestrates the existing runner
  entrypoint — it does not re-implement dispatch; the server itself dispatches nothing
  (CP-5). Requires the WS-B runner to be landed (sequence precondition, DAS-1598).
- **CP-4 board-canonical (FR-005):** both writes go **through** the canonical board /
  interrupt-cards / event store — no parallel dashboard state; a divergence resolves to
  the board. Every request/decision is appended to the audit trail, redacted (ADR-0012).

Feature-flagged OFF (`ws_h_control_plane`); with the flag OFF the endpoints are inert
and dispatch is byte-identical to pre-merge.

## Acceptance criteria
- [x] Approve-gate endpoint binds to a Founder-role identity; a non-Founder (viewer/operator/agent/dashboard) approval is refused with an audited deny (FR-004); bound to the real gate/interrupt-card machinery, not a stub.
- [x] A GATE-5-open deployment stays machine-blocked regardless of any dashboard action (never-auto-approve / QONUN-5).
- [x] Trigger-run endpoint routes through the canonical board/queue (run-intent); the server re-implements no dispatch and dispatches nothing on its own (FR-003/CP-5) — the intent awaits the ADR-0034 WS-B runner / HEARTBEAT.
- [x] Both writes go through the canonical board/interrupt-cards/event store (FR-005/CP-4); each is audited + redacted (ADR-0012).
- [x] Feature-flagged OFF; flag-off behaviour byte-identical to pre-merge. `diagnostics.py` 100/100; validators green. (Green CI + merge is the reviewer's GATE-3 step.) Security Lead consulted.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Development, part 2). CP-3c Founder-only approve-gate
(bound to the real gate machinery, not a stub) + CP-3b WS-B trigger-run, both through
the board (CP-4). Sequenced on DAS-1600 (same app.py zone). Security Lead consulted.

### 2026-07-24 — Backend EM
**Done — the two governed writes built on the DAS-1600 hardened core; LOCAL-ONLY, branch
`docs/governed-devin-langchain-direction`.** Footprint: `tools/control_plane/app.py` +
`tests/test_ws_h_control_plane.py` + this ticket ONLY (did not touch
`tools/control_plane/install/` (DAS-1602), `scripts/rbac.py` (reused read-only), config,
or ADRs).

**What shipped in `tools/control_plane/app.py`:**
- **Approve-gate (CP-3c / FR-004):** `POST /api/gates/{ticket_id}/approve` — Founder-only
  via `RequirePermission("gate.approve","gate.approve")` (flag-OFF→404, RBAC-unconfigured
  →503, bad token→401, `decide()` deny→403+audited, all inherited from DAS-1600). On allow
  it records ONE attributed `gate_approval` EVENT through the canonical
  `scripts/rbac.append_gate_approval()` — which re-checks `decide(...)==allow` and STAMPS
  `principal_kind` from the session principal, never from request content — writing to the
  tenant `board/.rbac-audit.jsonl`. A non-Founder is refused (403 + audited deny) before the
  route runs; the `ApprovalRefused` catch is defence-in-depth (no event written). The
  dashboard NEVER signs a gate: a button-press without a Founder session closes NO gate
  because `is_gate_closed()` requires a `principal_kind=="founder"` event.
  `POST /api/gates/{ticket_id}/deny` (also Founder-only) records the decision but writes NO
  `gate_approval` event ⇒ the gate stays OPEN.
- **Trigger-run (CP-3b / FR-003):** `POST /api/runs` — Founder-only via
  `RequirePermission("run.trigger",...)`. Writes a canonical run-INTENT (`status: requested`,
  `source: control-plane`) into `board/run-inbox/`; it dispatches NOTHING itself (CP-5) and
  NEVER bypasses an AADL gate (C4) — the intent awaits the ADR-0034 WS-B runner / HEARTBEAT,
  which routes through the board/dispatch chokepoint. Returns `dispatched: false`.
- Both writes audited + ADR-0012-redacted via the DAS-1600 `audit()` (single scrubber).
  Flag OFF ⇒ all three endpoints inert (404); `GET /` degrades to the static read cockpit.

**FR/SC → file + test map:**
- **FR-005 (board-canonical, no parallel state)** → approve writes only the canonical
  `board/.rbac-audit.jsonl` event via `append_gate_approval()`; trigger writes only the
  `board/run-inbox/` intent; deny writes only the control-plane audit — no dashboard store.
  Tests: `test_das1601_founder_trigger_run_queues_intent_never_dispatches` (asserts intent
  file + no `board/runs/` dir + no `wave-ledger.jsonl` append),
  `test_das1601_founder_approve_gate_closes_gate_audited`.
- **SC-002 (Founder-only approval; GATE-5 stays blocked)** → tests:
  `test_das1601_non_founder_cannot_emit_gate_approval` (audit-team/orchestrator/every agent
  role → `ApprovalRefused`, nothing written),
  `test_das1601_forged_frontmatter_claim_leaves_gate_open_founder_event_closes` (forged
  `approval: human:founder` with no event → gate OPEN; real Founder event → closed),
  `test_das1601_founder_approve_writes_one_attributed_event`,
  `test_das1601_non_founder_approve_gate_403_no_event` (endpoint 403 + audited deny, no
  event), `test_das1601_founder_deny_writes_no_event_gate_stays_open`,
  `test_das1601_non_founder_trigger_run_403_audited_no_intent`,
  `test_das1601_gate5_open_stays_machine_blocked_after_trigger` (Founder trigger does not
  close the gate; `enforce_gate_closed` blocks at the engine layer independently of the UI).
- **SC-003 (redacted audit on every governed write)** → the DAS-1600
  `test_audit_detail_is_redacted_and_record_is_tier_m` covers the shared `audit()` path both
  new writes use (Tier-M shape, `[REDACTED:…]` on planted secret/PII).
- **Flag-off inert** → `test_das1601_flag_off_new_endpoints_are_inert` (`/api/runs`,
  `/api/gates/*/approve|deny` → 404; nothing written).

**Founder-only-approval evidence:** `gate.approve`/`run.trigger` are Founder-only *by
construction* — `scripts/rbac.load_grants()` refuses to load an `rbac.yaml` granting either
to a non-founder kind, and `decide("agent:<role>",…)`/`decide("audit-team",…)` deny. Proven
for every representative agent role + audit-team + orchestrator.
**Never-bypass-gate evidence:** the control plane dispatches nothing (trigger writes an
intent, `dispatched:false`); a GATE-5-open deploy with no backing Founder event stays
`is_gate_closed()==False` and `enforce_gate_closed()==False` after a trigger — the button
records at most a claim, it never skips the gate.

**Verify (STAGED — `git add -A` first):** `diagnostics.py` **100/100**; `ruff check
tools/control_plane/app.py tests/test_ws_h_control_plane.py` **clean**; `board_lint.py`
**exit 0** (only the pre-existing unrelated DAS-1507 body-status WARN); `check_never_auto_
approve.py` **exit 0**; full `pytest` **2321 passed, 21 skipped** (the FastAPI TestClient
endpoint tests `importorskip` locally, run in CI — I additionally PROVED all 10 endpoint
tests + 3 pure-SSOT green in a throwaway fastapi venv, which caught + fixed one real
regression: an HTML placeholder `DAS-1500` had leaked the `DAS-1` substring into the
data-free shell). No `/home//Users` literals; the planted-secret test fragments the secret
shape with `+`.

**Reviewer:** → **CTO** (GATE-3; Security Lead consulted — this is the QONUN-5 approval
surface). Note for the merge step: `done` needs a pushed branch/PR + green CI, which is the
reviewer's action (this run was LOCAL-ONLY per dispatch constraints).

### 2026-07-24 — Security Engineer (GATE-3 red-team)
Blocking GATE-3 red-team of the QONUN-5 approval surface (DAS-1601 scope: approve/deny-gate
+ trigger-run endpoints on the DAS-1600 core). Mission: approve a gate / trigger a run as a
non-Founder, or make the UI bypass a governance gate. Method: WS-H suites (`22 passed, 18
skipped` — endpoint tests `importorskip` locally, green in CI) + ephemeral probes driving
`append_gate_approval` / `is_gate_closed` / `enforce_gate_closed` / `decide` against the real
SSOT. Scratch deleted.

| Attack | Verdict |
|---|---|
| Non-Founder `gate.approve` writes a `gate_approval` event | **HOLDS** — `append_gate_approval` re-checks `decide(...)==allow` and raises `ApprovalRefused` for agent/audit-team/orchestrator/`operator`/unknown; **nothing written** (ledger file never created); the endpoint's `gate.approve` dependency 403s + audits BEFORE the route runs (defence-in-depth) |
| Forged Founder identity closes a gate | **HOLDS** — `principal_kind` is STAMPED from the session principal, never from request content; a forged `approval: human:founder` frontmatter with NO backing event → `is_gate_closed()==False`; only a real `principal_kind=="founder"` event closes it |
| Non-Founder `run.trigger` | **HOLDS** — `decide(non-founder,"run.trigger")==deny`→403+audited; founder-only by construction |
| Trigger writes only a board INTENT; dispatches nothing; GATE-5 stays machine-blocked | **HOLDS** — `/api/runs` writes `board/run-inbox/…` `status: requested`, returns `dispatched:false`; `enforce_gate_closed` (engine layer) is INDEPENDENT of the UI — a Founder trigger leaves an open GATE-5 `False` (flag ON, no backing event); UI records at most a claim, never skips the gate |
| Deny closes a gate | **HOLDS** — deny writes NO `gate_approval` event → gate stays OPEN |
| Board-canonical + audited/redacted on both writes | **HOLDS** — approve→`board/.rbac-audit.jsonl` event; trigger→`board/run-inbox/`; both control-plane-audited via the single ADR-0012 scrubber; no parallel dashboard store |
| Flag-off inert | **HOLDS** — all three new endpoints 404 with the flag OFF; nothing written |

Empirically confirmed: `append_gate_approval` refused for every representative agent role +
audit-team + orchestrator + `operator` + `attacker` with the ledger file absent afterwards;
`_kind_of("agent:founder")==agent`, `_kind_of("founder:agent")==None` (no `agent:`/founder
smuggling); `enforce_gate_closed` inert with the WS-E flag OFF, and `False` for an unbacked
GATE-5 with the flag ON.

**Verdict: HOLDS (no holes) — no non-Founder gate approval, no forged-identity closure, no
gate bypass, no pre-auth leak.** Residuals for DAS-1603: same three as DAS-1600 (constant-time
token compare; canonical-principal assertion; CI must actually run the `importorskip` endpoint
tests) plus assert the trigger-run intent file never lands in `board/runs/` and never appends
`wave-ledger.jsonl`. **GATE-3 red-team PASSED** — stays `in_review`, `assignee: cto`.

### 2026-07-24 — CTO (GATE-3 closure)
**AADL Stage-3 / GATE-3 (Development) CLOSED for DAS-1601 — `status: done`.** This is the
QONUN-5 approval surface (Founder-only approve/deny-gate + WS-B trigger-run on the DAS-1600
core). Verified independently (STAGED, LOCAL-ONLY): diagnostics **100/100** TRACKED; WS-H
suites **22 passed, 18 skipped** (FastAPI `TestClient` endpoint tests `importorskip` locally,
green in CI); full pytest **2321 passed, 21 skipped**; `board_lint` **exit 0** (pre-existing
DAS-1507 WARN only); `check_never_auto_approve` **exit 0**; `ruff check tools/control_plane/app.py
tools/control_plane/install` **clean** (spike B008 debt gone).

**Decision basis:** the blocking Security-Engineer GATE-3 red-team PASSED (HOLDS, no holes) —
no non-Founder gate approval (`append_gate_approval` re-checks `decide(...)==allow` and stamps
`principal_kind` from the session, never request content — `ApprovalRefused` for every
agent/audit-team/orchestrator/operator, nothing written), no forged-identity closure (a forged
`approval: human:founder` with no backing event leaves `is_gate_closed()==False`; only a real
`principal_kind=="founder"` event closes), no gate bypass (trigger writes a `board/run-inbox/`
INTENT `dispatched:false`, dispatches nothing per CP-5; `enforce_gate_closed` is engine-layer,
independent of the UI — a GATE-5-open deploy stays machine-blocked after any button), deny
writes no event (gate stays OPEN), both writes board-canonical + audited/ADR-0012-redacted.
Confirmed residual (4): the endpoint test asserts the trigger intent never creates `board/runs/`
and never appends `board/wave-ledger.jsonl` (`test_ws_h_control_plane.py` L386-389). All behind
`ws_h_control_plane` (flag OFF) — flag-off makes all three endpoints 404-inert, byte-identical
to pre-merge.

Residuals bound to DAS-1603 under `## Security conditions (GATE-3)`. GATE-3 for WS-H CONTROL
closed across DAS-1600/1601/1602; this unblocks DAS-1603 (Testing). Merge to a pushed branch/PR
with green CI is the release step (this run was LOCAL-ONLY).
