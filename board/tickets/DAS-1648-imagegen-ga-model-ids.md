---
id: DAS-1648
title: Verify the GA OpenRouter image-model ids against a live account and swap off -preview
status: todo
assignee: backend-eng-1
author: security-lead
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [governance]
zone: tools/mcp_bridges
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Routed out of DAS-1645, where the reviewer deliberately left it unsettled rather
than guessing.** `tools/mcp_bridges/imagegen_tool_bridge.py` pins:

```python
_ALLOWED_MODELS = {
    "google/gemini-3-pro-image-preview",
    "google/gemini-2.5-flash-image",
}
```

A `-preview` id can be retired by the provider without notice. The reviewer kept it
anyway, on the grounds that pinning an *unverified* GA id converts every call into a
provider error immediately, whereas preview retirement fails **closed** — a refused
call, never a wrong image. Guessing trades a certain failure for a possible one.

Closing it therefore requires a **live account**, not a code edit: the GA ids must be
read from the real OpenRouter catalogue and confirmed to work before they are pinned.

## Acceptance criteria
- [ ] GA ids read from the live OpenRouter catalogue, with the date and the catalogue
      response recorded — not inferred from the `-preview` string by dropping a suffix.
- [ ] Each candidate GA id proven to return an image end to end before it is pinned.
- [ ] `_ALLOWED_MODELS` updated only for ids that passed that proof; any id that could
      not be verified stays `-preview` with the reason recorded.
- [ ] The credential is read from the environment in-process — never passed on a
      command line (visible in the process list), never echoed, never committed.
- [ ] `tests/test_imagegen_tool_bridge.py` still green (its
      `test_every_reviewed_model_is_accepted` asserts against `_ALLOWED_MODELS`, so the
      reviewed set and the tests move together by construction).
- [ ] Routed back to `security-lead` for review — the model set is part of the
      reviewed surface DAS-1645 signed off, so it does not change unreviewed.
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green; no flag flipped; no
      `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the explicit routing request in `security-lead`'s DAS-1645 sign-off report.
Priority `p2`, not `p1`: the current pin fails closed, so this is durability work
rather than an open risk. Needs a live credential, so it cannot be completed in a
sandbox without one — expect it to park if the key is absent.
