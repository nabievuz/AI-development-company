# Golden task — cmo — roas-budget-reallocation

**Role:** `cmo`
**Kind:** deterministic

## Prompt

`fixtures/channels.json` gives this quarter's paid channels, each with its
current `spend` (USD) and measured `roas` (return on ad spend), plus a
`total_budget` (USD) available for next quarter. Apply the standard
reallocation rule:

1. **Cut** any channel whose `roas` is **strictly less than `2.0`** — its next-
   quarter budget is `0`. (Below 2.0 the channel doesn't cover its own
   acquisition + margin cost, so it gets no further spend.)
2. **Keep** every channel with `roas >= 2.0`. Split the entire `total_budget`
   across the kept channels **proportionally to their `roas`**:
   `new_budget[channel] = total_budget * roas[channel] / sum(roas of all kept channels)`.

Recommend next quarter's budget for every channel (cut channels get `0`).

## Input

- `fixtures/channels.json` — `{"total_budget": <num>, "channels": [{"name": str, "spend": num, "roas": num}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "allocations": { "<channel name>": <num>, ... } }
```

Every channel from the fixture must have a key in `allocations`.

## Scoring (deterministic, fractional credit)

`verify.py` recomputes the correct allocation from `fixtures/channels.json`
(the same rule stated above). For each channel, the reported allocation
is counted as correct when it is within **5% of `total_budget`** of the
expected value. Credit is the fraction of channels reported correctly:

```
credit = clamp01( (# channels within tolerance) / (# channels in the fixture) )
```

An empty submission, or one missing the `allocations` object, scores `0.0`.
The exact per-channel numbers are never spelled out in the prompt — only the
reallocation rule is.
