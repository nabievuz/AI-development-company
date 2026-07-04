# Golden task — senior-pm — acceptance-criteria-quality

**Role:** `senior-pm`
**Competency:** acceptance-criteria quality (turning a story + implied edge
cases into testable, well-structured acceptance criteria)
**Kind:** deterministic

## Prompt

`fixtures/user_story.md` describes a "password reset via email link" story,
plus a block of support-ticket context that implies several edge cases the
happy-path story doesn't spell out explicitly. Write the acceptance criteria
for this story.

## Input

- `fixtures/user_story.md` — the story and its support-ticket context.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "acceptance_criteria": ["<criterion 1>", "<criterion 2>", ...] }
```

Each string is one acceptance criterion. Given/When/Then phrasing is
encouraged (it scores a structure bonus) but not required for content
credit.

## Scoring (deterministic, fractional credit)

`verify.py` checks two things, neither spelled out here in full (the keys
live only in `verify.py`):

1. **Scenario coverage (70% of credit).** The support-ticket context implies
   a fixed number of distinct edge-case scenarios (e.g. an expired link, a
   rate-limited endpoint, malformed input, a reused/replayed token). A
   criterion "covers" a scenario when it contains all of that scenario's
   required keywords (case-insensitive substring match). Coverage is
   `covered_scenarios / total_scenarios`, with a padding penalty once the
   list is far longer than the number of scenarios.
2. **Given/When/Then structure (30% of credit).** The fraction of submitted
   criteria that read as a testable Given/When/Then condition.

```
credit = clamp01( 0.7 * scenario_coverage + 0.3 * structure_fraction )
```

An empty or missing `acceptance_criteria` list scores `0.0`.
