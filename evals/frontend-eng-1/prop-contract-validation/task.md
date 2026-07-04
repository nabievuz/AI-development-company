# Golden task — frontend-eng-1 — prop-contract-validation

**Role:** `frontend-eng-1`
**Kind:** deterministic

## Prompt

`fixtures/component_contract.json` describes the prop contract for the
`SubmitButton` component (required props, optional props, and their types).
`fixtures/call_sites.json` lists 5 call sites (`a`..`e`) that render
`SubmitButton` with a given set of props.

For each call site, decide whether the props passed satisfy the component's
contract (`"valid"`) or violate it (`"invalid"`) — e.g. a missing required
prop, a prop of the wrong type, or an unknown prop not declared in the
contract.

## Input

- `fixtures/component_contract.json` — the prop contract (required/optional, types).
- `fixtures/call_sites.json` — 5 call sites, each with an `id` and a `props` object.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "verdicts": { "a": "<valid|invalid>", "b": "<valid|invalid>", "c": "<valid|invalid>", "d": "<valid|invalid>", "e": "<valid|invalid>" }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correct / total_call_sites` (5). The contract-violation logic
  (which props are missing/mistyped/unknown) is the graded knowledge — it
  lives in `verify.py`, not the fixture.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
