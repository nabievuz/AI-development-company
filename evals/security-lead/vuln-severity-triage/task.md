# Golden task — security-lead — vuln-severity-triage

**Role:** `security-lead`
**Kind:** deterministic

## Prompt

`fixtures/vulns.json` lists vulnerabilities found in the current release
candidate. For EACH vulnerability, apply the following triage rule exactly to
determine its **severity** tier and the resulting **gate decision** (this is
the GATE-4 red-team risk-acceptance judgment your role owns — see
`.claude/agents/security-lead.md`).

### Severity rule (apply in order, first match wins)

1. `"critical"` if `cvss_score >= 9.0`, OR if `public_exploit_available` is
   `true` AND `internet_facing` is `true` (a public exploit against an
   internet-facing surface is critical regardless of the raw CVSS score).
2. `"high"` if `cvss_score >= 7.0`.
3. `"medium"` if `cvss_score >= 4.0`.
4. Otherwise `"low"`.

### Gate decision rule

- `"block"` the release if severity is `"critical"` or `"high"`.
- `"block"` if severity is `"medium"` AND `data_sensitivity` is `"pii"`
  (a medium-severity bug that touches PII does not get to ride along).
- Otherwise `"accept"`.

## Input

- `fixtures/vulns.json` — array of
  `{id, title, cvss_score, public_exploit_available, internet_facing, data_sensitivity}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "triage": {
    "<vuln id>": { "severity": "critical" | "high" | "medium" | "low", "decision": "block" | "accept" },
    ...
  }
}
```

## Scoring (deterministic, fractional credit)

The expected `severity` and `decision` are recomputed per vulnerability from
the rules above applied to `fixtures/vulns.json` — never spelled out for a
specific vulnerability in this prompt. Per vulnerability, credit is `0.5` for
a correct `severity` plus `0.5` for a correct `decision`. Task credit is the
mean per-vulnerability credit. A blank submission (`triage` omitted or empty)
scores `0.0`.
