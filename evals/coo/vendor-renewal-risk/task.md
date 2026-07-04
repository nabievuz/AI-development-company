# Golden task — coo — vendor-renewal-risk

**Role:** `coo`
**Kind:** deterministic

## Prompt

`fixtures/vendors.json` is this quarter's vendor register. As COO you own
vendor relationships and contract renewal decisions (`operations/CLAUDE.md`
Authority: "Approve vendor contracts"). Flag exactly the vendors that are at
**renewal risk** this quarter, using the standard operations vendor-risk
criteria:

> A vendor is at renewal risk if it has had **2 or more SLA breaches**
> year-to-date, **or** its annual cost has increased **20% or more**
> year-over-year (`cost_change_pct >= 20`). Either condition alone is enough.

## Input

- `fixtures/vendors.json` — `{"vendors": [{"name": str, "annual_cost_usd": int, "cost_change_pct": number, "sla_breaches_ytd": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "flagged_vendors": ["<vendor name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely at-risk vendors:

```
credit = clamp01( (|reported ∩ at_risk| - |reported \ at_risk|) / |at_risk| )
```

A blank submission (`flagged_vendors: []` or omitted) scores `0.0`. The
at-risk set is computed from the fixture inside `verify.py`; it is never
spelled out in the prompt.
