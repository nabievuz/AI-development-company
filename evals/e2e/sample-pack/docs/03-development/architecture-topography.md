# Stage 3 — Development: architecture topography and contracts

## Topography
- `api` service (FastAPI): auth, workspaces, tasks, membership endpoints.
- `worker` service: consumes a task-event queue and calls the Slack integration.
- `web` service: the React SPA.
- `postgres`: single managed EU instance, per-environment schema.

## Tool and integration contracts
- Slack outbound: a single `notify(workspace, event)` contract that posts to a
  per-workspace webhook. Email is masked before the payload is built. Failures
  are retried up to three times, then dropped to a dead-letter log.
- Auth: email plus password with a hashed-and-salted store; sessions are signed
  server-side cookies.

## Reproducible dev environment
- `docker compose up` brings the four services and a seeded Postgres online.
- Configuration is entirely environment-variable driven; no secrets in the repo.

## GATE-3 exit
The topography document matches the running code, the Slack tool contract is
documented, the dev environment is reproducible from a single command, and the
notification layer is swappable behind the `notify` contract.
