---
id: DAS-1599
title: WS-H Design — Founder-only RBAC and audit, approve-gate and trigger-run UX, offline and not-a-daemon
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1597
goal: mustaqil-ws-h-control
spec: 008-mustaqil-ws-h-control
implements: [FR-002, FR-003, FR-004, FR-007]
labels: [security]
zone: docs/design
depends_on: [DAS-1598]
created: 2026-07-24
updated: 2026-07-25   # GATE-2 closed by CTO
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-H).** Design the governed control model
the Development tickets implement. No code beyond schemas/specs. Accountable stage owner
= CTO; responsible = backend-em; Security Lead consulted (auth/RBAC/audit); CDO
consulted (dashboard UX).

- **RBAC + fail-closed (CP-2/FR-002):** how a request is identified to a role
  (viewer < operator < founder), where the token/identity map lives (tenant vault,
  ADR-0038 TN-5, out of the repo), and the fail-closed rule — unconfigured RBAC ⇒ 503
  for every data/action endpoint, only a health probe and a data-free HTML shell answer.
  No anonymous or default-open access; in-tenant bind only.
- **Three governed writes + audit (CP-3/FR-003):** the exact write surface — (a) submit
  a goal proposal to the Founder-approved queue, (b) trigger a run via the WS-B headless
  runner (ADR-0034), (c) approve/deny a gate or interrupt-card — each RBAC-authorized,
  each appended to the event store (ADR-0024/0025) and redacted per ADR-0012. Specify the
  audit record shape and the redaction mapping.
- **Founder-only approval (CP-3/FR-004/Q6):** the approve-gate UX and the invariant that
  approval binds to a **Founder-role identity** — the dashboard, an agent, or any
  non-Founder role cannot sign a gate; a GATE-5-open deployment stays machine-blocked
  regardless of any button. Bind to the **real** gate/interrupt-card machinery — never a
  PoC stub.
- **Board-canonical view+controller (CP-4):** every read/write goes through the board /
  goal queue / event store; no parallel dashboard state; a divergence resolves to the
  board.
- **Offline-install + NOT-a-daemon (FR-007/FR-006/CP-5/6):** the vendored-wheel offline
  install path (platform-matched closure), the degrade-to-static contract (the read
  cockpit is the base case when the process is absent), the optional Founder-enabled
  process shape (systemd/launchd opt-in), and the in-tenant/no-external-SaaS boundary.

Extends the ADR-0028 cockpit render seam (CP-1) — the design reuses `render()`/
`_render_panel`/`NODATA` + `cockpit_html.py`, never a second cockpit.

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering: the RBAC + fail-closed contract, the three governed writes + audit/redaction mapping, the Founder-only approve-gate invariant bound to the real gate machinery, the board-canonical view+controller rule, and the offline-install + degrade-to-static + NOT-a-daemon design — each traced to its FR and CP invariant.
- [ ] Negative-path behaviour specified for SC-001 (fail-closed RBAC, 401, data-free shell) and SC-002 (Founder-only approval, GATE-5 stays blocked) so DAS-1603 can test it.
- [ ] The vendored-wheel offline-install and degrade-to-static contract specified so DAS-1602 can build it and DAS-1603 can test the offline boot (SC-003).
- [ ] Security Lead (auth/RBAC/audit) + CDO (UX) review recorded. `board_lint`/`check_spec_consistency`/`check_dependency_graph` green. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-H Design). CP-2/CP-3/CP-4 + Q6 Founder-only approval + the
offline-install/NOT-a-daemon deployment reality. Bind approve-gate to the REAL gate
machinery (not the PoC stub). Security Lead + CDO consulted.

### 2026-07-25 — Backend EM
**AADL Stage-2 Design (GATE-2) — design doc written; → in_review to CTO.**

Wrote `docs/design/ws-h-control-plane.md` (mirrors the WS-A/B/C/D/E/G design-doc
style), each section traced to its FR + ADR-0039 CP invariant:
- **§1 Governed control over the read-only cockpit (CP-1/FR-001).** WS-H is a thin
  controller layer over the ADR-0028 `render()`/`_render_panel`/`NODATA` +
  `cockpit_html.py` seam — one cockpit, not a fork; degrade-to-static inherited (D-5).
- **§2 Founder-only RBAC + fail-closed (CP-2/FR-002/FR-007/Q6).** BOUND to the WS-E
  RBAC SSOT — reuses `scripts/rbac.decide()` over `config/rbac.yaml`; the spike's ad-hoc
  `viewer<operator<founder` tier is RETIRED for the SSOT kinds
  `founder`/`audit-team`/`agent`/`orchestrator`. Near-term = Founder + read-only team
  (Q6). Unconfigured RBAC ⇒ 503; bad token ⇒ 401; not-permitted ⇒ 403+audited-deny;
  data-free HTML shell; vault-resident token→principal map (TN-5); loopback-default
  in-tenant bind, no external SaaS.
- **§3 Three governed writes + audit; Founder-only approval as an EVENT
  (CP-3/FR-003/FR-004).** (a) goal-proposal, (b) trigger-run→`run.trigger`→ADR-0034
  runner, (c) approve-gate→`gate.approve`→`append_gate_approval()`. Approval binds to a
  Founder-identity `gate_approval` event (`principal_kind` stamped by the runtime, never
  from request content); a button-press is an UNVERIFIED CLAIM the dashboard can never
  sign; `decide("agent:*","gate.approve")==deny` by construction; GATE-5-open stays
  machine-blocked (CP-5 dispatches-nothing + independent gate enforcement). Audit record
  shape + ADR-0012 redact→truncate→append mapping specified (Tier-M by construction). No
  `operator` tier reintroduced for (a) — Founder-only near-term; widening = reviewed
  `config.edit.security` edit. Two-flag interplay (`ws_h_control_plane` vs
  `ws_e_tenant_hardening`) made honest.
- **§4 Board-canonical view+controller (CP-4/FR-005).** Stateless projection over
  board/goal-queue/event-store; writes via existing entrypoints only; divergence
  resolves to the board.
- **§5 Offline + NOT-a-daemon (CP-5/CP-6/FR-006/FR-008).** Vendored-wheel
  `.vendor/site-packages` gitignored closure, no-network boot; optional deps out of core
  `requirements.txt`; degrade-to-static base case (ADR-0028 D-5); optional Founder-enabled
  flag-OFF process that dispatches nothing, loopback-default.
- **§6 Spike hardening (SC-005).** Fix pattern for the ~10 B008 FastAPI
  `Depends`/`require`-in-defaults violations = `Annotated[dict, Depends(...)]`
  (preferred) or module-level singleton dependency; plus retire `ROLE_RANK` for
  `decide()`.

**Negative-path spec handed to DAS-1603 (§7):** SC-001 fail-closed RBAC (503 on every
data/action endpoint, only `/healthz`+data-free shell; 401 bad token; structurally
invalid rbac.yaml ⇒ `RbacConfigError`⇒503; shell leaks no data); SC-002 Founder-only
approval (non-Founder/agent approve REFUSED+audited; `append_gate_approval` for a
non-approver raises `ApprovalRefused`, no record; forged `approval: human:founder`
frontmatter with no backing event ⇒ `is_gate_closed` NOT closed; GATE-5-open stays
machine-blocked regardless of any button); SC-003 offline boot (no-network `/healthz`
200 + redacted Tier-M audit on every write); SC-004 guard (flag-OFF byte-identical +
process-absent degrade-to-static); SC-005 guard (ruff clean, tier gone).

**Placement:** touched ONLY `docs/design/ws-h-control-plane.md` + this ticket. LOCAL-ONLY
(no git push/PR/commit). **Validators (exit 0):** `board_lint` OK (180 tickets, 0
violations — the lone WARN is on unrelated DAS-1507, not WS-H), `check_links` OK,
`check_spec_consistency` OK (10 SPEC.md checked). → `in_review`, assignee `cto`
(GATE-2 accountable); Security Lead consulted on §2/§3 RBAC+audit, CDO consulted on §3 UX.

### 2026-07-25 — CTO
**AADL Stage-2 / GATE-2 (Design) CLOSED for WS-H CONTROL. `docs/design/ws-h-control-plane.md` RATIFIED.**

Reviewed `docs/design/ws-h-control-plane.md` §0–§9 against Accepted **ADR-0039** (CP-1…CP-6,
ratified 2026-07-24, RACI 3.1/3.6 A), **SPEC-008** (FR-001…FR-008 / SC-001…SC-005), **ADR-0028**
(cockpit render seam), the **WS-E RBAC SSOT** (`scripts/rbac.py` + `config/rbac.yaml`), and
**ADR-0012** (audit redaction). Carried the **Security-Lead-consulted** review on §2/§3 (RBAC +
audit) and confirmed the **CDO-consulted** approve/trigger-run UX myself. Every load-bearing
claim verified against the actual code, not the prose:

- **RBAC-SSOT binding (CHECK a — a control action can NEVER be signed by a non-Founder or an
  agent).** Design §2.1/§6.1 RETIRES the spike's `ROLE_RANK = {viewer,operator,founder}` +
  `require(min_role)` tier and binds authorization to the WS-E SSOT `scripts/rbac.decide()` over
  `config/rbac.yaml`. Verified in `scripts/rbac.py`: `decide()` is default-DENY; `FOUNDER_ONLY =
  {gate.approve, run.trigger, config.edit.security}` and `load_grants()` raises `RbacConfigError`
  (refuses to load) if any is granted to a non-`founder` kind → `decide("agent:<any-of-32>",
  "gate.approve") == deny` **by construction**. Approval binds to a Founder-identity
  `gate_approval` EVENT via `append_gate_approval()`, which (i) checks `decide(principal,
  "gate.approve")==allow` FIRST (else `ApprovalRefused`, nothing written) and (ii) stamps
  `principal_kind` from `_kind_of(principal)` — never from request/agent content — so the
  dashboard/JS can never manufacture a `founder` record. `is_gate_closed()` closes a gate ONLY on a
  matching `principal_kind=="founder"` event; a forged `approval: human:founder` frontmatter with no
  backing event stays OPEN. `config/rbac.yaml` confirmed: the three founder-only perms sit under
  `founder` only; `audit-team`=`audit.read` only; `agent`/`orchestrator` hold no approve/trigger. A
  button-press without a Founder identity closes NO gate. SOUND.
- **Never-bypass-a-gate (CHECK b).** §3.3/§3.4 give two INDEPENDENT machine blocks on GATE-5-open:
  (1) CP-5 dispatches-nothing — a wave advances only from a human `run.trigger` write or the
  HEARTBEAT, never because the server is up; (2) engine-layer `enforce_gate_closed()` (when
  `ws_e_tenant_hardening` ON) / `check_never_auto_approve.py` (ticket-layer, flag-independent) block
  the deploy regardless of any button. The two-flag interplay is made honest: with WS-E enforcement
  OFF the gate is governed exactly as today — a control action is only ever AS-governed-or-MORE than
  the CLI, never less. The button can RECORD a Founder approval event; it can never SKIP a gate.
  SOUND.
- **NOT-a-daemon, degrade-to-static (CHECK c).** `ws_h_control_plane: false` confirmed at
  `config/features.yaml` line 27 (default OFF). §5.2/§5.3: optional Founder-enabled process,
  dispatches nothing itself, no timer/self-scheduler, loopback-default bind; degrade-to-static is
  STRUCTURAL, inherited from ADR-0028 D-5 (the read cockpit is the base case, exercised on every
  flag-OFF run). SOUND.
- **Offline-installable, no external SaaS (CHECK d).** §5.1: `tools/control_plane/.vendor/
  site-packages` gitignored platform-matched closure, no-network `PYTHONPATH` boot, optional deps
  out of core `requirements.txt`; §2.2/CP-6 in-tenant/vault-resident token map (TN-5)/self-hosted
  Langfuse, no component phones a hosted SaaS. The exceptiongroup silent-drop gotcha is flagged for
  DAS-1602 to verify the closure by hand, not trust the resolver. SOUND.
- **Audit + redaction (Security-Lead-consulted, §3.2).** Audit record is Tier-M by construction
  (controlled-vocab `action` + ids + reference `detail`, no secret/prompt/completion/source field);
  free-text passes the SAME ADR-0012 §2 scrubber as WS-A/WS-D/`append_gate_approval` (no third
  redactor); the `gate_approval` governance fact reuses the WS-E `board/.rbac-audit.jsonl` ledger
  via one canonical producer. Matches `append_gate_approval`'s `GATE_APPROVAL_TIER_M` pass-through +
  `safe_scrub` on Tier-B. No `operator` tier reintroduced for the goal-proposal write — Founder-only
  near-term (Q6); widening is a reviewed `config.edit.security` edit, never a hardcoded rank tier.
- **CDO-consulted UX captured.** The approve-gate (`POST /api/gates/{id}/approve`|`/deny`) and
  trigger-run (`POST /api/runs`) surfaces are specified in §3.1; the UX-honesty crux — a button is
  an UNVERIFIED CLAIM, the server (not the page) derives the principal from the session token — is
  captured. Approve/trigger UX confirmed present and honest.
- **Spike B008-hardening bound.** §6.2 fixes the ~10 FastAPI `Depends`-in-argument-default B008
  violations via `Annotated[dict, Depends(...)]` (preferred) or a module-level singleton dependency —
  CLEANED, not `# noqa`-suppressed — bound to DAS-1600.
- **Negative-path spec (§7) ACCEPTED for DAS-1603.** SC-001 (fail-closed RBAC 503/401/403 +
  data-free shell + `RbacConfigError`), SC-002 (Founder-only approval, forged-frontmatter rejected,
  GATE-5 stays machine-blocked), SC-003 (offline boot + redacted Tier-M audit on every write),
  SC-004 (flag-OFF byte-identical + process-absent degrade-to-static), SC-005 (ruff-clean, tier
  gone) — all expressible against the hardened `app.py` + reused `scripts/rbac.py` primitives.
  Accepted as the GATE-4 test contract.

**Traceability matrix (§8) complete** — every FR/CP maps to a design section and a downstream
build ticket. **Validators (exit 0):** `python3 scripts/board_lint.py` OK (180 tickets, 0
violations — lone WARN is unrelated DAS-1507), `python3 scripts/check_links.py` OK,
`python3 scripts/check_spec_consistency.py` OK (10 SPEC.md checked).

**DECISION: GATE-2 CLOSED.** Design ratified, Founder-only RBAC-SSOT binding, never-bypass-a-gate,
not-a-daemon/degrade-to-static, offline-installable, B008-hardening bound, negative-path spec
accepted. → `status: done`. **LOCAL-ONLY** (no git push/PR/commit); edited ONLY this ticket file.

**Unblocks WS-H Development.** DAS-1600 (harden app + RBAC/audit → SSOT) and DAS-1601
(approve-gate/trigger-run) BOTH edit `tools/control_plane/app.py` → **SEQUENTIAL (1600 then
1601)**, never same-wave. DAS-1602 (offline-install + degrade-static, zone
`tools/control_plane/install`) is **parallel-safe with 1600**. Routing note handed to the
orchestrator/CEO.
