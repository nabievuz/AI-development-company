# Golden task — qa-eng — detect-flaky-assertion

**Role:** `qa-eng`
**Kind:** deterministic

## Prompt

The test file at `fixtures/sample_test.py` fails intermittently in CI. Exactly one
assertion is non-deterministic (it depends on wall-clock time). Identify it and
name an appropriate fix strategy.

## Input

- `fixtures/sample_test.py` — the flaky test module.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "flaky_line": <int>,       // 1-indexed line of the non-deterministic assertion
  "fix_kind": "<str>"        // fix strategy: one of inject_clock | freeze_time | assert_range
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `flaky_line` points at the assertion that reads `datetime.datetime.now()`.
- `0.5` — `fix_kind` is one of the accepted deterministic-time fix strategies.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
