# Golden task — design-lead — spacing-grid-audit

**Role:** `design-lead`
**Kind:** deterministic
**Competency:** design-quality gating — enforcing the design system's spacing
grid before a component ships.

## Prompt

`fixtures/spacing-spec.json` lists the spacing tokens used by the
`settings-panel` component, plus the design system's base grid unit
(`grid_base_px`). As the design-quality gate, identify exactly the tokens
whose pixel value is **not** a multiple of the base grid unit — the tokens
that violate the spacing grid and must be flagged before ship.

## Input

- `fixtures/spacing-spec.json` — `{"grid_base_px": int, "spacing": [{"token": str, "px": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "violations": ["<token>", ...] }
```

## Scoring (deterministic, fractional credit)

The verifier derives the true violating set from `px % grid_base_px != 0`.
Credit rewards true positives and penalises false positives, normalised by the
number of genuine violations:

```
credit = clamp01( (|reported ∩ violations| - |reported \ violations|) / |violations| )
```

A blank submission (`violations: []` or omitted) scores `0.0`. The violating
set is never spelled out in the prompt — only the raw spec and grid unit are
given; the gate rule is applied inside `verify.py`.
