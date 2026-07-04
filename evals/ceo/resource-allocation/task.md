# Golden task — ceo — resource-allocation

**Role:** `ceo`
**Kind:** deterministic

## Prompt

`fixtures/budget_requests.json` lists this quarter's cross-org budget
requests and the total capital available. Perform the CEO's cross-org
resource-allocation duty: allocate `total_cap_usd` across departments using
this concrete waterfall rule:

1. Sort departments by `priority_tier` ascending (tier `1` is highest
   priority).
2. Walk the tiers in order. Within a tier, if the **remaining cap** is
   enough to fully fund every request in that tier, fund each dept's full
   `requested_usd`.
3. If the remaining cap is **not** enough to fully fund a tier, split the
   remaining cap across that tier's depts **proportionally** to their
   `requested_usd` (i.e. `dept_share = remaining_cap * requested_usd /
   sum(requested_usd for the tier)`), and every lower-priority tier then
   receives **`0`**.
4. Never allocate more than `total_cap_usd` in total.

## Input

- `fixtures/budget_requests.json` — `{"total_cap_usd": number, "requests":
  [{"dept": str, "requested_usd": number, "priority_tier": int}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "allocations": { "<dept>": number, ... } }
```

One entry per `dept` in the fixture (numeric USD amount, may be `0`).

## Scoring (deterministic, fractional credit)

The expected allocation is derived by `verify.py` by re-applying the
waterfall rule above to the fixture — it is never spelled out numerically in
this prompt. Credit is `1 - normalized L1 error`:

```
credit = clamp01( 1 - sum(|reported[dept] - expected[dept]|) / sum(expected.values()) )
```

A blank submission (`allocations: {}` or omitted, i.e. every dept implicitly
`0`) scores `0.0`.
