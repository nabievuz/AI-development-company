# helpdesk-triage — sample PROJECT-OS pack (pack 2)

A second, deliberately different PROJECT-OS pack (contract:
`docs/specs/PROJECT-OS-PACK.md`): an AI support-ticket triage assistant
(TypeScript, Anthropic model provider, Zendesk integration) rather than pack 1's
non-AI CRUD SaaS. It exists to prove the WS7 gateway generalizes — the same
`scripts/gateway_compile.py`, with no code changes, compiles this pack too.

## Why it is a good generality check

Pack 1 (`acme-tasks`) is a non-AI Python/React CRUD app with four goals. This pack
is an AI-agent product with a different language, a real model budget, a
human-in-the-loop autonomy constraint, and five goals. Nothing about either pack
is special-cased in the compiler; both are validated and compiled by the same code
path off the same closed manifest shape and the same canonical AADL doc tree.

## What is in this pack

- [`PROJECT-OS.yaml`](PROJECT-OS.yaml) — the manifest.
- [`docs/01-planning`](docs/01-planning) … `docs/06-maintenance` — the canonical
  AADL six-stage skeleton with real artifacts.
- [`docs/01-planning/discovery.md`](docs/01-planning/discovery.md) — eleven
  Founder discovery Q&A pairs.
- [`APPROVED-GOAL-QUEUE.md`](APPROVED-GOAL-QUEUE.md) — five `founder_approved`
  goals, which compile to 35 self-contained story tickets.

The honest scope note lives in the parent `evals/e2e/README.md`.
