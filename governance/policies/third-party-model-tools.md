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
  like any other cost line. **Open:** metering for `mcp__imagegen` is not yet
  wired; until it is, the grant is limited to the three design roles.

## 5a. Open follow-up — per-role egress injection

Overlays declare `egress_profile:` per role, but nothing yet injects
`DASLAB_EGRESS_PROFILE` at sidecar launch from the invoking role — today it is
set only in tests. Every profile shipped before `imagegen-openrouter` was
deny-all, so the gap was inert.

`mcp__imagegen` is the first non-empty profile, so it is pinned in `.mcp.json`
and applies to **any caller of that server**. Role granularity is still enforced,
by the TB-2 PreToolUse allow-list (fail-closed, explicit roles, no wildcards) —
but the egress layer is host-scoped only, not role-scoped.

Until per-role injection lands, treat the overlay `egress_profile:` field as
**declared intent, not an enforced control**, and keep non-empty profiles scoped
to a server whose full grant list is acceptable as a single unit. Widening a
non-empty profile to a server with a broader grant list is not safe under the
current wiring.

## 6. Provider terms

Before a provider is admitted, confirm on the account actually in use: that
commercial use of the output is permitted, what the provider retains and whether
it trains on submitted content, and what the output-ownership terms are. Record
the answer with the egress-profile change. Re-confirm when the plan changes.

## 7. Review

The grant list, the egress profile and the model set are reviewed whenever a new
role requests access — that request is a new reviewed change, not an edit to an
existing profile.
