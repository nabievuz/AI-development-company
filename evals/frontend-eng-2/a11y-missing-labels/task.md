# Golden task — frontend-eng-2 — a11y-missing-labels

**Role:** `frontend-eng-2`
**Kind:** deterministic

## Prompt

`fixtures/form.html` is a form snippet under review before ship. Some of its
interactive/informational elements have no accessible name (no associated
`<label>`, `aria-label`, `aria-labelledby`, or — for images — `alt`). List the
**element `id`s** that fail this accessible-name requirement.

A `placeholder` attribute does NOT count as an accessible name (it is not
announced consistently by assistive tech and disappears on input). An `alt=""`
would mark an image as intentionally decorative (not present in this fixture).

## Input

- `fixtures/form.html` — the form markup, every checkable element carries an
  `id`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "violations": ["<element id>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuine violations:

```
credit = clamp01( (|reported ∩ violations| - |reported \ violations|) / |violations| )
```

A blank submission (`violations: []` or omitted) scores `0.0`. The violation
set is derived by parsing the actual fixture markup inside `verify.py`; it is
never spelled out in the prompt.
