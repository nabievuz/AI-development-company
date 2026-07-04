# Golden task — frontend-eng-1 — render-precedence

**Role:** `frontend-eng-1`
**Kind:** deterministic

## Prompt

`fixtures/component_spec.json` defines the `DataView` component's conditional
render priority — the ORDER in which state flags are checked (a common source
of frontend bugs: checking `items.length === 0` before `loading`, for
example, flashes an empty state during a fetch).

`fixtures/scenarios.json` lists 5 state combinations (`a`..`e`), each with
`error`, `loading`, and `items`. For each scenario, determine which view
actually renders once the priority order is applied correctly.

## Input

- `fixtures/component_spec.json` — the render-priority rules, checked in
  the listed order; the first matching rule wins.
- `fixtures/scenarios.json` — 5 scenarios, each with an `id` and the
  `error` / `loading` / `items` state.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "render": { "a": "<ViewName>", "b": "<ViewName>", "c": "<ViewName>", "d": "<ViewName>", "e": "<ViewName>" }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct / total_scenarios` (5). The resolved view per scenario is
  the graded knowledge — it lives in `verify.py`, not the fixture.

A blank submission scores `0.0`.
