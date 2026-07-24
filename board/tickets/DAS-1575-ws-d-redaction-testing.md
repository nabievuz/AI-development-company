---
id: DAS-1575
title: WS-D Testing — redaction-on-export verified, tool-admission negative tests, in-tenant target proven
status: todo
assignee: qa-eng
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [SC-001, SC-002, SC-003, SC-004]
labels: [security]
zone: tests
depends_on: [DAS-1573, DAS-1574]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-D).** Prove the export path and
the tool-admission reuse both hold under adversarial negative tests. Security
Engineer (red team) consulted, mirroring the WS-A GATE-4 pattern.

Cover:
- **SC-002 — redaction-on-export verified:** a planted secret/PII/tool-transcript
  fixture in a span must NOT survive in the exported OTLP payload; the
  redaction pass runs before any network call, matching the ADR-0012
  redact-then-truncate ordering.
- **SC-004 — in-tenant target proven:** the exporter target check BLOCKS a
  config pointing at a hosted Langfuse Cloud / LangSmith URL and PASSES only
  an in-tenant/self-host endpoint.
- **SC-003 — tool-admission negative tests:** a role NOT allow-listing
  promptfoo/AgentShield/Presidio is refused each tool; a call that skips the
  `PreToolUse` audit on any of the three is denied — identical guarantee to
  the base 0033 edge, no WS-D-specific bypass.
- **SC-001 — flag-off guard:** with `ws_d_langfuse_lens` OFF, no export occurs
  and event emission is byte-identical to pre-merge.
- Fold in and extend the exporter/tool-admission test suites from DAS-1573/1574.

## Acceptance criteria
- [ ] Negative tests exist and PASS in CI for SC-002 (redaction probe) and SC-004 (in-tenant-only target check).
- [ ] Negative tests exist and PASS in CI for SC-003 (non-allow-listed refusal + audit-skip denial for all three tools).
- [ ] Flag-off no-op behaviour asserted (SC-001).
- [ ] Security Engineer red-team review recorded. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Testing). Redaction-on-export probe, in-tenant
target check, tool-admission negative tests, flag-off guard. Red team
consulted.
