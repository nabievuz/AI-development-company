# Golden task — cpo — roadmap-prioritization-rice

**Role:** `cpo`
**Kind:** deterministic

## Prompt

You are planning next quarter's roadmap. `fixtures/features.json` lists candidate
features with the inputs needed for a RICE score (`reach`, `impact`,
`confidence`, `effort_weeks`) and the engineering team's total capacity for the
quarter (`capacity_weeks`).

RICE score = `(reach * impact * confidence) / effort_weeks`.

Choose the subset of features to commit to this quarter that **maximizes total
RICE value while staying within `capacity_weeks`** (sum of `effort_weeks` of
chosen features must not exceed capacity). This is the prioritization
trade-off a CPO owns: not every high-value feature fits, so the selection —
not just the scoring — is the judgment being tested.

## Input

- `fixtures/features.json` — `{"capacity_weeks": int, "features": [{"name": str, "reach": int, "impact": number, "confidence": number, "effort_weeks": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "selected": ["<feature name>", ...] }
```

`selected` is the set of features committed for the quarter (order does not
matter).

## Scoring (deterministic, fractional credit)

`verify.py` computes the RICE score for every feature and finds the
capacity-feasible subset with the maximum total RICE score (brute-force over
all subsets — small `n`). Let `optimal_value` be that maximum.

- If the submission's total `effort_weeks` exceeds `capacity_weeks`, the plan
  is infeasible and credit is `0.0`.
- Otherwise, `achieved_value` = sum of RICE scores of the submitted features,
  and `credit = clamp01(achieved_value / optimal_value)`.

A blank submission (`selected: []` or omitted) scores `0.0`. The optimal
subset is never spelled out in the prompt or fixtures — only in `verify.py`.
