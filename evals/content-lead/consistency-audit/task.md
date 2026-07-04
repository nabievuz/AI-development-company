# Golden task — content-lead — consistency-audit

**Role:** `content-lead`
**Kind:** deterministic

## Prompt

Four short marketing snippets live under `fixtures/docs/`. The canonical
product facts (`fixtures/style_guide.json`) give the exact product name and
price that every published snippet must use verbatim. Audit the snippets and
report which files are **inconsistent** — i.e. they do not use the canonical
name and/or canonical price exactly as specified.

## Input

- `fixtures/docs/doc-a.md`, `doc-b.md`, `doc-c.md`, `doc-d.md` — the snippets.
- `fixtures/style_guide.json` — `canonical_name` and `canonical_price`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "inconsistent_docs": [<string>, ...]   // filenames, e.g. "doc-b.md"
}
```

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |required inconsistent set|`, clamped
  to `[0,1]`. The required set is every doc filename that does not contain
  the `canonical_name` string exactly and/or does not contain the
  `canonical_price` string exactly.

A blank submission scores `0.0`. The answer key (which docs actually deviate)
lives only in `verify.py`.
