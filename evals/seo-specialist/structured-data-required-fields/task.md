# Golden task — seo-specialist — structured-data-required-fields

**Role:** `seo-specialist`
**Kind:** deterministic

## Prompt

`fixtures/product.jsonld.json` is a `schema.org/Product` JSON-LD block pulled
from a live product page. Google's structured-data rich-result eligibility
requires these fields to be present AND non-empty:

- top level: `name`, `image`, `description`, `sku`
- inside `offers`: `price`, `priceCurrency`

Audit the block and report which of those required fields are **missing or
present-but-empty** (an empty string counts as invalid). Reference a
nested `offers` field as `offers.<field>` (e.g. `offers.priceCurrency`).

## Input

- `fixtures/product.jsonld.json` — the JSON-LD `Product` object.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "invalid_fields": ["<field name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-invalid fields:

```
credit = clamp01( (|reported ∩ invalid| - |reported \ invalid|) / |invalid| )
```

A blank submission scores `0.0`. The invalid-field set is computed directly
from `fixtures/product.jsonld.json` inside `verify.py` — it is never spelled
out in the prompt.
