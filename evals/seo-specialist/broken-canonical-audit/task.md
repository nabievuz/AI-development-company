# Golden task — seo-specialist — broken-canonical-audit

**Role:** `seo-specialist`
**Kind:** deterministic

## Prompt

`fixtures/pages.json` lists crawled pages with their `url` and declared
`canonical` tag. A page's canonical tag has an issue when:

- it is **missing or empty** (no canonical declared), OR
- it points to a **different URL that does not exist** anywhere else in the
  crawl (a "dangling"/broken canonical — the target page was never found, so
  the signal is worthless and risks duplicate-content dilution).

A canonical that points to the page's own URL, or to another URL that *is*
present elsewhere in the crawl (e.g. a parameterised variant canonicalising to
its clean version), is **fine** — do not flag it.

Report the `url`s of every page whose canonical tag has an issue.

## Input

- `fixtures/pages.json` — `{"pages": [{"url": str, "canonical": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "broken_urls": ["<page url>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-broken pages:

```
credit = clamp01( (|reported ∩ broken| - |reported \ broken|) / |broken| )
```

A blank submission scores `0.0`. The broken set is computed directly from
`fixtures/pages.json` inside `verify.py` — it is never spelled out in the
prompt.
