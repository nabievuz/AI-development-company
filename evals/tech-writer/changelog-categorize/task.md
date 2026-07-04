# Golden task — tech-writer — changelog-categorize

**Role:** `tech-writer`
**Kind:** deterministic

## Prompt

Group the Conventional-Commit messages in `fixtures/commits.json` under their changelog category (`feat`, `fix`, `docs`, ...). A message belongs to exactly one category — the token before the first `:`.

## Input

- `fixtures/commits.json` — the merged commit messages.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "categories": {
    "feat": ["feat: ..."],
    "fix": ["fix: ..."]
  }
}
```

## Scoring (deterministic, fractional credit)

- credit = `correctly_placed / total_commits`. A commit counts only if it appears under its true category AND under no other category (dumping a commit under every bucket earns nothing).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
