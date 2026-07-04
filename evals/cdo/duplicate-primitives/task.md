# Golden task — cdo — duplicate-primitives

**Role:** `cdo`
**Kind:** deterministic

## Prompt

Per `design/CLAUDE.md` §Success Metrics, the design system must cover ≥90% of
UI primitives — which fails when the same UI purpose is re-implemented as
multiple, divergent components instead of one shared primitive.
`fixtures/component_manifest.json` lists every component currently registered
in the core UI kit, each tagged with the UI **purpose** it serves.

Identify exactly the component **names** that belong to a purpose served by
**more than one** component — these are the consolidation candidates that
should be merged into a single design-system primitive.

## Input

- `fixtures/component_manifest.json` — `{"components": [{"name": str, "purpose": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "duplicates": ["<component name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely duplicated components:

```
credit = clamp01( (|reported ∩ duplicates| - |reported \ duplicates|) / |duplicates| )
```

A blank submission (`duplicates: []` or omitted) scores `0.0`. The duplicate
set is derived by grouping the manifest by `purpose` inside `verify.py`; it is
never spelled out in the prompt.
