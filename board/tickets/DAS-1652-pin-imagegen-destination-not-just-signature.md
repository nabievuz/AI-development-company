---
id: DAS-1652
title: §5a claims condition (a) is machine-enforced, but only the signature is pinned — pin the destination
status: todo
assignee: security-eng
author: ceo
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [governance, security]
zone: tests
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Routed by the CEO at DAS-1645 closure, and confirmed independently by the orchestrator
with one route the CEO did not name — which is the worst of them.**

`governance/policies/third-party-model-tools.md:131` states:

> Condition (a) is machine-enforced: `tests/test_imagegen_tool_bridge.py::...`

Condition (a) is the first voiding condition of the DAS-1645 egress risk acceptance:
*the destination becomes caller-influenced*. The whole acceptance of server-scoped
egress rests on it — per-role `DASLAB_EGRESS_PROFILE` injection was declined **because**
a caller cannot steer the target.

The named test, `test_the_key_is_never_accepted_as_a_tool_argument`, asserts
`generate_image`'s exact parameter set. That is real enforcement of one route: adding a
`url` / `host` / `base_url` argument turns the suite red, and the docstring comment
correctly warns a future author not to "fix" that red by relaxing it.

But condition (a) is **broader than a signature**. It trips on *any* caller-supplied
value influencing the target, and these routes leave the suite green:

1. **The egress-checked URL and the fetched URL can diverge — no test compares them.**
   `test_egress_is_checked_against_the_pinned_endpoint` asserts only what `check_egress`
   *received* (`seen == [(mod._ENDPOINT, "imagegen-openrouter")]`). Nothing asserts that
   the `urllib.request.Request` actually sent is for that same URL. Gate one URL, fetch
   another, suite stays green. This is a check-then-use gap and it is the most serious
   of the three — the CEO's report did not name it.
2. **`_ENDPOINT` ceasing to be a compile-time constant.** Line 339 asserts only
   `mod._ENDPOINT.startswith("https://openrouter.ai/")`. A computed value that still
   starts with that prefix passes.
3. **The existing `model` argument interpolated into a request path**, or a second tool
   function added to the module inheriting the server-scoped profile. Neither adds a
   parameter; neither is covered.

**Severity is genuinely low and should not be inflated:** the profile allows exactly one
host, redirects are refused (C4), and the TB-2 allow-list denies ungranted roles
pre-execution — so the blast radius of every route above stays inside `openrouter.ai`.
This is a follow-up, not a block, and DAS-1645 was correctly closed without it.

**What is actually wrong is the policy sentence, not the code.** §5a asserts machine
enforcement of a condition the machine only partly checks. A governance document that
over-claims its own enforcement is worse than one that admits a gap, because the next
reviewer trusts it.

## Acceptance criteria
- [ ] A test pins the **destination actually requested** — assert the URL on the
      `Request` object handed to the opener equals `_ENDPOINT`, closing route 1. Prove it
      by mutation: make the fetched URL differ from the checked one and confirm red.
- [ ] Routes 2 and 3 either covered or explicitly declared out of scope with reasoning —
      do not silently cover one and leave the policy claiming all three.
- [ ] §5a reworded to state precisely what the suite does and does not catch. If a route
      is left uncovered, the policy must say so.
- [ ] The `test_the_key_is_never_accepted_as_a_tool_argument` docstring updated so its
      dual-load-bearing note points at whichever test now owns condition (a).
- [ ] `tests/test_imagegen_tool_bridge.py` stays green (53+ cases); `diagnostics.py`
      100/100; `board_lint`/validators green; no flag flipped; no grant or profile
      changed; no `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the CEO's explicit routing request at DAS-1645 closure. The CEO deliberately
did not create it — three agents were running concurrently and racing for the next free
id is exactly the DAS-1644/DAS-1645 collision that already forced a renumbering (now
caught by `board_lint` R14). Correct call; the orchestrator is the single id writer.

Orchestrator verification before filing: read all four `_ENDPOINT` references in the
test file and the signature test in full. The CEO's finding holds, and route 1 above —
the checked-URL vs fetched-URL divergence — was found during that verification rather
than taken from the report.
