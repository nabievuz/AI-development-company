# Golden task — tech-writer — release-note

**Role:** `tech-writer`
**Kind:** soft (rubric-scored — haiku-as-judge)

## Prompt

Write a concise, user-facing release note for the change described in
`fixtures/changeset.md`. It should state what changed, why it matters, and any
action a user must take — no internal jargon.

## Input

- `fixtures/changeset.md` — the merged change to summarise.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "text": "<the release note>",
  "judge_scores": {            // per-dimension scores in [0,1] — a haiku-as-judge
    "correctness": 0.0,        // output at run time; RECORDED here for offline scoring
    "evidence_factuality": 0.0,
    "tests": 0.0,
    "security": 0.0,
    "completeness": 0.0,
    "maintainability": 0.0
  }
}
```

## Scoring (soft, rubric-reuse)

This is the ONLY sanctioned haiku-as-judge path. Credit is the T7 weighted score
computed by [`scripts/check_t7_quality.py`](../../../scripts/check_t7_quality.py)
over the IMMUTABLE dimensions in
[`config/t7_rubric.yaml`](../../../config/t7_rubric.yaml) — no parallel scorer is
forked. A submission with no `judge_scores` scores `0.0`.
