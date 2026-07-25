# SPEC 009 — MUSTAQIL A2A OUTBOUND (DasLab as a callable governed agent)

- **Goal:** mustaqil-a2a-outbound
- **Owner:** backend-em
- **Status:** reviewed
- **Reviewed:** 2026-07-24 — CTO (DAS-1607, GATE-1). All six functional
  requirements and all five success criteria below were checked coherent, testable,
  and traceable 1:1 to the ADR-0040 invariants (A2-1…A2-6): governed-delivery →
  A2-1, goal-proposal-never-approval → A2-2, Founder-act publish → A2-6, in-tenant
  only → A2-4, admission+redaction reuse → A2-5, feature-flag-OFF → A2-6; each
  success criterion exercises the same invariants. No `[NEEDS CLARIFICATION]`
  markers outstanding. The untrusted-caller-input / injection-defense invariant
  (A2-3) is carried by ADR-0040 and exercised in the Stage-2 negative tests
  (DAS-1612); the WHAT/WHY here stays sound.

> WHAT/WHY only. The HOW (the A2A wire protocol shape, endpoint framework, queue
> intake mechanics) lives in ADR-0040 (`docs/adr/0040-a2a-outbound-surface.md`,
> Accepted) and the AADL Stage-2 design tickets, not here. Binds to ADR-0036 (OB-1…OB-4, which this extends), ADR-0038
> (TN-1 in-tenant boundary), ADR-0009 (admission layer), ADR-0012 (redaction),
> QONUN-5 (never-auto-approve / Founder-only approval), the master prompt
> (`docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md`, Part 1 interop
> extension note + Part 2), and Founder discovery answer Q12 (defer A2A until
> after the WS-G proof lands; build it as the first post-proof reach increment).

## User Scenarios

- **P1 —** Given another agent system reaches DasLab through the A2A outbound endpoint, when it invokes DasLab, then it gets governed delivery only — "deliver this spec through the AADL-gated org" — with no ability to skip a gate, self-approve, or bypass never-auto-approve (extends ADR-0036 OB-1).
- **P1 —** Given an external caller submits work through the A2A endpoint, when the submission is intaken, then it is recorded ONLY as a goal proposal — never as a gate approval — and a Founder must still approve any gate the resulting work reaches (QONUN-5).
- **P1 —** Given the A2A outbound endpoint is disabled or not yet published, when anyone asks to expose it beyond that state, then doing so is an explicit Founder act, never automated or self-triggered by a workstream ticket (extends ADR-0036 OB-4).
- **P1 —** Given the A2A feature flag is OFF (default), when a wave runs, then dispatch and board behavior are byte-identical to pre-merge — the endpoint simply does not exist.
- **P2 —** Given the A2A endpoint is live, when it is reached from outside the tenant boundary, then the call is refused — the surface is in-tenant only (ADR-0038 TN-1), with no external/hosted A2A relay or registry carrying code or IP.
- **P2 —** Given an A2A call crosses the outbound boundary, when its payload is prepared, then it passes the same ADR-0009 admission and ADR-0012 redaction discipline as the existing ADR-0036 outbound edge — no secret or unredacted transcript ever crosses, and no second admission path is created.

## Functional Requirements

- **FR-001** — DasLab MUST expose an A2A outbound endpoint as a governed-delivery unit extending ADR-0036 OB-1 — an external caller reaches "deliver this spec through the AADL-gated org," never raw tool or agent access, and cannot make DasLab skip a gate or bypass never-auto-approve.
- **FR-002** — Any submission an external caller makes through the A2A endpoint MUST be intaken ONLY as a goal proposal (a board-intake artifact awaiting Founder review) and MUST NEVER be treated as, auto-converted into, or mistaken for a gate approval (QONUN-5); the proposal MUST NOT write routing fields, self-approve, or advance a ticket past an open AADL gate (C3/C4).
- **FR-003** — Publishing the A2A endpoint (exposing it beyond a disabled/internal state, or pointing it at any external registry/relay) MUST be an explicit Founder act (extends ADR-0036 OB-4, QONUN-5) — never automated, never self-triggered by a workstream ticket, and logged to `board/.events.jsonl`.
- **FR-004** — The A2A endpoint MUST operate in-tenant only (ADR-0038 TN-1): no external/hosted A2A registry, relay, or endpoint that carries code or IP is permitted; the endpoint is reachable only from within the declared tenant boundary.
- **FR-005** — The A2A surface MUST reuse the existing ADR-0009 admission layer and ADR-0012 redaction discipline at its boundary, identically to the ADR-0036 outbound edge — no secret or unredacted tool transcript crosses the boundary, and A2A MUST NOT stand up a second, parallel admission path.
- **FR-006** — The A2A outbound surface MUST be feature-flagged in `config/features.yaml` DEFAULT **OFF** (ADR-0019); with the flag OFF, dispatch and board behavior are byte-identical to pre-merge; rollback is disabling the flag / removing the endpoint wiring.

## Success Criteria

- **SC-001** — A test proves an external A2A call cannot advance a ticket past an open AADL gate and cannot self-approve — identical to the ADR-0036 OB-1 acceptance test, exercised against the A2A surface specifically.
- **SC-002** — A test proves a goal proposal submitted via A2A lands only as a board-intake artifact (e.g., a queue/backlog entry) and never flips an `approval`/gate-status field; only an explicit Founder action can move it forward.
- **SC-003** — A check proves the A2A endpoint resolves to an in-tenant-only address (TN-1); a config pointing at an external/hosted relay or registry fails this check, and exposing the endpoint beyond that requires a logged Founder act in `board/.events.jsonl`.
- **SC-004** — A negative test proves a call that skips the ADR-0009 admission layer is denied, and a redaction probe proves any transcript crossing the A2A boundary is ADR-0012 classified and redacted — no A2A-specific bypass of the existing edge.
- **SC-005** — With the feature flag OFF (default), a wave's dispatch/board behavior is byte-identical to pre-merge; `diagnostics.py` 100/100, `board_lint`/`check_spec_consistency`/`check_dependency_graph` all green, no `project:` field on any A2A ticket (board_lint R9), committed wave attestation for every merged A2A PR.
