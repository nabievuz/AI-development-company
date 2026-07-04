# Golden task — design-lead — contrast-audit

**Role:** `design-lead`
**Kind:** deterministic
**Competency:** design review — accessibility/contrast gating on a component's color tokens.

## Prompt

`fixtures/tokens.json` lists the foreground/background color-token pairs used
in the `checkout-summary` component. As design review, identify exactly the
pairs that **fail** WCAG 2.1 **AA** contrast for normal text (contrast ratio
`< 4.5:1`, computed via the standard relative-luminance formula).

## Input

- `fixtures/tokens.json` — `{"pairs": [{"name": str, "fg": "#hex", "bg": "#hex"}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "failing": ["<pair name>", ...] }
```

## Scoring (deterministic, fractional credit)

The verifier computes the actual WCAG contrast ratio for every pair and derives
the true failing set. Credit rewards true positives and penalises false
positives, normalised by the number of genuinely-failing pairs:

```
credit = clamp01( (|reported ∩ failing| - |reported \ failing|) / |failing| )
```

A blank submission (`failing: []` or omitted) scores `0.0`. The failing set is
never spelled out in the prompt or fixtures — it is derived only inside
`verify.py` from the raw color values.
