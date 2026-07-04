# Golden task — coo — sla-gate-decision

**Role:** `coo`
**Kind:** deterministic

## Prompt

`fixtures/compliance_report.json` lists this cycle's open compliance/SLA
issues. As COO you hold the release-gate authority
(`operations/CLAUDE.md` Authority: "Block any release with unresolved
compliance issues"). Decide whether to block this release, using the
standard operations gate rule:

> The release is **blocked** if, and only if, there is at least one issue
> that is both **unresolved** (`resolved: false`) and has severity
> **`critical`** or **`high`**. Unresolved `medium`/`low` issues and any
> resolved issue (of any severity) do NOT block the release on their own.

## Input

- `fixtures/compliance_report.json` — `{"issues": [{"id": str, "severity": "critical"|"high"|"medium"|"low", "resolved": bool, "area": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "block_release": true,
  "blocking_issues": ["<issue id>", ...]
}
```

`blocking_issues` lists exactly the issue ids that satisfy the blocking
condition above (empty list if `block_release` is `false`).

## Scoring (deterministic, fractional credit)

- `0.5` — `block_release` matches the correct gate decision.
- `0.5` — `blocking_issues` matches the correct blocking-id set via
  `clamp01((hits - false_positives) / |blocking set|)` when the blocking set
  is non-empty; when the correct blocking set is empty, this half is earned
  only if `blocking_issues` is also empty.

A blank submission (no `block_release`, no `blocking_issues`) scores `0.0`.
The blocking set is computed from the fixture inside `verify.py`; it is
never spelled out in the prompt.
