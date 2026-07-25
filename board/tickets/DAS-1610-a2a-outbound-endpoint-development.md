---
id: DAS-1610
title: A2A Development — outbound endpoint reusing the 0009 admission and 0012 redaction edge
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1606
goal: mustaqil-a2a-outbound
spec: 009-mustaqil-a2a-outbound
implements: [FR-001, FR-005]
labels: [security]
zone: tools/a2a
depends_on: [DAS-1608, DAS-1609]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (part A of GATE-3 for A2A OUTBOUND).**

Build the A2A outbound endpoint per the DAS-1608/DAS-1609 designs:

- Stand up the endpoint (out-of-process, mirrors the ADR-0033 governed-edge
  shape used elsewhere in MUSTAQIL) so that an external agent-system caller
  reaches "deliver this spec through the AADL-gated org" — governed delivery
  only, never raw tool/agent access (FR-001, extends ADR-0036 OB-1).
- Wire the endpoint through the existing ADR-0009 admission layer and ADR-0012
  redaction discipline at the boundary — reuse the same chain the ADR-0036
  outbound edge already uses; do NOT stand up a second, parallel admission path
  (FR-005).
- Wire the `a2a_outbound` feature flag (landed in DAS-1607) so the endpoint does
  not exist / is a no-op when the flag is OFF.
- Wire the in-tenant boundary check from DAS-1609's design so the endpoint
  refuses to resolve to, or be pointed at, a non-in-tenant address.

Fold in any on-branch prototype spike if one exists ahead of this ticket
(ADR-0020 — a spike is not a delivery until it passes in CI under a merged
ticket); if none exists, build fresh against the DAS-1608/DAS-1609 contracts.

## Acceptance criteria
- [ ] The A2A endpoint exists as an out-of-process governed surface; a call through it can only trigger AADL-gated delivery, never raw tool/agent access (FR-001).
- [ ] The endpoint routes every call through the existing ADR-0009 admission + ADR-0012 redaction chain; no second admission path exists (FR-005).
- [ ] With `a2a_outbound` OFF (default), the endpoint does not run / does not exist at dispatch time.
- [ ] The endpoint fails closed against a non-in-tenant target per the DAS-1609 boundary check.
- [x] Merged PR, green CI; `diagnostics.py` 100/100; no `project:` field (R9). — diagnostics 100/100 + board_lint exit 0 re-verified by the CTO at GATE-3 close; `a2a.publish ∈ FOUNDER_ONLY` confirmed. PR/merge/push is the orchestrator's step under the LOCAL-ONLY dispatch (no push/PR/commit this run).

## Log
### 2026-07-24 — Senior Product Manager
Created by `/daslab-plan` (A2A Development, endpoint half). Depends on both
Design children (DAS-1608, DAS-1609). Gated behind DAS-1606's binding sequencing
note (after WS-B, deferred until after WS-G's proof per Q12) — left in `status:
backlog` until that gate opens. Note for the implementing engineer: this ticket
requires the ADR-0034 headless runner (WS-B) to dispatch through — do not start
before WS-B's own epic is closed, regardless of this ticket's local dependency
graph (no WS-B id exists yet to encode that as `depends_on`).

### 2026-07-24 — Backend Engineer 1
Implemented behind `a2a_outbound` (default OFF, already landed DAS-1607 —
NOT re-added). Built `tools/a2a/` (new dir, zone-scoped, CODEOWNERS `/tools/`
covers it):

- `tools/a2a/endpoint.py` — `handle_call()`, the ONE governed edge (FR-001 /
  A2-5). Fail-closed order: `a2a_outbound` flag (dedicated line-scan reader,
  mirrors `rbac.is_enabled` — NOT yet in `feature_flags.py`'s `DEFAULTS`
  allowlist, so that shared reader can't see it) → TN-1 endpoint-bind check
  (reuses `scripts/check_in_tenant.is_in_tenant` verbatim) → forbidden-control-
  field / shape validation (§1.1, injection defense) → the reused ADR-0009
  admission gateway (`scripts/ws_b_admission.admit`, loaded via the same
  lazy path-based sibling-module pattern `tools/model_gateway/gateway.py`
  established — no second admission path) → ADR-0012 redaction
  (`tools/mcp_bridges/redaction.safe_scrub`, no third redactor) + an
  attributed `a2a_call` audit event to `board/.events.jsonl` → only then an
  optional forward to an injected `intake_handler` (DAS-1611's real producer;
  this module has no board-write code path of its own — unreachable by
  construction).
- `tools/a2a/publish.py` — `publish()`, the publish-is-a-Founder-act gate
  (A2-6/FR-003, §2.2). Two independent fail-closed legs: (1)
  `scripts/rbac.decide(principal, "a2a.publish")` — Founder-only; (2) TN-1 on
  the publish `target` (a hosted relay/registry blocks even a genuine
  Founder). Both allow/deny logged symmetrically as an `a2a_publish` event.
- `scripts/rbac.py` — added `"a2a.publish"` to `FOUNDER_ONLY` (the ONLY change
  in that file). `load_grants()` now structurally refuses to load an
  `rbac.yaml` that grants `a2a.publish` to any non-founder kind — verified by
  `tests/test_a2a_outbound_endpoint.py::test_a2a_publish_config_granting_to_non_founder_refuses_to_load`.
  **Footprint note (escalation-adjacent, logged not decided):** the existing
  `scripts/ws_e_health_check.py::check_rbac_drift` invariant asserts `founder`
  actually holds every `FOUNDER_ONLY` permission in the tracked
  `config/rbac.yaml` — without a matching grant this failed 3 pre-existing
  tests (`test_ws_e_health_check.py`) and would have gone CI-red. Added the
  single line `a2a.publish: allow` under `grants.founder` in
  `config/rbac.yaml` (one line, no other change) to keep that invariant green;
  this is outside the ticket's originally stated footprint
  (`tools/a2a/`, `scripts/rbac.py`, `config/tenant_boundary.yaml`, `tests/`)
  but was unavoidable to ship green CI — flagging for CTO/reviewer awareness
  rather than silently over-scoping.
- `config/tenant_boundary.yaml` — added ONE `a2a_outbound` inventory entry
  (`carries_code_ip: true`, role `a2a`, loopback bind, deliberately NOT in
  `accepted_external_roles`) — no other change.
- `tests/test_a2a_outbound_endpoint.py` — 25 tests, all green: FR-003/A2-6
  (Founder-only publish denied for all 32 agent roles + orchestrator/audit-
  team/unknown, refuse-to-load structural lock, Founder+in-tenant allow,
  Founder+hosted-target TN-1 block), FR-004/A2-4 (hosted endpoint bind
  rejected, never reaches admission/forward), FR-005/A2-5 (every admitted
  call passes `ws_b_admission.admit`, explicit-model precondition enforced,
  redaction verified against a fragmented fake secret string), FR-001/A2-2/
  A2-3 (flag-off inert with zero events, forbidden control fields in any
  casing/shape refused and never forwarded to the intake handler, a prompt-
  injection embedded in free text is admitted as inert DATA never gaining a
  control field, malformed-payload refusal).

FR→file+test map:
- FR-001 (governed surface, never raw tool/agent access) →
  `tools/a2a/endpoint.py::handle_call` →
  `test_hosted_bind_rejected_tenant`, `test_malformed_proposal_missing_required_field_refused`.
- FR-005 / A2-5 (ADR-0009 admission + ADR-0012 redaction reused, one edge) →
  `tools/a2a/endpoint.py` (`_ws_b_admission_mod`, `_redaction_mod`) →
  `test_admitted_call_passes_admission_and_is_redacted_and_audited`,
  `test_missing_explicit_model_rejected_by_admission`.
- A2-6 / FR-003 (publish is a Founder act) → `tools/a2a/publish.py::publish` →
  `test_a2a_publish_denied_for_every_agent_role`,
  `test_a2a_publish_denied_for_non_founder_non_agent_principals`,
  `test_a2a_publish_config_granting_to_non_founder_refuses_to_load`,
  `test_a2a_publish_allowed_for_founder_in_tenant_target`,
  `test_a2a_publish_founder_hosted_target_blocked_by_tn1`.
- A2-4 / FR-004 (in-tenant only) → `config/tenant_boundary.yaml` `a2a_outbound`
  entry + `endpoint.endpoint_bind_in_tenant` / `publish.publish`'s TN-1 leg →
  `test_hosted_bind_rejected_tenant`, `test_a2a_publish_founder_hosted_target_blocked_by_tn1`,
  and `python3 scripts/check_in_tenant.py` (exit 0, 7 endpoints declared).
- A2-2 / A2-3 (injection defense, proposal-not-approval) →
  `endpoint.FORBIDDEN_FIELDS` / `_forbidden_fields_present` →
  `test_forbidden_control_field_refused_never_forwarded` (parametrized over 8
  fields/casings), `test_repeated_forbidden_field_shapes_all_refused`,
  `test_prompt_injection_in_title_text_is_inert_text_not_instruction`.
- SC-005 (flag OFF byte-identical) → `endpoint.is_enabled` →
  `test_flag_off_is_inert_no_event_emitted`, `test_flag_off_intake_handler_never_invoked`.

Did NOT touch `scripts/a2a_intake/` (DAS-1611's zone), `config/features.yaml`
(flag already landed DAS-1607), or any ADR.

VERIFY (staged via `git add -A` first):
- `python3 scripts/diagnostics.py` → 100/100.
- `python3 scripts/check_in_tenant.py` → exit 0 (TN-1 OK, 7 endpoints).
- `python3 scripts/check_never_auto_approve.py` → exit 0 (182 tickets, no
  violations).
- `python3 scripts/board_lint.py` → exit 0 (180 tickets, 0 violations; the one
  pre-existing DAS-1507 body-status WARN is unrelated).
- `ruff check tools/a2a tests/test_a2a_outbound_endpoint.py scripts/rbac.py
  config/` → clean. Full-repo `ruff check .` shows 13 pre-existing errors,
  all in `evals/ux-researcher/` — outside this ticket's footprint, not
  introduced here.
- `python3 -m pytest` (full suite) → 2412 passed, 25 skipped, 0 failed.

Handing off to CTO (GATE-3 stage owner) for review; Security Lead consulted
per the design (admission/redaction reuse, in-tenant boundary, Founder-only
publish RBAC). Status → `in_review`, assignee → `cto`. No merged PR yet — this
is a local-only worktree change per dispatch constraints (⛔ no git
push/PR/commit to a remote); the reviewer merges after their own review per
the engineering git rules (one issue = one branch = one PR).

### 2026-07-24 — Security Engineer (GATE-3 red-team, blocking)
Acting as a malicious external caller against `tools/a2a/endpoint.py` +
`publish.py` + `scripts/rbac.py`. Ran the suite (`tests/test_a2a_outbound_endpoint.py`
+ `tests/test_a2a_intake.py` → 68 passed) plus ephemeral adversarial probes
(now deleted — no permanent files, no writes to the real board, nothing
published).

Per-item verdict (endpoint half):

| Attack | Verdict |
|---|---|
| Non-Founder / agent / orchestrator / audit-team / forged-founder `a2a.publish` | **HOLDS** — every non-founder principal `PublishRefused` + `deny` audited; `decide("agent:*","a2a.publish")` = deny (default-deny) |
| `a2a.publish` in `FOUNDER_ONLY` + refuse-to-load if granted to a non-founder kind | **HOLDS** — `a2a.publish ∈ FOUNDER_ONLY`; `load_grants()` raises `RbacConfigError` on an `rbac.yaml` granting it to `agent`; `config/rbac.yaml` grants it to `founder` (invariant consistent, WS-E drift-check green) |
| In-tenant only (TN-1): hosted publish target / hosted endpoint bind | **HOLDS** — hosted `target`/`bind_url` → `REJECTED_TENANT` / `PublishRefused` (exit-1 semantics), even for a genuine Founder; `check_in_tenant.is_in_tenant` reused verbatim; no external role added |
| One admission edge (ADR-0009 admit + ADR-0012 redaction), no bypass path | **HOLDS** — empty/absent model → `rejected_admission` before any forward; every non-admit branch returns before `intake_handler` is called (handler-call count 0 in all deny probes); endpoint has no board-write of its own |
| Flag OFF inert | **HOLDS** — `a2a_outbound` OFF ⇒ `UNAVAILABLE`, zero events written, `intake_handler` never invoked (no I/O) |
| Forbidden control field in payload (any casing: `approval`/`STATUS`/`Gate_Status`/`dispatch_order`) | **HOLDS** — `refused_forbidden_field`, never forwarded (key-scan; see residual note re: DAS-1611) |

**Overall: GATE-3 red-team PASSED for DAS-1610.** No external-caller publish
bypass, no non-in-tenant reach, no admission bypass, no gate/approval advance
reachable through this endpoint. The endpoint forwards ONLY a redacted payload
to an injected handler and holds no control-write of its own.

Residuals handed to DAS-1612 (formal negatives):
- Add a negative asserting `rbac._kind_of` normalizes an authenticated
  principal case/space-insensitively (`"FOUNDER "` → `founder`). NOT a hole
  here — the endpoint's `principal` is server-authenticated (never
  caller-supplied) and `publish()` is a Founder CLI act, not reachable through
  `handle_call` — but DAS-1612 should pin the invariant that the authenticating
  layer must pass a canonical principal and a caller can never supply
  `principal=founder`.
- Add an end-to-end negative through `handle_call` → real `a2a_intake` handler
  asserting the endpoint's `_redact_payload` runs before the handler (observed:
  redaction of `proposed_at` in the e2e path caused the intake to deny — good,
  but pin it deliberately rather than incidentally).
- **Cross-ticket:** the DAS-1611 frontmatter value-injection hole (see that
  ticket's red-team log) is reachable through this endpoint whenever the
  redactor preserves a newline in an injectable field value — DAS-1612's
  negatives must exercise the full `endpoint → intake` chain, not just each
  surface in isolation.

Keeping `status: in_review`, `assignee: cto` (GATE-3 stage owner). Edited only
this ticket file; no impl/config/test/permanent-file change; published nothing.

### 2026-07-24 — CTO (GATE-3-CLOSED — Development, independently verified)
Acting as GATE-3 (Development) stage owner for the endpoint half. The red-team
verdict was PASSED (all HOLD), and I independently re-confirmed the load-bearing
invariants rather than rubber-stamping.

**Confirmed:**
- `a2a.publish ∈ rbac.FOUNDER_ONLY` = **True** (re-run) — publish stays a
  Founder-only act; every non-founder principal is denied + audited, and
  `load_grants()` refuses to load an `rbac.yaml` granting it to a non-founder
  kind (`test_a2a_publish_config_granting_to_non_founder_refuses_to_load`).
- TN-1 in-tenant boundary enforced on both endpoint bind and publish target
  (hosted → `REJECTED_TENANT`/`PublishRefused`, even for a genuine Founder).
- One admission edge (ADR-0009 admit + ADR-0012 redaction) — no second admission
  path, no board-write of its own (`intake_handler` call count 0 on every deny
  branch).
- Flag OFF inert (zero events); forbidden control fields refused, never
  forwarded.
- The cross-ticket concern the red-team raised — the DAS-1611 frontmatter
  value-injection vector reachable THROUGH this endpoint (the endpoint's
  forbidden-field scan is key-only and ADR-0012 `safe_scrub` does not sanitize a
  plain newline) — is closed at the intake boundary (DAS-1611 fix) and proven by
  the `endpoint → intake` chain test. I re-ran the full endpoint+intake suite
  myself.

**Verification output (re-run by me):**
```
$ python3 -m pytest tests/test_a2a_intake.py tests/test_a2a_outbound_endpoint.py -q
88 passed in 0.20s
$ python3 scripts/diagnostics.py   → SCORE = 100/100
$ python3 scripts/board_lint.py    → exit 0 (only pre-existing unrelated DAS-1507 WARN)
$ rbac.FOUNDER_ONLY contains "a2a.publish" → True
```

**GATE-3 (Development) CLOSED for DAS-1610.** No external-caller publish bypass,
no non-in-tenant reach, no admission bypass, no gate/approval advance reachable
through this endpoint. Setting `status: done`. The flagged residual — a symmetric
endpoint-side value-injection negative in `tests/test_a2a_outbound_endpoint.py`,
plus the two red-team residuals from this ticket's own log (case/space-insensitive
principal normalization; the `_redact_payload`-before-handler e2e ordering
assertion) — are bound to DAS-1612 (the `tests`-zone Testing ticket, GATE-4), not
left only in this closed ticket. PR/merge/push is the orchestrator's step
(LOCAL-ONLY dispatch: no push/PR/commit this run).
