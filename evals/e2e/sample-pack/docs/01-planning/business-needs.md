# Stage 1 — Planning: business needs, objectives, resources, risk-ethics

## Business need
Small teams lose visibility into task ownership and deadlines when they track
work in shared spreadsheets. acme-tasks gives them a shared, auditable workspace
with clear owners and due dates.

## Objectives (measurable)
- Reach forty weekly active workspaces by the end of the first quarter.
- Keep task-create p95 latency at or under 400ms.
- Deliver Slack notifications at or above a 99% success rate.

## Resources
- Team: two backend engineers, one frontend engineer, part-time SRE and QA.
- Budget: USD 300 per month infrastructure ceiling; no model-inference spend.
- Reused assets: the org FastAPI service template, shared EU Postgres, Dokploy.

## Risk and ethics review
- Data minimization: store only email and display name; mask email in Slack.
- Data residency: all data stays in EU-region storage.
- Cross-workspace isolation is a hard requirement; a leak blocks launch.
- No autonomous automation in v1, so there is no runaway-loop cost risk.

## GATE-1 exit
A measurable business KPI is defined (weekly active workspaces), scope is explicit
(CRUD plus one integration, AI explicitly out of scope), and the budget and
risk-ethics review are signed off.
