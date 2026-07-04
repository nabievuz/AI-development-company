# Golden task — tech-writer — doc-link-check

**Role:** `tech-writer`
**Kind:** deterministic

## Prompt

The Markdown document `fixtures/doc.md` links to relative files. Using the list of files that actually exist in `fixtures/files.json`, report every link whose target is missing (a broken link).

## Input

- `fixtures/doc.md` — the document.
- `fixtures/files.json` — existing file paths.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "broken_links": ["docs/legacy.md", ...]
}
```

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |broken set|`, clamped to `[0,1]`. The broken set = link targets not present in the existing-files list.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
