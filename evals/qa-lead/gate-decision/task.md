# Golden task — qa-lead — gate-decision

**Role:** `qa-lead`
**Kind:** deterministic

## Prompt

`fixtures/ci_report.json` is the pre-release CI/QA snapshot for a release
candidate. As QA Lead you own the GATE-4 quality-gate decision: make the
**go / no-go call** and name every substantive reason that drives it.

A flaky test is not, by itself, a release blocker (it is a reliability debt to
track, not a correctness failure) — judge each signal on its own merits rather
than flagging everything present in the report.

## Input

- `fixtures/ci_report.json` — `coverage_pct`, `coverage_threshold`,
  `failing_tests_on_main` (list), `flaky_tests` (list), `open_bugs` (list of
  `{id, severity}`).

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decision": "go" | "no_go",
  "blocking_reasons": ["<reason>", ...]
}
```

Valid `blocking_reasons` values: `failing_tests_on_main`, `open_p0_bug`,
`coverage_below_threshold`. (A flaky test is never itself a valid blocking
reason.)

## Scoring (deterministic, fractional credit)

- `0.5` — `decision` matches the correct call for this report.
- `0.5` — `blocking_reasons` scored by
  `clamp01((|reported ∩ expected| - |reported \ expected|) / |expected|)`,
  where `expected` is derived from the report inside `verify.py` (never spelled
  out here).

A blank submission scores `0.0`.
