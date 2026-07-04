# Golden task — ux-researcher — severity-triage

**Role:** `ux-researcher`
**Kind:** deterministic

## Prompt

`fixtures/findings.json` lists usability findings gathered across a moderated
study (`session_count` participants total). Each finding records how many
participants hit it (`participants_affected`) and whether it blocked the
participant from completing the task (`task_blocking`).

Triage each finding into a severity using this standard usability-severity
matrix, driven by **frequency** (`participants_affected / session_count`) and
**impact** (`task_blocking`):

- **critical** — blocks the task AND frequency ≥ 0.5 (a majority hit a
  showstopper).
- **major** — blocks the task but is rarer (frequency < 0.5), OR does not
  block the task but is pervasive (frequency ≥ 0.5).
- **minor** — does not block the task AND frequency < 0.5 (rare, cosmetic, or
  low-impact).

## Input

- `fixtures/findings.json` — `{"session_count": int, "findings": [{"id": str,
  "description": str, "participants_affected": int, "task_blocking": bool}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "severities": { "<finding id>": "critical" | "major" | "minor", ... } }
```

## Scoring (deterministic, fractional credit)

`credit = (number of findings whose reported severity matches the matrix
above) / (total number of findings)`. A blank submission scores `0.0`. The
answer key (the correctly-triaged severity per finding) is derived from the
SAME fixture the agent was given — applying the matrix correctly is the
graded skill, not a separate leaked lookup table.
