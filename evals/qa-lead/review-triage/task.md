# Golden task — qa-lead — review-triage

**Role:** `qa-lead`
**Kind:** deterministic

## Prompt

`fixtures/findings.json` lists the findings from a code review of `PR-882`.
As QA Lead, triage them: identify exactly the findings that must **block the
merge**. Severity alone does not decide this — a `major` finding blocks the
merge only when it is also security-relevant; a `major` style nit does not.

## Input

- `fixtures/findings.json` — `{"findings": [{"id", "severity", "category"}, ...]}`.
  `severity` is one of `blocker`, `major`, `minor`, `nit`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "blocking": ["<finding id>", ...] }
```

## Scoring (deterministic, fractional credit)

```
credit = clamp01( (|reported ∩ blocking| - |reported \ blocking|) / |blocking| )
```

The blocking set is derived from the findings inside `verify.py` (never
spelled out here). A blank submission scores `0.0`.
