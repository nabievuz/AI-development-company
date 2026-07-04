# RFC-NNNN: <Title>

- Author:
- Status: Draft | In Review | Accepted | Rejected | Withdrawn
- Date:
- Related: <ADR, issue ids>

## Summary
One paragraph. What is being proposed?

## Motivation
Why now? What problem are we solving?

## Proposal
The concrete change. Include scope, non-scope, and migration shape.

## Alternatives
What else was considered and why it lost.

## Risks & Open Questions
What could go wrong; what needs more information before deciding.

## Threat Model

> **Required.** This section must be completed before CTO approval (A04:2021 — Insecure Design, DasLab Security Baseline).
> Security Lead reviews this section as part of the RFC approval gate.

### Data Flows
List the data flows introduced or modified by this RFC. For each flow identify:
- **Source** — where data originates (user input, external API, internal service, database, etc.)
- **Destination** — where data ends up (database, external API, browser, log, another service, etc.)
- **Sensitivity** — is the data PII, credentials, financial, or otherwise sensitive?
- **Transport** — is the channel encrypted in transit?

| Flow | Source | Destination | Sensitive? | Encrypted? |
|------|--------|-------------|------------|------------|
| example: user uploads avatar URL | browser form | avatar-service fetch | no | yes (HTTPS only) |

### Trust Boundaries
Identify every point where data crosses a trust boundary:
- User → service (unauthenticated input)
- Service → service (internal API call — is mTLS or a service token used?)
- Service → external third party
- Service → database (are parameterised queries used? RLS enabled for multi-tenant data?)

### Abuse Scenarios
Describe at least three plausible abuse scenarios for this feature. For each, describe the attack and the planned mitigation:

| Scenario | Attack | Mitigation |
|----------|--------|------------|
| 1. | | |
| 2. | | |
| 3. | | |

Common categories to consider: account enumeration, IDOR / broken access control, rate-limit bypass, privilege escalation, data exfiltration, input injection (SQL, shell, template), SSRF, replay attacks, bulk/automated abuse (referral fraud, bulk export), denial of service.

### Security Controls Checklist
Mark each item as **in scope** (must be addressed in implementation) or **N/A** (explain why):

- [ ] Authentication required on all new endpoints (A01)
- [ ] Authorisation / ownership check prevents IDOR (A01)
- [ ] No secrets or PII logged or returned in error responses (A02)
- [ ] All database queries parameterised; no raw SQL concatenation (A03)
- [ ] Rate limiting applied on new public/auth endpoints (A04)
- [ ] HTTP security headers present on new responses (A05)
- [ ] Input validated with Zod at the API boundary (A08)
- [ ] Webhook payloads validated with HMAC if applicable (A08)
- [ ] Security events (`logSecurityEvent`) emitted for auth/admin/privilege actions (A09)
- [ ] User-supplied URLs go through `safeFetch` from `@daslab/ssrf-guard` (A10)
