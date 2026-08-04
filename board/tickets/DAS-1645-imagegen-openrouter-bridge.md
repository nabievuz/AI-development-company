---
id: DAS-1645
title: Admit image generation (OpenRouter) through the ADR-0033 edge, scoped to design roles
status: in_review
assignee: ceo
author: cto
dept: engineering
priority: p1
labels: [governance, security]
zone: tools/mcp_bridges
created: 2026-08-01
updated: 2026-08-04
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
- [x] **Reviewer decision** on server-scoped vs role-scoped egress — ACCEPTED as
      shipped, bounded; reasoning and the four voiding conditions recorded in
      policy §5a and in the 2026-08-04 log entry below.
- [x] Cost metering — adjudicated: NOT wired, and NOT accepted. Converted from a
      note into a hard gate: the grant does not widen beyond the three design
      roles until metering lands (policy §5). Wiring routed as follow-up.

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

### 2026-08-02 — platform unification (worktree merge)
Renumbered `DAS-1644` → **DAS-1645**. The id collided with
`DAS-1644-infra-mcp-carveout-ssot` (created 2026-07-30, the earlier claim, which
keeps the number); both branches had allocated the next free id off the same base
and git merged them without a conflict because only the filenames differ. New
`board_lint` R14 now fails on a duplicate id, so the next one cannot reach a clean
board.

Added `tests/test_imagegen_tool_bridge.py` (53 cases, no network, no key). The
2026-08-01 entry above verified these invariants **by hand**; nothing pinned them,
which made this the only bridge in `tools/mcp_bridges/` without a regression test —
and the only one carrying a production credential. Now covered: prompt refusal on
each ADR-0012 §2 shape (and that the refusal never echoes the secret it refused),
out-path containment, the pinned model set (including the env override path), the
credential travelling as a header and never reaching the transcript on any path,
the egress gate running pre-flight against the pinned endpoint, redirect refusal,
never-raises on malformed/oversized/text-only provider answers, and mime retarget.
Mutation-checked: disabling the prompt filter, the containment check, the egress
gate, the model allow-list, or the redirect refusal each turns the suite red.

Status stays `in_review` — the two open reviewer decisions (server-scoped vs
role-scoped egress, cost metering) are unchanged and remain `security-lead`'s call.

### 2026-08-04 — Security Lead
Security sign-off. Reviewed the sidecar, the egress guard, the TB-2 hook, the
compiled allow-list, the three overlays, the policy and the 53-case suite.

**1. Server-scoped egress — ACCEPTED, bounded. Per-role injection is NOT required
before this grant goes live.**

The exposure a server-scoped profile creates is that any caller of the server
inherits its reach; the severity turns on whether a caller can *steer* that reach.
Here it cannot. `_ENDPOINT` is a module constant, `generate_image`'s parameters
are exactly `(prompt, out_path, model, aspect_ratio)`, and nothing derived from
caller input reaches the opener — so the profile grants one host and the code
grants one URL on it, with redirects refused (C4) so the target cannot be bounced
after the gate. A caller of this server has precisely the intended caller's reach.

Per-role injection would additionally be a **no-op here**: ungranted roles never
reach the module (TB-2 denies pre-execution), and all three granted roles declare
the identical profile string. Requiring it first would be ceremony, not risk
reduction. I verified the enforcement layer rather than taking it on trust —
`ws_a_tool_bridge: true`, the PreToolUse hook wired in `.claude/settings.json`
with `DASLAB_TOOL_ALLOWLIST`, `decide()` with no default-allow, wildcards rejected
at both load and decide, unidentified caller fail-closed (exit 2), grants compiled
to exactly `[cdo, design-lead, product-designer]`. It also bit me live: my own
`mcp__ccd_session__mark_chapter` call was denied mid-review with
`[WS-A governance] ... not allow-listed (TB-2: no default-allow)`.

Also confirmed `DASLAB_EGRESS_PROFILE` is set inside the imagegen server's own
`env` block in `.mcp.json`, so it does not widen any other bridge's profile.

**Bound — the acceptance is void, and per-role injection (or equivalent) must land
first, if:** (a) the destination stops being a compile-time constant, i.e. caller
input can influence the request target; (b) a role is granted `mcp__imagegen` with
a different declared `egress_profile`; (c) `imagegen-openrouter` gains a second
host or a second server; (d) a non-empty profile ships on a server whose
destinations ARE caller-steerable — `web_fetch` is the standing example, where the
URL is a tool argument and this reasoning inverts. **(d) gets its own review and
does not inherit this acceptance.**

Condition (a) was relying on nobody noticing. `test_the_key_is_never_accepted_as_a_
tool_argument` pins the parameter set, so a URL argument turns the suite red — but
it was written for the credential invariant, and a future author could have
"relaxed" it as a test fix and silently voided this acceptance with no signal. Its
second load-bearing role is now documented in the test itself. That comment is the
only code change in this review.

**2. Cost metering — NOT accepted; upgraded from a note to a hard gate.**

Security posture does not depend on it, so it does not block the current grant,
but the framing was too soft. `config/budgets.yaml` prices Claude tiers per
million tokens and has no home for a per-call third-party line; nothing in the
repo rate-limits calls, caps calls per wave, or ceilings spend. The bound today is
social (three roles), not mechanical — a retry loop bills a real account and no
repo control stops it. Accepted at three roles only because the blast radius is
small and the provider account carries its own credit ceiling. Policy §5 now reads
that the grant **does not widen for any role, for any reason** until metering
lands — blocked on that work, not merely accompanied by it. Wiring routed below.

**3. `-preview` vs GA model ids — deliberately NOT settled. Keep `-preview` as
shipped.** I will not swap ids I cannot verify: pinning a GA id that does not
resolve on the account in use converts every call into a provider error, trading a
working tool for a broken one on an assumption. And the pinned set is a reviewed
surface (policy §7), not a config bump. Leaving `-preview` is not free either —
providers retire preview ids on short notice — but that failure mode is safe (the
tool errors closed, it does not mis-egress). Routed as follow-up: verify against
the live account, then swap as a reviewed change.

Gates: full suite 2754 passed / 4 skipped; imagegen 53/53; `board_lint` 202
tickets, 0 violations; `diagnostics.py` 100/100. (Note for whoever runs this
worktree: it has no `.venv`, so a bare `diagnostics.py` scores 85/100 on
`ruff-clean` "ruff unavailable" — a missing-toolchain artifact, not a regression.
With the main checkout's venv on `PATH` it is 100/100.) No feature flag touched,
no egress profile widened, no grant changed.

Routing: `in_review` → `ceo`, to land this review record (policy §5/§5a, the test
comment, this log) on `main`. Not `cto`: the author IS my manager, so the standard
reviewer map would produce a self-review — `board_lint` rejects
`assignee == author` on `in_review`, and ROUTING.md's rule for that case is to
escalate one level (CTO → CEO). The security sign-off itself is granted and is
NOT contingent on that merge; what remains is landing the record, not re-deciding
it. Branch `feat/das-1645-imagegen-security-review`.

Two follow-ups for the orchestrator to route as new tickets (out of scope here —
this dispatch was adjudication, not implementation): **(1)** wire `mcp__imagegen`
cost metering into `config/budgets.yaml` + `scripts/check_cost.py` — blocks any
widening of the grant; **(2)** verify the GA image-model ids against the live
OpenRouter account and swap `-preview` as a reviewed change to the pinned set.
