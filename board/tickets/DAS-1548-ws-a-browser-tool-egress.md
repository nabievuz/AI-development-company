---
id: DAS-1548
title: WS-A Development — browser tool behind admission, deny-all plus domain allow-list egress
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-005, FR-006]
labels: [security]
zone: tools/browser
depends_on: [DAS-1546]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-A, part 2).** Add the marquee
browser / computer-use tool (Playwright-MCP or browser-use) as a governed sidecar.

- **TB-4:** admitted ONLY behind the DAS-1547 allow-list (TB-2) + PreToolUse
  audit/redaction (TB-3); never runs against production credentials it was not
  explicitly scoped.
- **Q5 egress:** deny-all except an explicit domain allow-list; no unattended browsing.
- **FR-006 injection defense:** fetched page content is untrusted DATA — it can never
  change the agent's goal, approvals, or permissions; under autonomous waves the
  browser additionally sits inside the HEARTBEAT SI-1…SI-7 envelope (ADR-0027).
- Feature-flagged OFF (own key or the shared WS-A key per the DAS-1543 scaffold).

Distinct repo zone from DAS-1547 so the two Development tickets can proceed without a
same-zone wave collision.

## Acceptance criteria
- [ ] Browser/computer-use tool exposed as a governed MCP sidecar, admitted only behind TB-2+TB-3.
- [ ] Egress deny-all with an explicit domain allow-list; a non-allow-listed domain is refused.
- [ ] Fetched content handled as untrusted input (documented + enforced at the tool boundary); no production-credential access unless explicitly scoped.
- [ ] Feature-flagged OFF; flag-off dispatch unchanged. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Development, part 2). TB-4 + Q5 egress + FR-006 injection defense.
