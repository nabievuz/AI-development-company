# Golden task — growth-marketer — experiment-prioritization

**Role:** `growth-marketer`
**Kind:** deterministic

## Prompt

Given the backlog of growth experiments in `fixtures/experiments.json` (each
scored 1-10 on `reach`, `impact`, `confidence`, and `effort`), compute the
RICE score for each experiment:

```
RICE = (reach * impact * confidence) / effort
```

Identify the experiment with the highest RICE score — the one growth should
run next — and report its score.

## Input

- `fixtures/experiments.json` — the experiment backlog.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "top_experiment": "<experiment-id>",
  "rice_score": <float>
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `top_experiment` equals the experiment with the highest RICE score.
- `0.5` — `rice_score` is within `±0.5` of that experiment's computed RICE score.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
