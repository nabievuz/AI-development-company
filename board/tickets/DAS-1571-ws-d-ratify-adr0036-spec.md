---
id: DAS-1571
title: WS-D Planning — ratify ADR-0036, review SPEC-005, confirm the WS-D feature key OFF
status: todo
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-001, FR-004, FR-006]
labels: [governance, security]
zone: docs/adr
depends_on: [DAS-1543]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 1 — Planning (closes GATE-1 for WS-D).**

- Ratify **ADR-0036** (currently `Proposed`) → `Accepted` after CTO sign-off
  (RACI 3.1/3.6); Security Lead consulted on the OTLP export redaction (OB-3);
  CMO consulted on distribution (OB-4). Confirm the ADR's stance that the
  self-host Langfuse lens is NOT LangSmith / NOT a hosted endpoint, and that
  the tool-admission shortlist (promptfoo, AgentShield, Presidio) rides the
  ADR-0033 edge rather than opening a second admission path.
- Review `docs/specs/005-mustaqil-ws-d-lens/SPEC.md` (FR-001…FR-006,
  SC-001…SC-005); resolve any `[NEEDS CLARIFICATION]`; mark SPEC Status
  `reviewed`.
- Confirm the `ws_d_langfuse_lens` feature key in `config/features.yaml`
  DEFAULT **OFF** (already landed by DAS-1543) — the flag that guards the
  OTLP exporter (FR-004).

No exporter and no tool wiring is built in this stage — this fixes the
contract the WS-D code builds against.

## Acceptance criteria
- [ ] ADR-0036 Status flipped to `Accepted` with the CTO sign-off recorded; `docs/adr/README.md` consistent.
- [ ] SPEC-005 reviewed (Status `reviewed`), no unresolved clarification markers.
- [ ] `ws_d_langfuse_lens` feature key confirmed present in `config/features.yaml`, value `false`, with its consumer/flip comment (from DAS-1543 — not re-added).
- [ ] `check_spec_consistency`/`check_links`/`board_lint` green.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Planning). Ratifies ADR-0036; reviews SPEC-005;
confirms the pre-landed `ws_d_langfuse_lens` OFF scaffold.
