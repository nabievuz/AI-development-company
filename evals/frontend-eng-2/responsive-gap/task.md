# Golden task — frontend-eng-2 — responsive-gap

**Role:** `frontend-eng-2`
**Kind:** deterministic

## Prompt

`fixtures/styles.css` lays out a sidebar + main two-column page. A mobile
breakpoint (`max-width: 599px`) hides the sidebar and a desktop breakpoint
(`min-width: 768px`) widens it. The base (un-media-queried) rules are tuned
for the desktop breakpoint's dimensions.

QA reports the sidebar visually overlaps the main content on tablet-width
devices. Identify the inclusive viewport-width range, in px, that falls into
**neither** breakpoint — where the desktop-tuned base rules render at a width
too narrow for them, causing the overlap.

## Input

- `fixtures/styles.css` — the layout rules and both media queries.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "broken_range": [<int low>, <int high>] }
```

## Scoring (deterministic, fractional credit)

The required range is the integer px gap strictly between the mobile
`max-width` breakpoint and the desktop `min-width` breakpoint — derived by
parsing the actual fixture CSS, not spelled out here. Credit is the
intersection-over-union (IoU) of the submitted range against the required
range, clamped to `[0, 1]`:

```
credit = clamp01( |submitted ∩ required| / |submitted ∪ required| )
```

A blank submission (missing/malformed `broken_range`) scores `0.0`. A wildly
oversized range is penalised by the union term, so guessing `[0, 100000]`
does not game the score.
