# Stage 3 — Development: architecture topography and contracts

## Topography
- `ingest` service: polls Zendesk for new tickets and enqueues events on Redis.
- `triage` worker: redacts, classifies intent and urgency, and drafts a reply.
- `router` service: writes the routing decision and the draft back to Zendesk.
- `redis`: the event and job queue.

## Tool and integration contracts
- `classify(ticket) -> {intent, urgency, confidence}` — the model-backed step;
  low confidence routes to a human catch-all.
- `draft(ticket, intent) -> reply_text` — produces a suggested reply only; it is
  never sent, only attached for human approval.
- `route(ticket, queue)` — writes the target queue back to Zendesk.

## Reproducible dev environment
- `docker compose up` starts the three services plus Redis with a Zendesk stub.
- The model layer is hot-swappable behind the `classify` and `draft` contracts.

## GATE-3 exit
The topography matches the code, the three tool contracts are documented, the dev
environment is reproducible, and the model layer is swappable.
