# Golden task — ux-researcher — theme-synthesis

**Role:** `ux-researcher`
**Kind:** deterministic

## Prompt

`fixtures/sessions.json` holds per-session observation notes from a round of
usability testing, each observation tagged with a `theme`. Synthesize across
sessions: for each theme, count the number of **distinct sessions** (not raw
observation mentions) in which it appears — a theme mentioned twice in one
session still counts as session-coverage 1 for that session. Identify the
**top theme** — the one with the highest distinct-session coverage — and
report how many sessions support it.

## Input

- `fixtures/sessions.json` — `{"sessions": [{"session_id": str, "observations":
  [{"theme": str, "note": str}, ...]}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "top_theme": "<theme string>",
  "session_count": <int>
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `top_theme` matches the theme with the highest distinct-session
  coverage in the fixture (ties broken by first occurrence in the fixture).
- `0.5` — `session_count` matches that theme's exact distinct-session coverage.

A blank submission scores `0.0`. The answer key (which theme is top, and its
true coverage) is computed from the SAME fixture the agent was given —
synthesizing it correctly is the graded skill, not a separate leaked table.
