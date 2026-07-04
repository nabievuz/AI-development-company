# Golden task — qa-lead — test-strategy-gap

**Role:** `qa-lead`
**Kind:** deterministic

## Prompt

`fixtures/feature.json` describes an upcoming feature, its risk level, and the
test types already planned for it. As QA Lead you own test-strategy sign-off:
name exactly the test types that are **missing** given the feature's risk
level — higher risk demands broader coverage (defense in depth), not just more
unit tests.

## Input

- `fixtures/feature.json` — `feature` (str), `risk_level` (`low` | `medium` |
  `high`), `existing_test_plan` (list of test types already planned).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "missing_test_types": ["<test type>", ...] }
```

## Scoring (deterministic, fractional credit)

```
credit = clamp01( (|reported ∩ missing| - |reported \ missing|) / |missing| )
```

The required test-type set per risk level (and thus the missing set) is
derived inside `verify.py` — never spelled out here. A blank submission
scores `0.0`.
