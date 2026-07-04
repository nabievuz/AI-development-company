# Golden task — content-lead — style-guide-violations

**Role:** `content-lead`
**Kind:** deterministic

## Prompt

You are reviewing a draft blog post before publication. The team's editorial
style guide (`fixtures/style_guide.json`) bans a list of corporate-jargon terms.
Read the draft (`fixtures/draft.md`) and list every banned term from the style
guide that actually appears in the draft's text.

## Input

- `fixtures/draft.md` — the draft blog post to edit.
- `fixtures/style_guide.json` — the style guide's `banned_terms` list.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "violations": [<string>, ...]   // banned terms found present in the draft
}
```

Match terms case-insensitively; report each found term once.

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |required violation set|`, clamped to
  `[0,1]`. The required set is the subset of `banned_terms` that literally
  occurs (case-insensitively) in the draft text.

A blank submission scores `0.0`. The answer key (which terms actually occur in
the draft) lives only in `verify.py`.
