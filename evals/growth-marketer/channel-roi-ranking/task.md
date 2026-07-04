# Golden task — growth-marketer — channel-roi-ranking

**Role:** `growth-marketer`
**Kind:** deterministic

## Prompt

Given the channel spend/results in `fixtures/channels.json` (each with `spend`,
`conversions`, and `revenue` for the period), compute ROAS
(`revenue / spend`) per channel and decide:

- `scale_channel` — the channel with the highest ROAS (double down budget here).
- `cut_channel` — the channel with the lowest ROAS (candidate to cut spend).

## Input

- `fixtures/channels.json` — per-channel spend, conversions, and revenue.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "scale_channel": "<channel-name>",
  "cut_channel": "<channel-name>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `scale_channel` equals the channel with the highest `revenue / spend`.
- `0.5` — `cut_channel` equals the channel with the lowest `revenue / spend`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
