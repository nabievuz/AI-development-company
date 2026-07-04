# Golden task — product-designer — design-spec-completeness

**Role:** `product-designer`
**Kind:** deterministic

## Prompt

`fixtures/component_spec.json` is a handoff spec for a component. Before it can
be handed to engineering, every DasLab component spec MUST define:

- **All required interaction states:** `default`, `hover`, `focus`, `disabled`,
  `error` (under the `states` object).
- **All required accessibility fields:** `aria_label`, `focus_visible` (under
  the `a11y` object).

Compare the spec against this checklist and list exactly what is **missing**.

## Input

- `fixtures/component_spec.json` — `{"component": str, "states": {<state>: {...}, ...}, "a11y": {<field>: ...}}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "missing": ["state:<name>" | "a11y:<name>", ...] }
```

Use the `state:` prefix for a missing interaction state and the `a11y:` prefix
for a missing accessibility field (e.g. `"state:focus"`, `"a11y:focus_visible"`).

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-missing items:

```
credit = clamp01( (|reported ∩ missing| - |reported \ missing|) / |missing| )
```

A blank submission (`missing: []` or omitted) scores `0.0`. The required
checklist is fixed above; the missing set for THIS spec is derived by
`verify.py` from the fixture, never spelled out directly in the prompt.
