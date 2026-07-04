# Stage 5 — Deployment: launch runbook

## Pre-launch checklist
- EU Postgres provisioned, backups verified, migrations applied.
- Slack outbound remains disabled until the security-lead sign-off is recorded.
- Reverse proxy and TLS configured through the org standard.

## Rollout
- Deploy `api`, `worker`, and `web` via Dokploy behind a health check.
- Enable Slack outbound per workspace only after the sign-off gate.

## Observability and kill-switch
- Traces and request cost per endpoint are visible in the dashboard.
- A feature flag disables Slack outbound instantly if delivery errors spike.

## Rollback
- Roll back to the previous image tag; migrations are backward compatible within
  a release.

## GATE-5 exit
Guardrails are verified live, traces and per-request cost are visible, and the
Slack kill-switch is armed. No launch proceeds with GATE-5 open.
