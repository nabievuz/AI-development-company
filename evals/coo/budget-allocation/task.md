# Golden task — coo — budget-allocation

**Role:** `coo`
**Kind:** deterministic

## Prompt

`fixtures/budget_requests.json` lists this quarter's operations budget
requests (NOT listed in priority order — sort them yourself) plus the fixed
total operations budget cap. As COO you own the resource/budget trade-off
decision across the ops departments (Support, Finance, Legal, Facilities,
Vendor Tools). Decide which department requests get **fully funded** this
quarter, using the standard operations allocation rule:

> Sort requests by `priority_score` descending. Walk the sorted list once,
> keeping a running remaining-budget total (starting at the fixture's
> `total_budget_usd`). For each request, in order: if its `amount_usd` is
> **less than or equal to** the remaining budget, fully fund it and deduct
> its `amount_usd` from the remaining budget; otherwise **skip it** (do not
> partially fund it) and continue to the next request. Ties in
> `priority_score` break by the order the requests appear in the fixture.

## Input

- `fixtures/budget_requests.json` — `{"total_budget_usd": int, "requests": [{"dept": str, "amount_usd": int, "priority_score": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "funded_depts": ["<dept name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by
the number of genuinely-funded departments:

```
credit = clamp01( (|reported ∩ funded| - |reported \ funded|) / |funded| )
```

A blank submission (`funded_depts: []` or omitted) scores `0.0`. The funded
set is computed by applying the allocation rule to the fixture inside
`verify.py`; the resulting set is never spelled out in the prompt.
