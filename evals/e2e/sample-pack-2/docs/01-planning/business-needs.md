# Stage 1 — Planning: business needs, objectives, resources, risk-ethics

## Business need
A mid-size support team on Zendesk is slow to give a first response because
inbound tickets arrive unsorted. helpdesk-triage classifies and routes each ticket
and drafts a first reply for human review.

## Objectives (measurable)
- Median first-response time at or under ten minutes (from forty-five).
- Triage routing accuracy at or above 90% (from roughly 78% manual).
- Zero auto-sent customer replies.

## Resources
- Team: two engineers, one support lead as domain reviewer, part-time SRE and QA.
- Budget: USD 800 per month model spend plus USD 200 infrastructure, hard-capped.
- Reused assets: the org claude-agent-sdk template, shared Redis, Dokploy.

## Risk and ethics review
- Human-in-the-loop is mandatory: no reply leaves the system without approval.
- Card numbers and emails are redacted before any model call.
- A runaway classification loop is bounded by a five-iteration cap and kill-switch.

## GATE-1 exit
A measurable KPI is defined (first-response time), scope is explicit (triage and
draft, never auto-send), and the model budget and risk-ethics review are signed off.
