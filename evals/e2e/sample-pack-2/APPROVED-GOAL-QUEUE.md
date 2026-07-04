# APPROVED-GOAL-QUEUE — helpdesk-triage

APPROVED: TASDIQLANDI 2026-07-03 — Founder approved the queue below after the
eleven-question discovery pass and the sourced research conclusion. Each goal is
`founder_approved` and compilable by the WS7 gateway, one goal at a time.

The gateway compiles one epic plus six AADL stage tickets per approved goal. Five
approved goals therefore compile into 35 self-contained story tickets.

| order | goal_slug | outcome | why_now | research_basis | owner | status | ticket_refs |
|---|---|---|---|---|---|---|---|
| 1 | ticket-ingest | Poll Zendesk for inbound tickets and enqueue redacted events on Redis | nothing can be triaged until tickets are ingested safely | Zendesk API capabilities and rate-limit review | cpo | founder_approved | - |
| 2 | intent-classifier | Classify each ticket by intent and urgency with a confidence score | the accuracy KPI depends on reliable classification | support-taxonomy analysis and labeled-set study | cpo | founder_approved | - |
| 3 | reply-drafter | Draft a suggested first reply that always requires human approval | first-response time is the headline KPI | agent-assist reply-quality benchmarks | cpo | founder_approved | - |
| 4 | queue-router | Route each ticket to the correct human queue in Zendesk | mis-routing is the main current source of delay | queue-topology and escalation-path review | cpo | founder_approved | - |
| 5 | eval-harness | An offline labeled eval set with routing-accuracy and zero-auto-send scoring in CI | GATE-4 requires an automated eval threshold | org eval-harness patterns and red-team guidance | cpo | founder_approved | - |
