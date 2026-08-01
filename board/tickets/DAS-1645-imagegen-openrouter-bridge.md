---
id: DAS-1645
title: Admit image generation (OpenRouter) through the ADR-0033 edge, scoped to design roles
status: in_review
assignee: security-lead
author: cto
dept: engineering
priority: p1
labels: [governance, security]
zone: tools/mcp_bridges
created: 2026-08-01
updated: 2026-08-01
---

## Description

Founder-directed: a DasLab agent should be able to generate imagery with a
Nano-Banana-class model, connected via OpenRouter. This admits that capability as
`mcp__imagegen` through the **existing** ADR-0033 edge — no second admission path,
no direct SDK call from an agent-run script (ADR-0010 C1).

**Two firsts for this org, which is why this is `security-lead` review and not an
auto-approved config bump:**

1. **First sidecar carrying a production credential.** Every bridge before this one
   is deny-all and credential-free. `OPENROUTER_API_KEY` is read from the
   environment, never accepted as a tool argument, never echoed into a transcript.
2. **First non-Anthropic model anywhere in the org.** The Model Allocation Law is
   untouched — it governs which Claude model an *agent runs on*; this is a *tool an
   agent calls*. The new policy states the boundary explicitly: an agent may never
   be backed by a non-Anthropic model, only tools may call one.

**Prompt egress is a disclosure, not a fetch.** `web_fetch` reads; this tool SENDS
caller-authored text to a third party, irreversibly. The sidecar therefore REFUSES a
prompt tripping the ADR-0012 §2 secret/PII shapes rather than scrubbing it — a
scrubbed prompt renders the wrong image while teaching the caller nothing.

Scope is deliberately narrow: three design roles (`product-designer`, `design-lead`,
`cdo`), one host (`openrouter.ai`), a model set pinned in the sidecar so an agent
cannot select an arbitrary or arbitrarily expensive model.

### Surfaces changed

| Surface | Change |
| --- | --- |
| `tools/mcp_bridges/imagegen_tool_bridge.py` | new FastMCP sidecar |
| `.mcp.json` | `imagegen` server |
| `config/egress-allowlist.yaml` | new `imagegen-openrouter` profile → `openrouter.ai` only |
| `design/agents/{product-designer,design-lead,cdo}/AGENTS.md` | `## External tools` grants |
| `governance/policies/third-party-model-tools.md` | new binding policy |
| `board/.tool-allowlist.json` | recompiled by `scripts/gen_subagents.py` |

### Reviewer: the finding that needs your call

**Per-role egress injection is not implemented in this repo.** Overlays declare
`egress_profile:`, but nothing sets `DASLAB_EGRESS_PROFILE` at sidecar launch from
the invoking role — it appears only in tests. Every profile shipped before this one
is deny-all, so the gap has been inert and unnoticed.

`imagegen-openrouter` is the first non-empty profile, so it is pinned in `.mcp.json`
and is therefore **server-scoped, not role-scoped**. Role granularity still holds via
the TB-2 PreToolUse allow-list (fail-closed, explicit roles, no wildcards — verified),
but the egress layer is host-scoped only. Documented as open follow-up in the policy
§5a, with the interim rule: treat overlay `egress_profile:` as declared intent, not an
enforced control, and never widen a non-empty profile onto a server with a broader
grant list.

Decide whether that is acceptable as shipped, or whether per-role injection must land
before the grant goes live.

### Also open

Cost metering is not wired: `mcp__imagegen` bills per call and does not yet appear in
`config/budgets.yaml` / the `scripts/check_cost.py` path. That is the stated reason the
grant stays at three roles.

⛔ Do NOT widen `imagegen-openrouter` in place for a new role — a new need gets a NEW
reviewed profile (the allow-list's own rule). Do NOT hand-edit
`board/.tool-allowlist.json`; re-run `scripts/gen_subagents.py` (C1). Do NOT move the
credential out of the environment into config or a tool argument.

## Acceptance criteria
- [x] Sidecar admitted through the existing ADR-0033 edge; no second admission path.
- [x] Egress gated by `check_egress` before any network syscall; no-redirect opener (C4).
- [x] Grant compiles to exactly `[cdo, design-lead, product-designer]`; no wildcard role (C2).
- [x] Prompt carrying ADR-0012 §2 secret/PII shapes is refused, not scrubbed.
- [x] Tool returns a repo-relative file path, never base64 in the transcript.
- [x] `out_path` contained under the generated-media root; absolute paths and `..` refused.
- [x] Model set pinned in the sidecar; an unlisted model is refused.
- [x] Missing credential and provider errors return a clean `error:` string, never a traceback.
- [x] Binding policy landed covering disclosure, provenance, cost and provider terms.
- [x] `check_agents_sync` green; `board_lint`/validators green; no `project:` field (R9).
- [ ] **Reviewer decision** on server-scoped vs role-scoped egress (see above).
- [ ] Cost metering wired into `config/budgets.yaml` before the grant widens beyond design.

## Log
### 2026-08-01 — CTO
Implemented and verified without network: egress allows `openrouter.ai` only with the
profile, denies with an empty profile, denies `notopenrouter.ai` (C6 label boundary, no
substring bypass); prompt refusal fires on email / phone / OpenRouter key shapes and
passes ordinary prompts; path traversal, absolute paths and wrong extensions refused;
missing key and unlisted model return clean errors. `gen_subagents.py` recompiled the
allow-list to exactly the three declared roles; ungranted roles deny fail-closed.
`check_agents_sync` OK (32 shims); configs parse.

Filed `in_review` to `security-lead` rather than `done`: the egress surface and the
first production credential are that role's call, and the per-role-injection finding
above is a real architectural gap that a reviewer — not the author — should accept or
reject.
