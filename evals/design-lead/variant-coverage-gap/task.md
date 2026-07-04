# Golden task — design-lead — variant-coverage-gap

**Role:** `design-lead`
**Kind:** deterministic
**Competency:** design-system governance — catching screen usages that draw on
component variants the design system does not define.

## Prompt

`fixtures/design-system.json` is the design system's registry of defined
component variants. `fixtures/screen-usage.json` lists every
component/variant usage on the `billing-settings` screen. As design-system
governance owner, identify exactly the usages whose `component:variant` is
**not** defined in the design system (an undefined variant, or a component the
design system doesn't define at all).

## Input

- `fixtures/design-system.json` — `{"components": {<name>: [<variant>, ...]}}`.
- `fixtures/screen-usage.json` — `{"usages": [{"component": str, "variant": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "undefined": ["<component>:<variant>", ...] }
```

## Scoring (deterministic, fractional credit)

The verifier derives the true undefined set by diffing screen usage against
the design-system registry. Credit rewards true positives and penalises false
positives, normalised by the number of genuine gaps:

```
credit = clamp01( (|reported ∩ undefined| - |reported \ undefined|) / |undefined| )
```

A blank submission (`undefined: []` or omitted) scores `0.0`. The undefined
set is never spelled out in the prompt — only the raw registry and usage list
are given; the diff is computed inside `verify.py`.
