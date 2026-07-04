# Golden task — security-eng — spot-injection

**Role:** `security-eng`
**Kind:** deterministic

## Prompt

The function in `fixtures/query.py` builds a SQL statement. Identify the line that is vulnerable to SQL injection and name the vulnerability class.

## Input

- `fixtures/query.py` — the code under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "vuln_line": <int>,
  "vuln_type": "<category>"
}
```

## Scoring (deterministic, fractional credit)

- `0.5` — `vuln_line` (1-indexed) points at the interpolated-SQL line.
- `0.5` — `vuln_type` is `sql_injection` or `sqli`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
