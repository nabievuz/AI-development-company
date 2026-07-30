---
id: DAS-1644
title: Decide where the infra-MCP carve-out lives; an ambient env var must not redraw it
status: todo
assignee: security-lead
author: cto
dept: engineering
priority: p1
parent:
goal: mustaqil-ws-a-reach
spec: 002-mustaqil-ws-a-reach
implements: [FR-002]
labels: [security]
zone: tools/mcp_bridges
depends_on: []
created: 2026-07-30
updated: 2026-07-30
---

## Description

**The last member of the ambient-config defect class, and the one that could not be
closed mechanically with the other six.** `DAS-1644` is the residual routed out of the
2026-07-30 remediation that removed every environment override from the engine's
feature-flag readers (`scripts/rbac.py`, `tools/mcp_bridges/audit_external_tool.py`,
`tools/model_gateway/flag.py`, `tools/a2a/endpoint.py` + `scripts/a2a_intake/intake.py`,
`tools/guardrails/chain.py`, `tools/control_plane/app.py`, `tools/sandbox/flag.py`).

`tools/mcp_bridges/audit_external_tool.py:52`:

```python
_DEFAULT_INFRA_MCP = "mcp__ArcRift,mcp__obsidian"

def _infra_servers() -> frozenset[str]:
    raw = os.environ.get("DASLAB_INFRA_MCP", _DEFAULT_INFRA_MCP)
    return frozenset(s.strip() for s in raw.split(",") if s.strip())
```

That set names the MCP servers WS-A does **not** govern. The carve-out itself is
legitimate and load-bearing: the Persistent Memory Law (CLAUDE.md) mandates an ArcRift
call from EVERY agent, so governing ArcRift under the allow-list would deny every role's
mandatory memory path and break the org. The problem is **who may redraw the set, and
from where** — today an ambient environment variable can, in the live `PreToolUse` hook
that `.claude/settings.json` spawns with the operator's inherited environment.

**It REPLACES the list rather than extending it, so the hazard runs both ways.** Verified
against the real hook and the committed `board/.tool-allowlist.json`:

```
default (no env)                     infra=['mcp__ArcRift', 'mcp__obsidian']
    mcp__playwright__browser_navigate  -> deny
    mcp__ArcRift__store_memory         -> allow

DASLAB_INFRA_MCP=mcp__playwright     infra=['mcp__playwright']
    mcp__playwright__browser_navigate  -> allow   <- ungoverned: FR-002 least privilege gone
    mcp__ArcRift__store_memory         -> deny    <- Persistent Memory Law path denied
```

So one shell variable both **widens** the exemption to an arbitrary server (the opposite
direction from the flag overrides just removed — those made governance inert, this one
carves a hole in it while leaving the edge apparently live and auditing) and **drops**
the servers the carve-out exists to protect.

**Why this was deliberately NOT swept up with the other six.** Unlike a binary flag, the
carve-out is a *list* that legitimately has to be configurable somewhere, and it has a
sanctioned consumer contract: `tests/test_ws_a_tool_bridge.py:213
test_infra_mcp_carveout_is_env_overridable` asserts the override is intentional
("`DASLAB_INFRA_MCP` scopes the carve-out; a server outside it stays governed"). Removing
the variable without deciding where the list moves would either delete a real test or
hardcode a security-relevant set in code with no SSOT and no drift check. That decision
is this ticket.

**The decision to make.** Today the set is a comma-joined string literal in the module —
it is the only part of the WS-A governance surface with no tracked artifact behind it,
while its sibling (the grant map) is a generate-and-diff artifact,
`board/.tool-allowlist.json`, compiled from the overlay SSOT by
`scripts/gen_subagents.py` and drift-checked by
`tests/test_ws_d_tool_admission.py::test_compiled_allowlist_matches_overlays_no_drift`.
Candidate shapes, cheapest first:

1. **Compile it like the allow-list** — declare the infra servers in the same SSOT the
   grants come from and emit them into the tracked compiled artifact, so the carve-out
   is reviewable in a diff and guarded by the existing no-drift test. Strongest, and it
   reuses machinery rather than inventing any.
2. **A tracked config key** (e.g. in `config/`), read the way the flag readers now read
   `config/features.yaml`: file-only, path anchored to the module (LAW A).
3. **Keep an env seam but make it fail-closed and additive** — it may only ever ADD to
   the default set, never remove from it, so ArcRift/obsidian can never be un-carved and
   an ambient value cannot silence the memory path. This still permits widening, so it is
   the weakest of the three and needs an explicit argument if chosen.

Whichever wins, the Founder-facing question is the same: *is redrawing the governed/
ungoverned boundary an operator act or a reviewed, tracked change?* Every other WS-A
governance input is now the latter.

**Scope note.** `tests/conftest.py` (2026-07-30) scrubs `DASLAB_INFRA_MCP` from the pytest
environment, so the test suite is already insulated from an ambient value. That is
containment for tests only — production behaviour is unchanged and is what this ticket
addresses.

⛔ Do NOT let any outcome deny `mcp__ArcRift` (Persistent Memory Law — CLAUDE.md).
⛔ Do NOT reintroduce an environment override for the hook's `ws_a_tool_bridge` FLAG; that
was removed as a zero-trace bypass and is a separate, closed decision.
⛔ Do NOT add a `--features`-style CLI seam for the carve-out without checking
`.claude/settings.json` — the deployed `PreToolUse` command passes no arguments, and a
test asserts it stays that way.
⛔ Do NOT silently delete `test_infra_mcp_carveout_is_env_overridable`; invert or rewrite
it to the chosen contract so the name-space keeps its coverage.

## Acceptance criteria
- [ ] The infra-MCP carve-out has a single tracked source of truth; the boundary between governed and ungoverned MCP servers is reviewable in a diff, not settable from a shell.
- [ ] An ambient `DASLAB_INFRA_MCP` cannot un-carve `mcp__ArcRift` / `mcp__obsidian` (the Persistent Memory Law path is never denied by an environment value).
- [ ] An ambient value cannot exempt a server the SSOT does not exempt — a governed server stays governed and audited (FR-002 / TB-2 least privilege).
- [ ] A test reproduces the two-directional harm above and fails against the current code (mutation-proved, not merely asserted); `test_infra_mcp_carveout_is_env_overridable` is inverted or rewritten, not dropped.
- [ ] If the carve-out becomes a compiled artifact, a no-drift test guards it the way `test_compiled_allowlist_matches_overlays_no_drift` guards the grant map.
- [ ] `docs/runbooks/ws-a-tool-bridge.md` documents the chosen source; no doc sanctions an ambient override.
- [ ] `diagnostics.py` 100/100; full suite green; `board_lint`/validators green; `scripts/ws_a_health_check.py` HEALTHY; no `project:` field (R9).

## Log
### 2026-07-30 — CTO
Filed out of the ambient-config remediation (commits `aaec13f`, `8db2962`, `7f4c539`,
`322702d`, `d7e3654`). Those closed every feature-flag reader — the census
`grep -rn 'os.environ.get("DASLAB_WS_|DASLAB_A2A_OUTBOUND_FLAG|DASLAB_FEATURES'` over
`scripts/ tools/ daslab_sdk/` now returns nothing. `DASLAB_INFRA_MCP` was held back
deliberately: it is a list with a sanctioned purpose and an existing test asserting the
override, so it needs a decision about where the SSOT lives rather than a mechanical
removal. Raised to `p1` / `todo` rather than `backlog` because the variable is read by the
LIVE `PreToolUse` hook and the widening direction is exploitable today with no flag flip;
assigned to the Security Lead since the outcome redraws a governance boundary, not just a
config path.
