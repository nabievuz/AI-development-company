# Golden task — seo-specialist — title-meta-length-audit

**Role:** `seo-specialist`
**Kind:** deterministic

## Prompt

`fixtures/pages.json` lists pages with their `<title>` and meta `description`
tags. Apply standard on-page SEO length guidance:

- Title tag: recommended length is **30–60 characters** (inclusive). Titles
  shorter or longer than that range risk truncation or poor keyword coverage
  in search results.
- Meta description: recommended length is **70–160 characters** (inclusive).

Audit every page and report the ids of pages that violate **either** rule
(title out of range OR meta description out of range).

## Input

- `fixtures/pages.json` — `{"pages": [{"id": str, "title": str, "meta_description": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "violations": ["<page id>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-violating pages:

```
credit = clamp01( (|reported ∩ violations| - |reported \ violations|) / |violations| )
```

A blank submission (`violations: []` or omitted) scores `0.0`. The violation
set is computed directly from the character lengths in `fixtures/pages.json`
inside `verify.py` — it is never spelled out in the prompt.
