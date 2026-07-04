# Golden task — product-designer — ux-flow-deadends

**Role:** `product-designer`
**Kind:** deterministic

## Prompt

`fixtures/flow.json` describes the screen graph of the **checkout** flow: each
screen lists its outgoing `transitions` (the other screens a user can reach from
it) and whether it is a `terminal` screen (an intentional end state, e.g. an
order-confirmation screen).

Identify every **UX dead-end**: a *non-terminal* screen with **no outgoing
transitions at all** — a user who lands there cannot continue forward, go back,
or reach any other screen in the flow. Terminal screens are the deliberate exit
of the flow and must NOT be reported as dead-ends, even though they also have no
outgoing transitions.

## Input

- `fixtures/flow.json` — `{"screens": [{"name": str, "transitions": [str, ...], "terminal": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "dead_ends": ["<screen name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuine dead-ends:

```
credit = clamp01( (|reported ∩ dead_ends| - |reported \ dead_ends|) / |dead_ends| )
```

A blank submission (`dead_ends: []` or omitted) scores `0.0`. The dead-end set is
derived from the flow graph inside `verify.py`; it is never spelled out in the
prompt.
