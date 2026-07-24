---
id: DAS-1574
title: WS-D Development — admit promptfoo, AgentShield, and Presidio through the ADR-0033 governed MCP edge
status: todo
assignee: backend-eng-1
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-005, FR-006]
labels: [security]
zone: tools/mcp_bridges
depends_on: [DAS-1572, DAS-1547]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-D, part 2).** Admit the
eval/guardrail tool shortlist — **promptfoo, AgentShield, Presidio** — per the
DAS-1572 design, reusing the ADR-0033 edge WS-A built rather than opening a
second admission path.

**Cross-workstream dependency:** this ticket needs the ADR-0033 edge mechanism
to already exist — the FastMCP sidecar convention, the compiled
`board/.tool-allowlist.json`, and the `PreToolUse` audit/deny hook — all built
in **DAS-1547** (WS-A Development). It does NOT need WS-A's browser tool
(DAS-1548) or WS-A's epic to be fully closed; only the tool-bridge sidecar
mechanism.

- **FR-005:** each of the three tools enters as an out-of-process MCP sidecar
  under `tools/`, wired in `.mcp.json`, reachable only through a role's overlay
  allow-list (least privilege — no blanket grants); every call passes the
  existing `PreToolUse` audit/deny path.
- **FR-006:** publishing/enabling is bounded by the same fail-closed defaults
  as the base 0033 edge — no WS-D-specific bypass, no global grant, no new
  admission surface.
- Do not fork `audit_external_tool.py`, the allow-list compiler, or
  `egress_guard.py` — import/reuse them (ADR-0029 extend-vs-new), matching how
  DAS-1548 reused DAS-1547's egress guard.
- Feature-gated by `ws_d_langfuse_lens` OR the shared `ws_a_tool_bridge` key
  per the DAS-1572 design's decision on which flag governs admission of these
  three tools; record the choice in the log.

## Acceptance criteria
- [ ] promptfoo, AgentShield, and Presidio each exposed as a governed MCP sidecar under `tools/`, wired in `.mcp.json`.
- [ ] Each reachable only via an explicit overlay allow-list entry; a role without the entry is refused (no blanket/global grant).
- [ ] Every call passes the existing `PreToolUse` audit/deny + ADR-0012 redaction path, reused (not reimplemented) from DAS-1547.
- [ ] Feature-flagged OFF by default; flag-off dispatch unchanged. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Development, part 2). Admits promptfoo,
AgentShield, Presidio through the existing ADR-0033 edge. Depends on DAS-1572
(this workstream's design) AND DAS-1547 (the WS-A ticket that built the 0033
edge mechanism being reused) — the concrete instance of the master-prompt's
"D runs parallel from A, needs the 0033 edge" sequencing note. Distinct repo
zone from DAS-1573 (tools/mcp_bridges vs tools/observability) so the two
Development tickets can proceed without a same-zone wave collision.
