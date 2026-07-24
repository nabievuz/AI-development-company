# SPEC 002 — MUSTAQIL WS-A REACH (governed browser + tool reach)

- **Goal:** mustaqil-ws-a-reach
- **Owner:** backend-em
- **Status:** reviewed

> WHAT/WHY only. The HOW (FastMCP sidecar, Playwright-MCP/browser-use, `.mcp.json`
> wiring, PreToolUse hook mechanics) lives in ADR-0033 and the AADL Stage-2 design
> ticket, not here. Binds to ADR-0033 (TB-1…TB-5), the direction brief
> (`docs/research/2026-07-22-daslab-devin-langchain-direction.md` §3), and Founder
> discovery answer Q5 (deny-all + allow-list egress).

## User Scenarios

- **P1 —** Given a role whose overlay allow-lists an external tool, when that role runs a wave, then it can call the tool through the governed MCP edge and every call is audited and redactable — with no change to any role that was NOT granted the tool.
- **P1 —** Given a role that does NOT allow-list an external tool, when it attempts to call it, then the call is refused (least privilege — no blanket grants).
- **P1 —** Given the tool-bridge feature flag is OFF (default), when a wave runs, then dispatch behaves exactly as today — the tool simply does not exist.
- **P2 —** Given a granted browser tool, when it navigates the web, then egress is denied to any domain outside the explicit allow-list, and fetched content is treated as untrusted data that can never change the agent's goal, approvals, or permissions.
- **P2 —** Given any external-tool call, when its transcript becomes an event, then it is classified and redacted under ADR-0012 before storage/export.

## Functional Requirements

- **FR-001** — External tools MUST enter DasLab only as out-of-process MCP servers wired in `.mcp.json` (FastMCP sidecar under `tools/`), never as an in-agent capability or global grant (ADR-0033 TB-1). The engine stays server-free (`check_no_dead_runtime` holds); the sidecar's absence means the tool does not exist.
- **FR-002** — A role MUST reach an external tool only when its `<dept>/agents/<role>/AGENTS.md` overlay allow-lists it (least privilege — TB-2). No blanket tool grants.
- **FR-003** — Every external-tool call MUST pass a `PreToolUse` audit hook that may deny it, and every tool transcript MUST be classified + redacted under ADR-0012 (TB-3). An external tool MUST NOT write routing fields (C3) or bypass an AADL gate (C4).
- **FR-004** — The bridge MUST be feature-flagged in `config/features.yaml` DEFAULTS **OFF** (ADR-0019); adding a sidecar MUST change no dispatch behaviour on merge (TB-5). Rollback = delete the `.mcp.json` entry.
- **FR-005** — A browser / computer-use tool MUST be admitted only behind the least-privilege allow-list and the PreToolUse audit/redaction path, with egress **deny-all except an explicit domain allow-list** (Q5), and MUST NOT run against production credentials it was not explicitly scoped (TB-4).
- **FR-006** — Browser egress content MUST be treated as untrusted input (prompt-injection defense): a fetched page can never change the agent's goal, approvals, or permissions.

## Success Criteria

- **SC-001** — A negative test proves a globally-granted tool (no overlay allow-list) is refused, and a call that skips the `PreToolUse` audit is denied.
- **SC-002** — A negative test proves browser egress to a non-allow-listed domain is blocked, and a tool-event redaction probe passes.
- **SC-003** — With the feature flag OFF, a wave's dispatch behaviour is byte-identical to pre-merge; flipping it ON exposes the tool only to allow-listed roles.
- **SC-004** — `diagnostics.py` 100/100, `board_lint`/validators green, green CI on every WS-A PR, no `project:` field on any WS-A ticket (board_lint R9), committed attestation for the wave.
