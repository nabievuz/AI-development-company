---
id: DAS-1544
title: MUSTAQIL WS-A REACH — governed browser and tool reach via the MCP edge (EPIC)
status: backlog
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
labels: [security]
depends_on: [DAS-1543]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**EPIC — MUSTAQIL v3.0 WS-A REACH.** Give any DasLab agent Devin-like *hands and
eyes* — a browser / computer-use tool and the broad integration catalog — while every
tool call stays allow-listed, audited, redacted, and gate-bounded. Tool reach goes
**up** without governance going **down**.

**Contract of record:** ADR-0033 (TB-1…TB-5), `docs/specs/002-mustaqil-ws-a-reach/SPEC.md`
(FR-001…FR-006, SC-001…SC-004), direction brief §3, discovery Q5 (deny-all + allow-list).

**Extend-vs-new (do not duplicate).** Fold in the on-branch prototype spikes rather
than rebuild: `tools/mcp_bridges/langchain_tool_bridge.py`, `tools/mcp_bridges/audit_external_tool.py`,
`tests/test_ws_a_tool_bridge.py`, runbook `docs/runbooks/ws-a-tool-bridge.md`. These
are spikes ahead of formal tickets — harden and merge them; a spike is not a delivery
until it passes in CI under a merged ticket (ADR-0020).

**AADL — six-stage closure (children DAS-1545..DAS-1551):**

| Child | Stage | Ticket | Owner-hint |
|---|---|---|---|
| DAS-1545 | Planning | Ratify ADR-0033 + review SPEC-002 + land the WS-A feature key OFF | cto |
| DAS-1546 | Design | Tool-admission design — overlay allow-list (TB-2), PreToolUse audit/deny + ADR-0012 redaction (TB-3), deny-all + domain allow-list egress (TB-4/Q5) | backend-em |
| DAS-1547 | Development | FastMCP tool-bridge sidecar under tools/ (TB-1), fold in the spike, wire `.mcp.json`, flag OFF | backend-em |
| DAS-1548 | Development | Browser / computer-use tool behind TB-2+TB-3+TB-4, egress allow-list, untrusted-egress handling | backend-eng-1 |
| DAS-1549 | Testing | Negative tests — global grant refused, audit-skip denied, non-allow-listed egress blocked, redaction probe | qa-eng |
| DAS-1550 | Deployment | Runbook + flag stays OFF on merge (no dispatch change), rollback = delete `.mcp.json` entry | sre-eng |
| DAS-1551 | Maintenance | Scheduled health/eval of the tool edge (allow-list drift, redaction probe) | product-analyst |

## Acceptance criteria
- [ ] All seven children (DAS-1545..DAS-1551) closed, each through its own AADL stage gate.
- [ ] **FR-001/TB-1:** every external tool enters as an out-of-process MCP sidecar under `tools/`; the engine stays server-free (`check_no_dead_runtime` holds).
- [ ] **FR-002/TB-2:** a role reaches a tool only via its overlay allow-list; a negative test proves a non-allow-listed / global grant is refused (SC-001).
- [ ] **FR-003/TB-3:** every tool call passes a `PreToolUse` audit that can deny it; tool transcripts are ADR-0012 classified + redacted; a redaction probe passes (SC-002).
- [ ] **FR-005/TB-4 + Q5:** the browser is admitted only behind TB-2+TB-3, egress is deny-all except an explicit domain allow-list, and a negative test blocks non-allow-listed egress (SC-002).
- [ ] **FR-006:** browser egress is treated as untrusted input (injection defense) — documented and tested at the tool boundary.
- [ ] **FR-004/TB-5:** the bridge is feature-flagged OFF; with the flag OFF, dispatch is byte-identical to pre-merge (SC-003); rollback = delete the `.mcp.json` entry.
- [ ] On-branch spikes folded in and passing in CI (not left as untracked prototypes).
- [ ] `diagnostics.py` 100/100; `board_lint`/`check_spec_consistency`/validators green; no `project:` field on any WS-A ticket (R9); committed wave attestation (ADR-0031/0032).
- [ ] **Epic acceptance = AADL 6-gate closure for WS-A**, each gate logged in the stage-board.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan from the Founder-approved MUSTAQIL v3.0 queue (order 1). Contract = ADR-0033 (TB-1..TB-5) + SPEC-002. Children DAS-1545..DAS-1551 (one per AADL stage, 2 Development). Org-engine epic — no `project:` field (board_lint R9). Depends on the prep bootstrap (DAS-1543) for the feature-flag scaffold.
