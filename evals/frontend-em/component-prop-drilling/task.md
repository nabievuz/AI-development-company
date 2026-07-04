# Golden task — frontend-em — component-prop-drilling

**Role:** `frontend-em`
**Kind:** deterministic

## Prompt

You are doing a frontend team technical review of the component prop-flow
report in `fixtures/components.json`. Each entry records, for one component,
the prop it receives, how many intermediate component layers that prop is
threaded ("drilled") through before it's consumed (`prop_drill_depth`), and
whether the component already short-circuits that flow via context/composition
(`uses_context`).

Flag every component that has a **prop-drilling architecture problem**: the
prop is drilled through **3 or more** intermediate layers (`prop_drill_depth
>= 3`) **and** the component does **not** already use context/composition
(`uses_context == false`) to avoid it. A component that uses context is
considered already remediated regardless of depth; a component with shallow
drilling (`< 3`) is not worth flagging.

## Input

- `fixtures/components.json` — `{"components": [{"name": str, "prop_name": str, "prop_drill_depth": int, "uses_context": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "flagged": ["<component name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-flaggable components:

```
credit = clamp01( (|reported ∩ flaggable| - |reported \ flaggable|) / |flaggable| )
```

A blank submission (`flagged: []` or omitted) scores `0.0`. The flaggable set is
derived from the report inside `verify.py`; the exact answer is never spelled
out in the prompt.
