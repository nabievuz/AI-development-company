# ADR 0033 — Ecosystem-tool MCP bridge: external tools (browser, LangChain catalog) enter only through the governed MCP edge

- **Status:** Accepted (Backend EM authors; **CTO ratified — RACI 3.1/3.6 A — 2026-07-24**; Security Lead consulted — tool admission + redaction)
- **Date:** 2026-07-22
- **Scope:** Platform / org-engine — the tool-reach admission contract
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — ADR 0012 redaction, secrets policy)
- **Relates:** direction brief `docs/research/2026-07-22-daslab-devin-langchain-direction.md` and parity brief `docs/research/2026-07-22-daslab-vs-autonomous-coding-agents-parity.md`; builds on [0009](0009-harness-owns-transport-admission-layer.md) (admission, not transport), [0012](0012-dgox-event-store-content-classification-redaction-policy.md) (tool-event redaction), [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) §5 (C1–C6)
- **Supersedes / Amends:** nothing — establishes the inbound tool bridge fresh; additive to `.mcp.json`.

> DasLab's parity gap G2 (browser / computer-use) and G3 (external tool reach) are what make the autonomous coding platforms *feel* autonomous. This ADR fixes **how** external tools enter DasLab so that reach goes **up** without governance going **down**. It ships no tool — it fixes the contract the tool-bridge tickets build against.

## Context

DasLab agents reach tools three ways today: Claude Code built-ins (`Read`/`Bash`/`WebFetch`/…), the `Agent` subagent tool, and MCP servers wired in `.mcp.json` (`ArcRift`, `obsidian`). To operate like Jules/Devin/Factory the org needs a **browser / computer-use** capability and access to the broad third-party integration catalog (search, retrievers, trackers, SaaS APIs). The tempting shortcuts — bolt a browser into an agent, hand every role a blanket web tool — are exactly what turns a governed org into an ungoverned one: a tool with no allow-list, no audit, and no redaction is a policy hole (LAW 8 admission, ADR 0012 redaction, C4 gate order).

MCP is already DasLab's tool lingua franca. The decision is therefore not *whether* to add tools but *through which governed edge*.

## Decision

**Every external tool enters DasLab as an out-of-process MCP server wired in `.mcp.json`, governed at the MCP edge — never as an in-agent capability or a global grant.** Binding invariants:

### TB-1 — External tools are out-of-process MCP sidecars
A browser/computer-use tool and any LangChain-catalog capability are exposed by a small MCP server (e.g. a FastMCP sidecar under `tools/`), the same shape as `ArcRift`. The engine stays server-free (`check_no_dead_runtime` holds); the sidecar is optional infra, not core runtime, and its absence means the tool simply does not exist.

### TB-2 — Least privilege: a tool reaches a role only via its overlay allow-list
No blanket tool grants. A role uses an external tool only if its `<dept>/agents/<role>/AGENTS.md` overlay (compiled per ADR 0018/0029) allow-lists it. The browser reaches, e.g., the QA/Design roles that need visual verification — not every IC by default.

### TB-3 — Every external-tool call is audited and redactable
A `PreToolUse` hook (filesystem `.claude/settings.json`, honored identically by the Claude Code CLI and the Agent SDK, ADR 0034) may audit or **deny** each external-tool call; tool transcripts are events classified and redacted under ADR 0012. An external tool never writes routing fields (C3) and never bypasses an AADL gate (C4).

### TB-4 — Browser/computer-use is high-blast-radius and gated accordingly
The browser is the marquee tool but the widest attack surface (prompt-injection via fetched content — cf. the documented Jules exfiltration findings). It is admitted only behind TB-2 + TB-3, and under autonomous waves it additionally sits inside the HEARTBEAT SI-1…SI-7 envelope (ADR 0027). Two distinct controls apply: **(a) ingress** — fetched content is treated as untrusted input that can never change the agent's goal, approvals, or permissions (prompt-injection defense); **(b) egress** — outbound network access is **deny-all except an explicit domain allow-list** (Founder answer Q5), so the tool can reach only pre-approved destinations. It never runs against production credentials it was not explicitly scoped.

### TB-5 — Off by default; additive; no dispatch change on merge
The bridge is feature-flagged (ADR 0019 family, default OFF). Adding a sidecar to `.mcp.json` changes no dispatch behaviour; a wave with the flag off behaves exactly as today.

## Consequences

**Positive:** DasLab gains Devin-like reach (browser + hundreds of integrations) while every tool call stays allow-listed, audited, redacted, and gate-bounded. Because tools are MCP, the tool layer is model-agnostic even though the org is Claude-native. The bridge is reversible (delete the `.mcp.json` entry).

**Negative / accepted:** More sidecar surface to run and secure; the browser is a genuine new attack surface (mitigated by TB-4 and treating tool output as untrusted). Accepted — the alternative (no reach) forfeits the parity goal.

**Law check:** **C1/C2** (tools are substrate; the board and governance stay canonical). **LAW 8 / ADR 0009** (the MCP edge is an admission layer, not a transport proxy). **ADR 0012** (tool events classified + redacted). **AADL / C4** (a tool never dispatches past an open gate). **Model allocation** (unaffected — tools are model-independent). **Project placement** (the bridge lives under `tools/`, a platform path; it hosts no project content — C6).

## Enforcement / acceptance

- **Ratified by the CTO on 2026-07-24** (RACI 3.1/3.6 A); Security Lead consulted on tool admission + ADR 0012 redaction + secrets. Judged sound against ADR 0009 (the MCP edge is an admission layer, not a transport proxy), ADR 0012 (tool events classified + redacted), C1/C2 (tools are substrate; board + governance stay canonical), and Founder answer Q5 (deny-all + explicit domain allow-list egress — now bound explicitly in TB-4 and traced by SPEC-002 FR-005). Status moves `Proposed` → `Accepted` on this sign-off.
- A tool-bridge PR is reviewed against TB-1…TB-5; a PR that grants a tool globally (TB-2), skips the `PreToolUse` audit/redaction (TB-3), or exposes an unscoped browser (TB-4) is rejected.
- The feature key lands in `config/features.yaml` `DEFAULTS` **OFF** (ADR 0019); the `.mcp.json` entry and the sidecar land under `tools/`.
- Any future "how may an external tool enter DasLab?" question resolves to this ADR.
