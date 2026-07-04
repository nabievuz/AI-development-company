# Golden task — cmo — cac-underperformer-flagging

**Role:** `cmo`
**Kind:** deterministic

## Prompt

`fixtures/channels.json` lists this quarter's acquisition channels with their
`spend` (USD) and `conversions` (count), plus a company-wide `target_cac`
(maximum acceptable customer-acquisition cost, USD).

For each channel, compute its actual CAC as `spend / conversions`. A channel is
**underperforming** — a candidate to cut or de-fund next quarter — when its
actual CAC is **strictly greater than** `target_cac`. A channel at or below
`target_cac` is healthy; do not flag it.

Report the `name`s of every underperforming channel.

## Input

- `fixtures/channels.json` — `{"target_cac": <num>, "channels": [{"name": str, "spend": num, "conversions": num}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "underperforming_channels": ["<channel name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-underperforming channels:

```
credit = clamp01( (|reported ∩ underperforming| - |reported \ underperforming|) / |underperforming| )
```

A blank submission scores `0.0`. The underperforming set is computed directly
from the CAC arithmetic in `fixtures/channels.json` inside `verify.py` — it is
never spelled out in the prompt.
