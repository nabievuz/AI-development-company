# Policy: Enterprise Quality Bar per Deliverable

> **Status:** Binding board policy — precedence level 2 (root `AGENTS.md` §2).
> **Scope:** Every deliverable shipped by the DasLab engine, for any project.
> **Principle:** "done" is a green check, not a judgment call. A deliverable is
> not done until every applicable bar below is met and evidenced in the ticket.

DasLab is a high-performance, project-agnostic software factory. Performance is
measured (`scripts/board_metrics.py`: throughput, cycle time, gate pass-rate,
blocked/rework) and quality is gated. Speed never trades against the bar.

## The bar (per deliverable)

1. **Tested + green CI.** Code ships with automated tests that actually exercise
   the change; CI is green on the merge. No `done` without a merged PR + green CI.
2. **Reviewed (author ≠ reviewer).** Every change is reviewed by the author's
   manager per `board/ROUTING.md`. Decisions are logged in the ticket.
3. **Secured.** Security-relevant changes carry a Security-Lead sign-off
   (GATE-2/4/5); inputs validated, secrets never committed, threats considered.
4. **Documented in the same change.** User-facing or interface changes update the
   docs/README in the same PR — never "docs later".
5. **Observable + operable.** Production-bound work ships with the signals and a
   runbook to operate it (KPIs/SLOs, logs/metrics, on-call notes) before GATE-5.
6. **Reversible deploy.** Releases are staged and rollback-able; a backup/restore
   point exists before any destructive or outward step (per `AGENTS.md` safety).
7. **Traceable.** The work flowed through the board as gated tickets with an
   append-only log; ArcRift bracketed each unit (recall at start, store at end).

## Gate mapping (AADL)

| Gate | Bar enforced |
|---|---|
| GATE-1 Planning | scope + acceptance criteria written; RACI owner set |
| GATE-2 Design | design signed off; security threat model where relevant |
| GATE-3 Development | tested + reviewed + documented; green CI |
| GATE-4 Testing | eval/QA thresholds met; release-blocking judgment by QA-Lead |
| GATE-5 Deployment | observability + runbook + reversible deploy; SRE-Lead sign-off |
| GATE-6 Maintenance | KPIs/SLOs live; retro captured |

## Effectiveness (performance) expectations

- **Parallelism without a cap** — every actionable ticket is dispatched each
  wave; real concurrency is harness-bounded. The only dispatch bounds are the
  correctness guards (one ticket per repo area per wave) and AADL gate order.
- **Model by task complexity** — `governance/policies/model-allocation.md` is
  canon; the model follows the task, not the title.
- **Measured, not asserted** — `board_metrics.py` reports throughput, cycle time,
  gate pass-rate, and blocked/rework so regressions in effectiveness are visible.
