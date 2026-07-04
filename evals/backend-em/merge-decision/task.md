# Golden task — backend-em — merge-decision

**Role:** `backend-em`
**Kind:** deterministic

## Prompt

You are the Backend EM reviewing `PR #4127` before it merges (see
`fixtures/pr_review.md`). CI is fully green. Decide whether to **merge** the
PR now or **request changes**, and give a short reason tag for your decision.

This exercises the core backend-em competency of **technical review /
merge-decision judgment**: CI passing is necessary but not sufficient — an
EM must weigh an unresolved, explicitly `blocking` review thread on a
money-moving endpoint over a green CI signal.

## Input

- `fixtures/pr_review.md` — the PR summary, CI status, and review thread
  state.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decision": "<merge|request_changes>",
  "reason": "<snake_case tag>"
}
```

- `decision` — one of `"merge"` | `"request_changes"`.
- `reason` — a short snake_case tag naming why.

## Scoring (deterministic, fractional credit)

- `0.6` — `decision` matches what the PR state requires (a still-open,
  explicitly `blocking` review thread on a fund-moving endpoint means
  **`request_changes`**, regardless of green CI).
- `0.4` — `reason` is an accepted tag naming the actual blocker (the open
  blocking thread / missing idempotency protection), not just "looks risky"
  or CI status.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
