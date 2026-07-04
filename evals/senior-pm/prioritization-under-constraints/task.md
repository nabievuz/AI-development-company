# Golden task — senior-pm — prioritization-under-constraints

**Role:** `senior-pm`
**Competency:** prioritization under constraints (choosing the highest-value
backlog slice that fits a fixed capacity and respects dependencies)
**Kind:** deterministic

## Prompt

`fixtures/backlog.json` lists six candidate backlog items competing for the
next planning cycle, each with an estimated effort in engineer-weeks, a
relative value score, and (for some items) a dependency on another item
being shipped in the same cycle. The team's total capacity for the cycle is
`capacity_weeks` (also in the fixture).

Select the subset of items that:
1. fits within `capacity_weeks` (sum of `effort_weeks` for selected items),
2. never selects an item without also selecting everything it `depends_on`,
3. maximizes total `value`.

## Input

- `fixtures/backlog.json` — `{"capacity_weeks": int, "items": [{"id", "name", "effort_weeks", "value", "depends_on": [id, ...]}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "selected": ["<item id>", ...] }
```

## Scoring (deterministic, fractional credit)

`verify.py` first checks the submission is **feasible** — within capacity and
with every dependency satisfied. An infeasible submission scores `0.0`.
A feasible submission is scored against the true optimum (computed directly
from the fixture inside `verify.py`, not shown here):

```
credit = clamp01( value(selected) / value(optimal) )
```

An empty or missing `selected` list is feasible (value 0) and scores `0.0`.
