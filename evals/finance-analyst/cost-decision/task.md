# Golden task — finance-analyst — cost-decision

**Role:** `finance-analyst`
**Kind:** deterministic

## Prompt

`fixtures/vendor_options.json` describes a build-vs-buy decision over a fixed
horizon. `build` has an upfront cost plus a flat monthly maintenance cost;
`buy` has a flat monthly subscription cost (no upfront cost). Determine:

1. **Which option is cheaper** over the full `horizon_months`.
2. **The breakeven month** — the first month `m` (1-indexed) at which
   cumulative build cost drops to or below cumulative buy cost, i.e. the
   month `build` becomes the cheaper cumulative option going forward.

## Input

- `fixtures/vendor_options.json` — `{"build": {"upfront_cost_usd": number,
  "monthly_maintenance_usd": number}, "buy": {"monthly_subscription_usd":
  number}, "horizon_months": number}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "cheaper_option": "build" | "buy", "breakeven_month": <integer or null> }
```

`breakeven_month` is `null` only if the options never cross within the given
horizon.

## Scoring (deterministic, fractional credit)

```
credit = 0.5 * (1.0 if cheaper_option is correct else 0.0)
       + 0.5 * clamp01(1 - |breakeven_month - expected_breakeven_month| / 6)
```

A missing/non-integer `breakeven_month` is treated as maximally wrong (0.0 for
that half). Both expected values are derived from the same fixture inside
`verify.py` — never spelled out in the prompt. A blank submission scores
`0.0`.
