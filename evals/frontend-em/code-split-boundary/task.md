# Golden task — frontend-em — code-split-boundary

**Role:** `frontend-em`
**Kind:** deterministic

## Prompt

You are making a UI architecture decision: which routes in
`fixtures/routes.json` should be moved behind a lazy-loaded code-split
boundary. Each entry gives a route's current initial bundle contribution in KB
(`initial_bundle_kb`) and whether it sits on the app's critical render path
(`is_critical_path`) — the first screen(s) users must see before anything else
is usable.

A route needs a code-split boundary when its `initial_bundle_kb` **exceeds
150 KB** **and** it is **not** on the critical path (critical-path routes stay
eagerly bundled by design, however large, since splitting them would only add
a loading flash to the very first paint). A route under the 150 KB threshold
is not worth the added chunk-loading overhead.

## Input

- `fixtures/routes.json` — `{"routes": [{"name": str, "initial_bundle_kb": int, "is_critical_path": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "code_split": ["<route name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-splittable routes:

```
credit = clamp01( (|reported ∩ splittable| - |reported \ splittable|) / |splittable| )
```

A blank submission (`code_split: []` or omitted) scores `0.0`. The splittable
set is derived from the report inside `verify.py`; the exact answer is never
spelled out in the prompt.
