# Third-party model tools — binding policy

**Status:** active · Founder-authorized 2026-08-01
**Scope:** any DasLab tool that sends data to a model provider other than Anthropic.
**First instance:** `mcp__imagegen` (image generation via OpenRouter).

## 1. What this policy is not

It does **not** amend the [Model Allocation Law](model-allocation.md). That law
governs which **Claude model an agent runs on**. This policy governs **tools an
agent calls**. An agent's own reasoning stays on Claude; a third-party model may
only ever sit behind a tool boundary.

An agent may never be *backed* by a non-Anthropic model. Only tools may call one.

## 2. Admission

A third-party model tool enters through the existing ADR-0033 edge and nothing
else — no second admission path, no direct SDK call from a script an agent runs
(ADR-0010 C1):

1. A FastMCP sidecar in `tools/mcp_bridges/`, registered in `.mcp.json`.
2. A grant declared in each role's overlay `## External tools` block, compiled
   by `scripts/gen_subagents.py` into `board/.tool-allowlist.json`. Roles are
   explicit — never `*`.
3. A **dedicated** egress profile in `config/egress-allowlist.yaml` naming the
   provider host and nothing else. Editing that file is `security_sensitive` +
   `governance_or_policy`, never `approval: auto*` (QONUN-5), and the profile is
   never widened in place.

## 3. Disclosure — the rule that makes these tools different

Every earlier sidecar either reads (`web_fetch`) or works on text handed to it
locally. A model tool **sends caller-authored content to a third party**. That
is a disclosure event, and it is irreversible.

- **Refuse, do not scrub.** A prompt tripping the ADR-0012 §2 secret/PII shapes
  is refused with an explanation. Silently scrubbing produces a wrong result
  from a mangled prompt while still teaching the caller nothing.
- **Never send customer data, board contents, `.env` values, or anything
  classified above public** under `config/data_classification.yaml`.
- **Credentials come from the environment**, never from a tool argument, and are
  never echoed into a transcript.
- **Bulk output stays out of transcripts.** A tool returns a file path; tool
  transcripts are redact-then-truncate'd and are the wrong place for payloads.

## 4. Provenance — no representational claims

Generated media may illustrate. It may **not** stand in as evidence about a real
subject.

Concretely: a generated image must not be presented as a photograph of a real
asset, place, person, document or event. On a page that makes factual claims —
an offer, a valuation, a due-diligence pack — generated imagery belongs in
ambient/context slots, never next to a figure a reader would take it as
evidence for.

Where a generated asset ships, the repository records that it is generated
(a generator script, a README note, or both) so a later reader cannot mistake
its provenance.

Provider watermarking (e.g. Google SynthID in Gemini image output) is a
detection aid, not a substitute for this rule, and must not be stripped.

## 5. Cost

Model tools are metered per call and bill to a real account, unlike every
in-process sidecar before them.

- Default to the cheap tier for drafts; the quality tier is for assets that ship.
- The reviewed model set is pinned **in the sidecar**, not passed freely by the
  caller — an agent cannot select an arbitrary (or arbitrarily expensive) model.
- Spend belongs in `config/budgets.yaml` and the `scripts/check_cost.py` path
  like any other cost line.

**Open, and a hard gate (Security Lead, 2026-08-04).** Metering for
`mcp__imagegen` is not wired. `config/budgets.yaml` prices Claude tiers per
million tokens; a per-call third-party line has no home there yet, and nothing in
the repo rate-limits calls, caps calls per wave, or ceilings spend. The current
bound is therefore *social* (three design roles drafting assets), not mechanical:
a retry loop bills a real account and no repo control stops it. The residual is
accepted at three roles only because the blast radius is small and the provider
account carries its own credit ceiling.

**Until metering lands, the grant does not widen beyond `cdo`, `design-lead` and
`product-designer` — for any role, for any reason.** A widening request is
blocked on the metering work, not merely accompanied by it.

## 5a. Server-scoped egress — reviewed decision (Security Lead, 2026-08-04)

Overlays declare `egress_profile:` per role, but nothing injects
`DASLAB_EGRESS_PROFILE` at sidecar launch from the invoking role — today it is
set only in tests and in the server's own `.mcp.json` `env` block. Every profile
shipped before `imagegen-openrouter` was deny-all, so the gap was inert.
`mcp__imagegen` is the first non-empty profile, so it is pinned per-server and
applies to **any caller of that server**.

**Decision: accepted for `mcp__imagegen` as currently shaped. Per-role injection
is NOT required before this grant goes live.**

The exposure a server-scoped profile creates is that any caller of the server
inherits the profile's network reach. Its severity depends entirely on whether a
caller can *steer* that reach. In this sidecar it cannot: the destination is a
module-level constant (`_ENDPOINT`), and `generate_image`'s parameters are
exactly `(prompt, out_path, model, aspect_ratio)` — no URL, host, path or
base-url argument, and nothing derived from caller input reaches the opener. The
profile grants one host; the code grants one URL on that host, with redirects
refused (C4) so the target cannot be bounced after the gate runs. A caller of
this server therefore has precisely the reach the intended caller has.

Per-role injection would also be a **no-op here**: ungranted roles never reach
the module at all (the TB-2 PreToolUse hook denies before execution, fail-closed,
no default-allow, wildcards rejected), and all three granted roles declare the
identical profile string. The control would add no reduction in reach.

**Bound — what voids this acceptance.** It is scoped to this sidecar in this
shape. Per-role injection, or an equivalent control, must land BEFORE any of:

- **(a)** the outbound destination stops being a compile-time constant — i.e. any
  caller-supplied value can influence the request target;
- **(b)** a role is granted `mcp__imagegen` whose declared `egress_profile`
  differs from `imagegen-openrouter`;
- **(c)** `imagegen-openrouter` gains a second host, or is attached to a second
  server;
- **(d)** a non-empty profile ships on a server whose destinations ARE
  caller-steerable — `web_fetch` is the standing example, where the URL is a tool
  argument and a server-scoped non-empty profile would let any caller steer
  anywhere inside the profile. **That case gets its own review and does not
  inherit this acceptance.**

Condition (a) is machine-enforced: `tests/test_imagegen_tool_bridge.py::
test_the_key_is_never_accepted_as_a_tool_argument` pins the parameter set, so
adding a URL argument turns the suite red.

Outside those bounds the earlier rule stands: treat overlay `egress_profile:` as
**declared intent, not an enforced control**, and never widen a non-empty profile
onto a server with a broader grant list.

## 6. Provider terms

Before a provider is admitted, confirm on the account actually in use: that
commercial use of the output is permitted, what the provider retains and whether
it trains on submitted content, and what the output-ownership terms are. Record
the answer with the egress-profile change. Re-confirm when the plan changes.

## 7. Review

The grant list, the egress profile and the model set are reviewed whenever a new
role requests access — that request is a new reviewed change, not an edit to an
existing profile.
