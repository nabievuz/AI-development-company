# Runbook — WS-E: tenant hardening (RBAC + audit/SIEM export + in-tenant runtime BOM) (ADR-0038)

**Goal (MUSTAQIL WS-E TENANT):** stand up the internal self-host hardening surface —
Founder-gate RBAC, an append-only audited trail with a read-only SIEM export, and the
in-tenant runtime BOM (LiteLLM gateway, deferred vLLM/SGLang eject-path, Presidio
guardrail chain, promptfoo golden-set evals) — on the tenant's own Linux VM, with the
whole surface shipping **inert** (`ws_e_tenant_hardening: false`,
`ws_e_openweight_ejectpath: false`).

**AADL Stage 5 — Deployment (closes GATE-5 for WS-E).** Per the WS-A/B/C/D deploy-runbook
precedent (`docs/runbooks/ws-a-tool-bridge.md` "Deployment" section,
`docs/runbooks/ws-d-langfuse-lens.md` "Deploy evidence"), Stage-5 for a flag-OFF
workstream is **documented, not executed**: this runbook is the deliverable, the literal
VM provisioning + flag flip is a separate, later, explicit Founder governance act. No
service is stood up, no flag is flipped, and no production code is written by this
ticket.

## What ships (already landed, GATE-3/GATE-4 closed)

| File | Role |
| --- | --- |
| `config/rbac.yaml` | RBAC SSOT — principal kinds (`founder`, `audit-team`, `orchestrator`, `agent:<role>`) and their permissions; Founder-identity-only `gate.approve` / `config.edit.security` |
| `config/tenant_boundary.yaml` | TN-1 in-tenant endpoint inventory; `accepted_external_roles: [model]` is the sole exception |
| `tools/model_gateway/gateway.py` | LiteLLM in-tenant gateway wiring; `enforce_boundary` pins any `role="model"` route to the declared `claude_model` host (R2 hardening, DAS-1585) |
| `tools/model_gateway/ejectpath.py` | Deferred vLLM/SGLang open-weight adapter, gated by its own `ws_e_openweight_ejectpath` sub-flag |
| `tools/model_gateway/flag.py` | Feature-flag reads for `ws_e_tenant_hardening` / `ws_e_openweight_ejectpath` |
| Guardrail chain + promptfoo config (DAS-1584) | Presidio (PII) → classifier → policy, admitted through the ADR-0033 governed edge; promptfoo golden-set-before-judge in `evals/` |
| `tests/test_ws_e_rbac_audit_export.py`, `test_ws_e_litellm_gateway.py`, `test_ws_e_guardrail_chain.py`, `test_ws_e_promptfoo_golden_evals.py`, `test_ws_e_tenant_hardening.py` | GATE-3/GATE-4 negative + positive test suites (63 passed, 0 xfailed) |

Design of record: `docs/design/ws-e-tenant-hardening.md` (GATE-2). Spec: `docs/specs/006-mustaqil-ws-e-tenant/SPEC.md` (FR-001…FR-008, SC-001…SC-005). ADR: `docs/adr/0038-enterprise-internal-self-host-hardening.md`.

## Stand up the in-tenant stack on the tenant VM (documented, NOT executed)

This section is the procedure a Founder/SRE follows when they choose to open the VM —
it is not run by this ticket.

1. **Provision the tenant VM (Q2).** A single Ubuntu (Linux-first) Linux VM, sized for
   the LiteLLM gateway + guardrail sidecars + audit ledger + (optional, later) an
   eject-path serving backend. One VM, not a cluster — Q10 rules out multi-tenant/HA
   topology as out of scope.
2. **Deploy the LiteLLM in-tenant gateway** (`tools/model_gateway/`) on that VM. Model
   routes are pinned to the `claude_model` host declared in
   `config/tenant_boundary.yaml` (`api.anthropic.com`) — the **sole** accepted external
   role per TN-1 (`accepted_external_roles: [model]`). Every other endpoint the gateway
   or runner touches (sandbox, observability, audit, memory, embeddings) resolves
   in-tenant; `scripts/check_in_tenant.py` fails closed on any hosted code/IP endpoint,
   including a rogue non-declared `role="model"` host (R2 hardening, DAS-1585) or a
   mis-pointed audit/SIEM sink.
3. **Optional, deferred: the vLLM/SGLang open-weight eject-path**
   (`tools/model_gateway/ejectpath.py`), gated by its own `ws_e_openweight_ejectpath`
   sub-flag, nested under `ws_e_tenant_hardening`. This is **not** the near-term build
   (Q9 keeps the Claude-subscription default) — it is a later Founder decision to open
   an in-tenant open-weight serving path, and it is only meaningful once
   `ws_e_tenant_hardening` is already ON. Stand it up only when that decision is made;
   until then the route stays inert and its declared target (when present) must itself
   resolve in-tenant.

## RBAC + audit activation

1. **Deploy `config/rbac.yaml`** to the tenant VM as the RBAC SSOT. Its two
   load-bearing rows: `gate.approve` and `config.edit.security` are **Founder-identity
   only** — no `audit-team` member and no `agent:<role>` principal ever holds them
   (structurally denied by `decide()`, not by convention). `audit-team` is a pure
   **read-only** principal: `audit.read` allowed, everything else denied. This is a
   small, rarely-edited file (one Founder + a small read-only team, Q6/Q8) — edited
   once at stand-up and reviewed as a `security_sensitive` +
   `governance_or_policy` + `permission_change` change (never `approval: auto*`,
   QONUN-5).
2. **Place the audit ledger outside the agent uid.** The append-only ledger
   (dev-mode default `board/.rbac-audit.jsonl` in-repo) MUST live, in production, at a
   filesystem path **owned by a non-agent uid** — e.g. `/var/lib/daslab/audit` — so the
   R1 file-trust boundary (DAS-1585 security condition) actually holds: an agent
   process has no filesystem write access to forge a raw `principal_kind: founder`
   ledger line there, regardless of what the in-repo dev-mode ledger trusts. This is
   the accepted mitigation for R1 (documented FS-ownership residual, not an in-process
   HMAC scheme) — confirmed by `test_r1_direct_filesystem_forged_line_is_a_documented_fs_ownership_residual`
   in `tests/test_ws_e_tenant_hardening.py`. Concretely, at stand-up:
   - Create a dedicated service account (e.g. `daslab-audit`) that owns
     `/var/lib/daslab/audit` and its `.rbac-audit.jsonl` file, mode `0700`/`0600`.
   - Run the agent/orchestrator process under a **different**, less-privileged uid
     with no write grant on that directory — only the sanctioned API path
     (`append_gate_approval`) may append, via a setuid helper or a service boundary the
     tenant's ops team controls, never a bare agent filesystem write.
   - Point `config/tenant_boundary.yaml`'s `audit_store` endpoint at that path
     (`file:///var/lib/daslab/audit`) so the SSOT and the real ledger location agree.
3. **Wire the read-only, one-way SIEM export.** The export reads the canonical event
   store (`board/.events.jsonl` in dev, the tenant's audit store in production),
   re-applies the ADR-0012 §2 redaction scrubber at the boundary, and writes outward as
   OTel/JSON to the tenant's SIEM. It has **no** write path back into the board, a
   ticket file, or an attestation — a SIEM outage or divergence changes no
   board/dispatch outcome (ADR-0025 stays system-of-record). The SIEM endpoint is
   declared in `config/tenant_boundary.yaml` as an in-tenant `role: audit` sink; a
   hosted SIEM URL fails `check_in_tenant.py` unless the tenant explicitly runs it
   off-box as its own later Founder act.

## Guardrails / evals

1. **Install deps on the VM** for the Presidio + classifier + policy chain and for
   promptfoo (golden-set-before-judge, ADR-0017/0020 no-false-green discipline). These
   are optional deps kept out of core `requirements.txt`, mirroring the WS-A/WS-D
   pattern (`tools/mcp_bridges/requirements-tools.txt`).
2. **Reuse the ADR-0033 governed edge** — Presidio and promptfoo are admitted only as
   out-of-process sidecars under `tools/`, gated by a least-privilege `## External
   tools` overlay grant compiled into `board/.tool-allowlist.json`, the same
   `mcp__.*` `PreToolUse` audit/deny hook WS-A and WS-D use, deny-all egress by
   default. No bulk `pip install`, no second admission path, no blanket grant — the
   per-role grant is reviewed on its own (DAS-1584).
3. **Presidio's own I/O is itself scrubbed** (Tier-B/F) — its PII findings must not
   leak unredacted. The promptfoo golden set runs **before** any LLM-judge scoring and
   includes an anti-gaming probe; a golden-set failure (including the probe) keeps the
   eval gate red regardless of judge output.

## Flip procedure (a Founder governance act, not this ticket)

Installing the deps above and flipping `ws_e_tenant_hardening` ON is performed **only**
after:

1. The VM is provisioned and the gateway/RBAC/audit/guardrail stack above is deployed
   and smoke-tested on it.
2. A Founder (or delegated SRE/DevOps Lead under Founder direction) reviews the
   deployed configuration — `config/rbac.yaml`, `config/tenant_boundary.yaml`, the
   audit-ledger FS ownership, and the egress allow-list — against this runbook.
3. The flip itself is a `security_sensitive` + `governance_or_policy` change to
   `config/features.yaml` (`ws_e_tenant_hardening: true`), never `approval: auto*`
   (QONUN-5) — same posture as every prior WS-A/B/C/D flip.
4. If/when the eject-path is separately opened, `ws_e_openweight_ejectpath: true` is
   its **own** later, explicit Founder act, only after step 3 is already ON.

The non-goals bound by ADR-0038/Q10 — SaaS packaging, multi-tenant isolation, billing,
SOC 2 certification tooling, SSO/SAML/SCIM — stay **rejected**; a PR introducing any of
them is out of scope regardless of who requests it (see `docs/design/ws-e-tenant-hardening.md`
§5).

## Rollback

Two independent, additive levers — either alone fully disables the surface; apply both
for defense in depth (same posture as `docs/runbooks/ws-d-langfuse-lens.md` "Rollback"):

1. **Flip `ws_e_tenant_hardening` OFF** in `config/features.yaml` (already the default
   at merge — this ticket does not touch it). The whole surface becomes inert: the
   RBAC evaluator, gateway admission wiring, guardrail chain, and audit/export paths
   are not exercised by dispatch; `ws_e_openweight_ejectpath` is meaningless with the
   parent flag OFF regardless of its own value.
2. **Leave deps uninstalled / remove the sidecar entries.** Absent the Presidio/
   promptfoo `.mcp.json` sidecar entries and the optional deps, those tools do not
   exist from Claude Code's point of view — nothing to call, allow-list, or deny. This
   mirrors the WS-A/WS-D structural rollback (delete the sidecar objects from
   `mcpServers`, leave other entries untouched).

Either lever is sufficient; there is no ordering dependency between them.

### Deploy evidence — flag OFF ⇒ byte-identical dispatch

At merge, `config/features.yaml` declares both `ws_e_tenant_hardening: false` and
`ws_e_openweight_ejectpath: false` (confirmed — no environment override). No
`/daslab-cycle` dispatch code path reads either flag; both are consumed only inside
`tools/model_gateway/` and the RBAC/guardrail `decide()` paths, none of which any
dispatch import touches. `tests/test_ws_e_tenant_hardening.py`'s
`test_sc005_composite_all_wse_surfaces_are_byte_identical_with_flags_off` and
`test_sc005_features_yaml_declares_both_wse_flags_off` assert this composite
byte-identity across RBAC + guardrail chain + gateway invoked together with both flags
OFF.

## Verify quickly

```bash
python3 scripts/board_lint.py
python3 scripts/diagnostics.py
python3 scripts/check_in_tenant.py
python3 scripts/check_never_auto_approve.py
python3 -m pytest tests/test_ws_e_tenant_hardening.py tests/test_ws_e_rbac_audit_export.py tests/test_ws_e_litellm_gateway.py tests/test_ws_e_guardrail_chain.py tests/test_ws_e_promptfoo_golden_evals.py -q
```
