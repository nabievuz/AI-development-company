# Golden task — cmo — brand-voice-violation-audit

**Role:** `cmo`
**Kind:** deterministic

## Prompt

`fixtures/snippets.json` lists draft customer-facing marketing copy snippets
awaiting your sign-off. Per the brand guide, a snippet **violates brand
voice** when ANY of the following hold:

- it contains a banned superlative/hype phrase (case-insensitive, matched as a
  substring): `"best ever"`, `"guaranteed"`, `"revolutionary"`, `"#1"`,
  `"life-changing"`; OR
- it contains **more than one** exclamation mark (`!`) total; OR
- it contains a "shouting" word — a whole word of 4+ letters that is written
  in ALL CAPS (e.g. `FREE`, `NOW`) — punctuation and numbers don't count
  toward the letter count.

A snippet with none of these issues is on-voice; do not flag it.

Report the `id`s of every snippet that violates brand voice.

## Input

- `fixtures/snippets.json` — `{"snippets": [{"id": str, "text": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "violations": ["<snippet id>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-violating snippets:

```
credit = clamp01( (|reported ∩ violations| - |reported \ violations|) / |violations| )
```

A blank submission scores `0.0`. The violation set is computed directly from
the text-matching rules above applied to `fixtures/snippets.json` inside
`verify.py` — it is never spelled out further than the rules already stated.
