"""tools/a2a — A2A outbound governed endpoint (DAS-1610, extends ADR-0036 OB-1..OB-4).

Public surface:
  - :func:`tools.a2a.endpoint.handle_call` — the ONE governed edge an external
    agent-system caller reaches (FR-001, FR-005). Fail-closed order: the
    `a2a_outbound` flag (UNAVAILABLE when OFF) -> the TN-1 in-tenant bind check
    (REJECTED_TENANT on a hosted relay/registry) -> forbidden-control-field /
    shape validation (REFUSED_* — never silently stripped) -> the reused
    ADR-0009 admission gateway (`scripts/ws_b_admission.admit`, REJECTED_ADMISSION
    on deny) -> ADR-0012 redaction (`tools/mcp_bridges/redaction.safe_scrub`) +
    an attributed `a2a_call` audit event -> ONLY THEN an optional forward to an
    injected `intake_handler` (DAS-1611's `scripts/a2a_intake` is the real
    producer; this endpoint stands up no board-write path of its own).
  - :func:`tools.a2a.publish.publish` — the publish-is-a-Founder-act gate
    (A2-6/FR-003): `scripts/rbac.decide(principal, "a2a.publish")` (Founder-only,
    registered in `rbac.FOUNDER_ONLY` — a structural refuse-to-load lock) AND
    the TN-1 in-tenant check on the publish `target`, both logged (allow/deny
    symmetric) to `board/.events.jsonl` as an `a2a_publish` event.

Ships behind `a2a_outbound` (default OFF, `config/features.yaml`, landed DAS-1607).
With the flag OFF the endpoint is inert (`handle_call` returns UNAVAILABLE before
any side effect) — dispatch/board are byte-identical to pre-merge (SC-005).

Design: docs/design/a2a-outbound.md §2 (DAS-1609). Reuses, never re-implements:
the ADR-0009 admission gateway, the ADR-0012 §2 scrubber, `scripts/check_in_tenant.py`
+ `config/tenant_boundary.yaml` (TN-1), and `scripts/rbac.py` (the WS-E RBAC SSOT) —
mirrors the `tools/model_gateway` lazy path-based sibling-module loading pattern.
"""
from __future__ import annotations
