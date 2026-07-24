---
id: DAS-1573
title: WS-D Development — OTLP exporter of ADR-0024 spans to self-host Langfuse, flag OFF
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1570
goal: mustaqil-ws-d-lens
spec: 005-mustaqil-ws-d-lens
implements: [FR-001, FR-002, FR-003, FR-004]
labels: [security]
zone: tools/observability
depends_on: [DAS-1572]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-D, part 1).** Build the
OTLP exporter per the DAS-1572 design.

- **FR-001:** an exporter that ships the existing ADR-0024 span events
  (`event_type: "span"`, already OTel GenAI-attribute-named) as OTLP to a
  **self-hosted** Langfuse instance; the target endpoint is read from an
  in-tenant config value only — no default/fallback to a hosted Langfuse
  Cloud or LangSmith URL.
- **FR-002:** apply the ADR-0012 classification + redaction pass to every
  span/attribute before it leaves the process (reuse the existing scrubber,
  do not reimplement).
- **FR-003:** the exporter is read-only over the event store — it never writes
  back to `board/.events.jsonl` or any board field; losing/disabling it changes
  no dispatch outcome (C2).
- **FR-004:** guarded by `ws_d_langfuse_lens` (OFF); with the flag OFF the
  exporter does not run and event emission is byte-identical to pre-merge.

## Acceptance criteria
- [ ] Exporter maps ADR-0024 span fields to an OTLP payload and ships it to a configured self-host Langfuse endpoint only.
- [ ] Every exported span/attribute passes ADR-0012 redaction first; no secret/tool-transcript substring survives in the payload.
- [ ] Exporter is read-only over the event store; no board/routing field is ever written by it.
- [ ] Feature flag OFF by default; flag-off behaviour byte-identical to pre-merge. Merged PR, green CI.

## Log
### 2026-07-24 — Senior Product Manager
Created by /daslab-plan (WS-D Development, part 1). OTLP exporter, self-host
Langfuse target only, ADR-0012 redaction on export, flag OFF.
