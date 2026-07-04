# Golden task — backend-em — api-design-review

**Role:** `backend-em`
**Kind:** deterministic

## Prompt

Read the RFC in `fixtures/api_proposal.md`. As the reviewing Backend EM,
identify which of the listed **candidate issues** are real API/service
design problems with this proposal (as opposed to normal, unremarkable
properties of the design). This exercises the core backend-em competency of
**API/service design judgment**.

## Input

- `fixtures/api_proposal.md` — the RFC and a candidate-issue checklist.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "issues": ["<candidate tag>", ...]
}
```

`issues` is the subset of the candidate tags (from the fixture's checklist)
that are genuine design problems in this proposal.

## Scoring (deterministic, fractional credit)

Scored as the **F1** score of the submitted issue set against the answer
key (precision and recall over the tag set), so both missed real issues and
false-positive tags (e.g. flagging normal properties like `uses_json_body`
or `has_auth_header` as problems) cost credit.

An empty `issues` list (or missing key) scores `0.0`. The answer key lives
only in `verify.py`.
