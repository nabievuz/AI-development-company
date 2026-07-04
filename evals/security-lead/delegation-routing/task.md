# Golden task — security-lead — delegation-routing

**Role:** `security-lead`
**Kind:** deterministic

## Prompt

`fixtures/requests.json` lists security requests that landed on your desk.
For each request, decide whether it is **within your charter authority**
(delegate it to `security-eng`, your only delegation route per
`governance/communication-flows.yaml`) or whether it **exceeds your charter
authority** and must be escalated to `cto` (per `.claude/agents/security-lead.md`
"When to escalate": decision exceeds your charter authority → escalate to
your manager).

## Policy (apply exactly, per request)

A request **must escalate to `cto`** if ANY of the following holds:

- `blast_radius` is `"org-wide"` (a company-wide policy/control change), OR
- `requires_policy_exception` is `true` (granting an exception to a standing
  security policy is above your unilateral authority), OR
- `estimated_remediation_cost_usd > 100000` (spend past your delegated
  remediation-budget authority).

Otherwise, **delegate** the request to `security-eng`.

## Input

- `fixtures/requests.json` — array of
  `{id, description, blast_radius, requires_policy_exception, estimated_remediation_cost_usd}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "decisions": {
    "<request id>": { "action": "delegate" | "escalate", "route": "security-eng" | "cto" },
    ...
  }
}
```

## Scoring (deterministic, fractional credit)

For each request, the expected `(action, route)` pair is recomputed from the
policy above applied to that request's fields in `fixtures/requests.json` —
the expected answer is never spelled out in this prompt. Credit is the
fraction of requests where BOTH `action` and `route` match:

```
credit = (# requests with correct action AND route) / (# requests)
```

A blank submission (`decisions` omitted or empty) scores `0.0`.
