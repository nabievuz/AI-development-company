# Golden task — cpo — sunset-decision

**Role:** `cpo`
**Kind:** deterministic

## Prompt

`fixtures/feature_usage.json` lists shipped features with their monthly
active users (`mau`), monthly maintenance cost, and monthly revenue
attributed to the feature. Identify exactly the features that should be
**sunset** (deprecated and removed from the roadmap) this quarter, using this
rule:

> A feature is a sunset candidate when it is **both** low-adoption (`mau`
> below `mau_threshold`) **and** running a negative margin
> (`monthly_revenue_usd` < `maintenance_cost_usd`).

A feature that fails only one of the two conditions (e.g. low adoption but
still profitable, or unprofitable but broadly adopted) stays on the roadmap —
this is the trade-off judgment: adoption and margin must both fail before a
CPO recommends a cut.

## Input

- `fixtures/feature_usage.json` — `{"mau_threshold": int, "features": [{"name": str, "mau": int, "maintenance_cost_usd": int, "monthly_revenue_usd": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "sunset": ["<feature name>", ...] }
```

## Scoring (deterministic, fractional credit)

`verify.py` derives the exact sunset set from the same rule above, applied to
the fixture data. Fractional credit rewards true positives and penalizes
false positives, normalized by the number of genuinely sunset-worthy
features:

```
credit = clamp01( (|reported ∩ expected| - |reported \ expected|) / |expected| )
```

A blank submission (`sunset: []` or omitted) scores `0.0`. The expected set is
never spelled out in the prompt or fixtures — only in `verify.py`.
