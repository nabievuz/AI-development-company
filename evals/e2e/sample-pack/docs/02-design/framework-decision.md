# Stage 2 — Design: framework decision and guardrails

## Framework decision
- Backend: FastAPI (Python) behind the org service template, chosen for the team's
  existing familiarity and the shared Postgres tooling.
- Frontend: React single-page app, served statically.
- Persistence: managed EU-region Postgres, one schema per environment.

## Data model (indicative)
- `workspace(id, name, region)`
- `user(id, email, display_name)`
- `membership(workspace_id, user_id, role)`
- `task(id, workspace_id, title, owner_id, due_at, status)`

## Guardrails
- Every query is workspace-scoped; cross-workspace reads are rejected at the data
  layer, not just the API layer.
- Email is masked before it is placed in any outbound Slack payload.
- Slack outbound is disabled by default and turned on only after the security-lead
  sign-off named in the manifest constraints.

## GATE-2 exit
The framework decision is recorded, the data model and workspace-isolation
guardrail are specified, and the security-lead has signed off on the design of the
one external integration.
