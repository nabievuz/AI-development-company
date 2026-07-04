# acme-tasks — sample PROJECT-OS pack (pack 1)

A small but real PROJECT-OS pack (contract: `docs/specs/PROJECT-OS-PACK.md`) for a
CRUD task-management SaaS with email/password auth and one external integration
(Slack notifications). It exists to prove the WS7 gateway
(`scripts/gateway_compile.py`) compiles a Founder-approved pack into a coherent,
self-contained, stage-gated story-ticket board with zero hand-written tickets.

## What is in this pack

- [`PROJECT-OS.yaml`](PROJECT-OS.yaml) — the manifest (closed field set: name,
  mission, constraints, stack, budget, success_metrics).
- [`docs/01-planning`](docs/01-planning) … `docs/06-maintenance` — the canonical
  AADL six-stage lifecycle skeleton with real Stage-1..6 planning artifacts.
- [`docs/01-planning/discovery.md`](docs/01-planning/discovery.md) — twelve
  Founder discovery Q&A pairs (the gate needs at least ten).
- [`APPROVED-GOAL-QUEUE.md`](APPROVED-GOAL-QUEUE.md) — the Founder-approved,
  research-backed work queue: four goals, each `founder_approved`.

## What compiling it proves

Four approved goals, each compiling to one epic plus six stage tickets, produce
28 story tickets — comfortably above the 25-ticket bar. Every compiled ticket is
self-contained: embedded mission context, acceptance criteria, produces/consumes
edges, its AADL stage, and a gate reference. The e2e harness that drives this pack
is `tests/test_e2e_sample_pack.py`; the honest scope note lives in the parent
`evals/e2e/README.md`.
