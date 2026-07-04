# Stage 5 — Deployment: launch runbook

## Pre-launch checklist
- Redis provisioned; Zendesk API credentials stored as environment secrets.
- The human-approval step is verified live: no path can auto-send a reply.
- Model-budget alerting is wired with a hard stop at USD 800 per month.

## Rollout
- Deploy `ingest`, `triage`, and `router` via Dokploy behind health checks.
- Start with a single pilot support team before broader rollout.

## Observability and kill-switch
- Traces and cost per ticket are visible in the dashboard.
- The kill-switch halts the `triage` worker if the iteration cap or budget trips.

## Rollback
- Roll back to the previous image tag; queued events replay safely.

## GATE-5 exit
Guardrails (redaction, human approval, loop bound) are verified live, cost per
ticket is visible, and the kill-switch is armed. No launch proceeds with GATE-5
open.
