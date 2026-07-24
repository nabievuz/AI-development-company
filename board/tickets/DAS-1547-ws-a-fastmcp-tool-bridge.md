---
id: DAS-1547
title: WS-A Development — FastMCP tool-bridge sidecar under tools, fold in the spike, flag OFF
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1544
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-001, FR-002, FR-003, FR-004]
labels: [security]
zone: tools/mcp_bridges
depends_on: [DAS-1546]
created: 2026-07-23
updated: 2026-07-23
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-A, part 1).** Build the governed
tool-bridge MCP sidecar per the DAS-1546 design.

- **TB-1:** an out-of-process FastMCP sidecar under `tools/` (same shape as `ArcRift`),
  wired in `.mcp.json`; the engine stays server-free (`check_no_dead_runtime` holds);
  absence of the sidecar means the tool does not exist.
- **Fold in the on-branch spikes** — `tools/mcp_bridges/langchain_tool_bridge.py`,
  `tools/mcp_bridges/audit_external_tool.py`, `tools/mcp_bridges/mcp.snippet.json`,
  `requirements-tools.txt` — harden to the design; do not rewrite from scratch.
- **TB-2/TB-3:** enforce the overlay allow-list and the `PreToolUse` audit/deny path;
  emit tool transcripts as ADR-0012-redactable events.
- **TB-5/FR-004:** guarded by the WS-A feature flag (OFF); with the flag OFF the
  sidecar is inert and dispatch is unchanged.

## Acceptance criteria
- [ ] FastMCP sidecar under `tools/mcp_bridges/` wired in `.mcp.json`; `check_no_dead_runtime` / `diagnostics.py` still 100/100.
- [ ] On-branch spike files folded in and passing (not left untracked); allow-list + PreToolUse audit/deny enforced per design.
- [ ] Tool-event redaction path present (ADR-0012); tool never writes routing fields (C3) / never bypasses a gate (C4).
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge. Merged PR, green CI.

## Log
### 2026-07-23 — CEO
Created by /daslab-plan (WS-A Development, part 1). TB-1/TB-2/TB-3; folds in the branch spike.
