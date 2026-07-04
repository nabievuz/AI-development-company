# Stage 2 — Design: framework, model card, guardrails

## Framework decision
- Runtime: TypeScript on Express, using the org claude-agent-sdk template.
- Queueing: Redis-backed job queue for inbound ticket events.
- Integration: Zendesk API for reading tickets and writing routing plus a draft.

## Model card (indicative)
- Provider: Anthropic. Task: classify intent and urgency, then draft a first reply.
- Cost and latency: budgeted at USD 800 per month; per-ticket latency target under
  five seconds for classification.
- Failure behavior: on low confidence, route to a human catch-all queue rather
  than guess.

## Guardrails
- Redaction of card numbers and emails runs before any model call.
- A hard human-approval step gates every drafted reply; nothing auto-sends.
- Tool-iteration cap of five per ticket, with a kill-switch on runaway loops.

## GATE-2 exit
The framework decision and model card are recorded, guardrails cover redaction,
human approval, and loop bounding, and the security-lead has signed off.
