# Golden task — cdo — contrast-gate

**Role:** `cdo`
**Kind:** deterministic

## Prompt

Per `design/CLAUDE.md` §Authority, CDO can "block any release that violates
accessibility baseline (WCAG AA)". `fixtures/pairs.json` lists text/background
colour pairs proposed for the checkout flow, each with its pre-measured
contrast ratio and text size.

Using the WCAG 2.1 **Level AA** thresholds — **4.5:1** for normal text and
**3.0:1** for large text (≥18pt / ≥14pt bold) — identify exactly the pairs
that **FAIL** the AA bar and must be blocked before release.

## Input

- `fixtures/pairs.json` — `{"pairs": [{"name": str, "fg": str, "bg": str, "ratio": float, "text_size": "normal"|"large"}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "failing": ["<pair name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely failing pairs:

```
credit = clamp01( (|reported ∩ failing| - |reported \ failing|) / |failing| )
```

A blank submission (`failing: []` or omitted) scores `0.0`. The failing set is
derived by applying the AA thresholds to the ratios/sizes inside `verify.py`;
the thresholds themselves are never spelled out as a lookup table in
`fixtures/` — applying the AA rule correctly is the graded skill.
