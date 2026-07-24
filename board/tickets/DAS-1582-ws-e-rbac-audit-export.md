---
id: DAS-1582
title: WS-E Development — RBAC Founder-only approval plus team read-only audit and SIEM export
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1579
goal: mustaqil-ws-e-tenant
spec: 006-mustaqil-ws-e-tenant
implements: [FR-001, FR-002, FR-003]
labels: [security]
zone: config/rbac
depends_on: [DAS-1581]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-E, part 1).** Build the RBAC + audit
hardening per the DAS-1581 design. Security Lead consulted.

- **TN-3 / FR-001 (RBAC, Q6):** implement the principal/role/permission model — a
  Founder-identity principal is the ONLY actor who can approve an AADL gate; an agent
  identity can never hold gate-approval authority (structural, fail-closed — an
  unknown/agent principal denies); a non-Founder actor's approval string is refused. A
  small team holds **read-only audit** — read the trail; approve/trigger/mutate nothing.
  Every never-auto-approve category (QONUN-5) maps to the human-only Founder role.
- **TN-4 / FR-002 (audit export):** a read-only exporter of the event store +
  attestation (ADR-0024/0025/0031/0032) to the tenant SIEM as OTel/JSON, redacted per
  ADR-0012; the export is one-way (never writes back to the board) and carries no
  source/IP.
- **TN-5 / FR-003 (secrets/egress):** secrets resolved from the tenant vault (never in
  repo or spans — gitleaks + ADR-0012); egress bounded by the tenant-boundary allow-list
  (reuse the WS-A `config/egress-allowlist.yaml` posture, do not fork).
- **FR-008:** guarded by `ws_e_tenant_hardening` (OFF); with the flag OFF the surface is
  inert and dispatch is unchanged.

Hand the matching negative tests (SC-001/SC-002) to DAS-1585.

## Acceptance criteria
- [ ] RBAC model enforced: Founder-identity-only gate approval (agent/non-Founder refused, fail-closed); team read-only audit cannot approve/trigger/mutate (SC-001).
- [ ] Read-only SIEM exporter emits redacted OTel/JSON (ADR-0012); one-way, no board write-back, no code/IP (SC-002).
- [ ] Secrets from the tenant vault (never repo/spans); egress bounded by the boundary allow-list (no fork of the WS-A profile).
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge; `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-E Development, part 1). TN-3 RBAC (Founder-only approval + team read-only audit, Q6) + TN-4 SIEM audit export + TN-5 secrets/egress; all behind `ws_e_tenant_hardening` OFF.

### 2026-07-24 — Backend EM
AADL Stage-3 Development — RBAC + audit + read-only SIEM export built behind `ws_e_tenant_hardening` (OFF), against the DAS-1581 design §1-2. Security Lead consulted (per design §8); routing to CTO for GATE-3.

**FR → file → test map:**
- **FR-001 / TN-3 (RBAC Founder-gate, Q6)** — `config/rbac.yaml` (SSOT: 4 principal kinds + grant matrix; `gate.approve`/`run.trigger`/`config.edit.security` under `founder` only; agent has `board.work:own` + `audit.read:own` and NOTHING founder-only) + `scripts/rbac.py` `decide()` (default-deny; `_kind_of` fail-closes unknown principals; `load_grants()` REFUSES to load a config that grants a founder-only permission to a non-founder kind — the structural QONUN-5 exclusion). Tests in `tests/test_ws_e_rbac_audit_export.py`: `test_every_agent_role_denied_founder_only_permissions` (all 32 roles), `test_audit_team_is_read_only`, `test_orchestrator_routes_but_cannot_originate_approval_or_trigger`, `test_founder_is_the_only_gate_approver`, `test_unknown_or_forged_principal_holds_nothing`, `test_load_refuses_founder_only_permission_granted_to_agent`, `test_every_qonun5_category_maps_to_founder`.
- **FR-001 crux (approval = attributed EVENT, not a string)** — `scripts/rbac.py` `append_gate_approval()` (stamps `principal_kind` from the authenticated principal via `_kind_of`, NOT caller input; refuses any non-approver before writing) + `is_gate_closed()` (a gate closes ONLY with a matching Founder-identity `gate_approval` event; a `approval: human:founder` frontmatter claim with no backing event = forged, gate stays OPEN). Tests: `test_forged_frontmatter_claim_closes_no_gate`, `test_matching_founder_event_closes_the_gate`, `test_agent_cannot_emit_founder_gate_approval`, `test_appended_record_is_stamped_founder_kind_by_runtime`.
- **FR-002 / TN-4 (audit + read-only SIEM export)** — append-only attributed `gate_approval` ledger `board/.rbac-audit.jsonl` (Tier-M by construction; ADR-0012 redact-at-write; gitignored runtime state) + `scripts/rbac_siem_export.py` (read-only one-way OTel/JSON export; reuses the ADR-0012 scrubber + `check_in_tenant` VERBATIM — no fork; ADR-0012 redaction again at the boundary; NO write-back path; a hosted audit sink blocks). Tests: `test_audit_ledger_is_append_only`, `test_gate_approval_record_carries_no_secret_field`, `test_export_is_readonly_otel_json_and_never_writes_back`, `test_redaction_probe_over_exported_record`, `test_hosted_siem_sink_blocks_the_export`, `test_model_call_is_the_sole_accepted_external_exception`.
- **FR-003 / TN-5 (secrets/egress)** — no new secret store; the SIEM sink resolves as an in-tenant `role: audit` endpoint in `config/tenant_boundary.yaml` and reuses the landed `check_in_tenant.py` boundary + the WS-A `egress-allowlist.yaml` posture (not forked). Records carry fact-of-use metadata only (no secret value).
- **FR-008 (flag OFF inert)** — `is_enabled()` + `enforce_gate_closed()` (inert when OFF) + `export_audit()` (returns `ran=False` when OFF). Tests: `test_export_inert_when_flag_off`, `test_rbac_enforcement_inert_when_flag_off`. `config/features.yaml` UNCHANGED (flag stays `false`; the flag line is owned by DAS-1543/concurrent DAS-1583).

**Forged-founder-string rejected (evidence):** `is_gate_closed("DAS-1586", "gate5_deployment", approval_claim="human:founder", audit_path=<empty ledger>)` → `(False, "...forged/absent approval rejected...")`. An agent principal calling `append_gate_approval` raises `ApprovalRefused` and writes nothing, so it can never stamp `principal_kind: founder`.

**Verify (STAGED, `git add -A`):** `scripts/diagnostics.py` = 100/100; `pytest tests/test_ws_e_rbac_audit_export.py` = 23 passed; full suite = 2201 passed, 4 skipped; `check_never_auto_approve.py` exit 0; `board_lint.py` exit 0 (only the pre-existing DAS-1507 body-status WARN); `check_in_tenant.py` exit 0; `ruff check` clean on the three new files. No `/home//Users` literals; the redaction-probe test fragments its secret-shaped strings with `+`.

**Footprint:** `config/rbac.yaml`, `scripts/rbac.py`, `scripts/rbac_siem_export.py`, `tests/test_ws_e_rbac_audit_export.py`, `.gitignore` (added `board/.rbac-audit.jsonl` runtime ledger, consistent with the WS-A `.tool-audit.jsonl` convention). Did NOT touch `config/features.yaml`, `tools/model_gateway/` (DAS-1583), or `tools/guardrails/` (DAS-1584).

**Note for reviewer (routing):** the `gate_approval` audit trail is implemented as a DEDICATED append-only ledger (`board/.rbac-audit.jsonl`) owned by `scripts/rbac.py` rather than as a new `event_type` in the canonical `scripts/dgox/events.py` store — because `dgox/events.py` is outside this ticket's `config/rbac` zone and is a shared hot file (concurrency). Wiring `gate_approval` into `EventStore._VALID_EVENT_TYPES` for full canonical-stream unification is a small additive follow-up the orchestrator can route as its own ticket if the CTO wants it in the canonical store; the SIEM exporter already reads the dedicated ledger read-only. LOCAL-ONLY: no commit/branch/PR/push.

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking)

Adversarial in-code verification of the RBAC + audit + SIEM-export surface (the human-only approval boundary, QONUN-5). Ran the WS-E suites (55 passed incl. 23 RBAC) AND ephemeral hand-crafted exploit probes (deleted, no permanent test files — SC-001/002 formal tests are DAS-1585's).

**Completeness check (agent stalled mid-finalize):** `scripts/rbac.py` read end-to-end — `decide()`, `load_grants()`, `_kind_of()`, `append_gate_approval()`, `build_gate_approval()`, `is_gate_closed()`, `enforce_gate_closed()`, `iter_gate_approvals()`, `_append_audit()` are ALL fully implemented. No TODO, no `pass`-stub, no half-written function, no truncation anywhere in the security path. `rbac_siem_export.py` likewise complete. **Verdict: CODE COMPLETE, not truncated.**

**Per-item verdicts:**
| Item | Verdict | Evidence (ephemeral probe) |
|---|---|---|
| Agent cannot approve — STRUCTURAL | **HOLD** | `decide("agent:<any>","gate.approve")`→deny for every agent role; permission ABSENT from the `agent` kind by construction, not a string check; `load_grants()` REFUSES to load an rbac.yaml granting `gate.approve` to `agent` (`RbacConfigError`). |
| Every non-founder principal denied founder-only | **HOLD** | `audit-team`/`orchestrator`/`agent:*`/unknown/empty all deny on `gate.approve`,`run.trigger`,`config.edit.security`; only `founder` allows. |
| Forged founder string rejected | **HOLD** | `is_gate_closed(..., approval_claim="human:founder", <empty ledger>)`→`(False, "...forged/absent approval rejected")`. Gate stays OPEN with no backing event. |
| Agent cannot emit founder-stamped event | **HOLD** | `append_gate_approval(principal="agent:cto", ...)`→`ApprovalRefused`, ledger byte-untouched (verified file never created). `principal_kind` is stamped by runtime `_kind_of`, never caller input. |
| Audit-team read-only | **HOLD** | `audit.read`=allow; `gate.approve`/`config.edit.security`/`board.mutate.routing`/`board.work`/`run.trigger` all deny. |
| Audit trail append-only, ADR-0012 redacted, no secret field | **HOLD** | Genuine founder record carries no secret/token/key field; Tier-B values scrubbed at write; ledger `board/.rbac-audit.jsonl` gitignored (`.gitignore:60`). |
| SIEM export one-way | **HOLD** | Zero write/append call-sites into board/event-store/ledger in `rbac_siem_export.py` (source-scanned); hosted audit sink BLOCKS (`BoundaryError`) before any export; flag-OFF inert (`ran=False`). |

**Overall: PASS — no RBAC approval bypass. The specified structural guarantees all HOLD; the sanctioned API path is closed to every non-Founder principal.**

**Residual handed to DAS-1585 (NOT a GATE-3 blocker):** `is_gate_closed()` trusts the CONTENT of the append-only ledger. The sanctioned producer (`append_gate_approval`) is structurally closed to agents — HOLD — but a DIRECT filesystem append of a line stamped `principal_kind: founder` to `board/.rbac-audit.jsonl` (bypassing the API) WOULD close the gate. This is the same file-trust vector the whole file-based board shares (and the tenant runbook places the real ledger at `file:///var/lib/daslab/audit`, owned outside the agent uid, not the in-repo path). Harden in DAS-1585: HMAC/signed records or FS ownership by a non-agent uid, plus a negative test asserting a forged raw ledger line is rejected. Recorded, not blocking.

Verdict: keep `status: in_review`; `assignee: cto`. **GATE-3 red-team PASSED — cleared for CTO ratification.** LOCAL-ONLY: only this ticket file edited.

### 2026-07-24 — CTO (GATE-3 closure)

**AADL Stage-3 / GATE-3 (Development) CLOSED for WS-E part 1 (RBAC + audit + SIEM export).** Ratified on the blocking Security-Engineer red-team (PASSED — no RBAC bypass, no forged-founder gate closure via the sanctioned API, no code/IP endpoint leak) plus my own independent staged verification.

**Independent verification (STAGED, `git add -A` first):**
- `python3 scripts/diagnostics.py` → **100/100** (all categories PASS incl. `tn1-in-tenant-boundary`, `no-committed-secrets`), exit 0.
- `python3 -m pytest tests/test_ws_e_rbac_audit_export.py tests/test_ws_e_litellm_gateway.py tests/test_ws_e_guardrail_chain.py tests/test_ws_e_promptfoo_golden_evals.py -q` → **55 passed** (23 RBAC in this ticket).
- `python3 -m pytest -q` → **2201 passed, 4 skipped**, 0 failed.
- `python3 scripts/check_never_auto_approve.py` → exit 0 (182 tickets, no violations).
- `python3 scripts/board_lint.py` → exit 0 (180 tickets, 0 violations; only the pre-existing unrelated DAS-1507 body-status WARN).

**Judgment:** the FR-001 RBAC approval boundary is STRUCTURAL, not advisory — `gate.approve`/`config.edit.security`/`run.trigger` are absent from the `agent` kind by construction; `decide(agent, gate.approve)` denies; `load_grants()` REFUSES a config granting a founder-only permission to a non-founder kind; approval is an attributed `gate_approval` EVENT (`principal_kind` stamped by runtime `_kind_of`, never caller input); a bare `approval: human:founder` frontmatter claim with no backing Founder event closes no gate (QONUN-5 double-lock). Read-only audit team cannot approve/trigger/mutate. TN-4 SIEM export is read-only one-way OTel/JSON, ADR-0012-redacted at write AND boundary, no write-back, hosted sink blocks. All behind `ws_e_tenant_hardening` OFF (inert; flag-off byte-identical).

**Residual bound to DAS-1585 (R1 — NOT a GATE-3 blocker):** `is_gate_closed()` trusts ledger CONTENT; the sanctioned producer is structurally closed to agents, but a DIRECT FS append of a founder-stamped line to `board/.rbac-audit.jsonl` would close a gate — the same file-trust vector the whole file-based board shares, and the tenant runbook places the real ledger outside the agent uid (`file:///var/lib/daslab/audit`). Harden in DAS-1585 (signed/HMAC records or non-agent FS ownership + a forged-raw-line negative test). Bound into DAS-1585 `## Security conditions (GATE-3)` so it cannot be silently dropped.

**Decision: GATE-3 CLOSED → `status: done`.** LOCAL-ONLY: only this ticket file edited (no commit/branch/PR/push). Landing the staged diff as a merged PR with green CI remains the open LOCAL-ONLY-to-mainline question carried across the WS-E workstream (Founder/CTO decision, tracked outside this ticket). This unblocks DAS-1585 (Testing) once DAS-1583/1584 also close.
