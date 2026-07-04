---
id: DAS-1529
title: Golden eval — author 3 deterministic tasks for security-lead (opus)
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
spec: 001-organism-eval-coverage
implements: [FR-001, FR-002]
zone: evals-security-lead
created: 2026-07-04
updated: 2026-07-04
---

## Description

Author the golden-eval set for the **security-lead** role (assigned tier: **opus**,
dept: engineering) — part of R-5 (epic DAS-1508), raising coverage to 32/32.

Create **≥3** golden tasks under `evals/security-lead/<task-id>/`, each exercising a
core competency of security-lead per its overlay (`.claude/agents/security-lead.md`) and its
RACI duties. Use the existing `evals/qa-eng/` and `evals/README.md` as the
TEMPLATE — do not invent a new shape.

Per task:
- `task.md` — the prompt/spec handed to the agent.
- `fixtures/` — inputs the agent sees (NEVER the answer key).
- `verify.py` — a DETERMINISTIC verifier returning fractional credit in
  [0.0, 1.0]; an empty/degenerate submission MUST score 0.0. Use the soft
  rubric path (`RUBRIC = True`, reusing `check_t7_quality.py`) ONLY if the task
  is genuinely subjective.
- `submissions/` — record k=3 sample outputs so the role is graded OFFLINE.

The set MUST clear the ≥0.80 bar at the **opus** tier when scored by
`scripts/agent_eval.py --role security-lead --enforce`.

**Extend, don't fork:** add assets only; do not modify `scripts/agent_eval.py`.
Do NOT edit `docs/AGENT-ROSTER.md` here — the roster scorecard is updated once,
in the synthesis ticket DAS-1535 (avoids a shared-zone merge conflict).

## Acceptance criteria
- [ ] `evals/security-lead/` has ≥3 task dirs, each with `task.md` + `fixtures/` + deterministic `verify.py` + k=3 `submissions/`.
- [ ] `python3 scripts/agent_eval.py --role security-lead --enforce` exits 0 at the opus tier (mean ≥0.80).
- [ ] `--check-gaming` clean for security-lead; empty-submission → 0.0 verified.
- [ ] No change to `scripts/agent_eval.py` or `docs/AGENT-ROSTER.md`.

## Log
### 2026-07-04 — CEO
Created from goal decomposition (/daslab-plan) — R-5 role coverage (security-lead).

### 2026-07-04 — QA Engineer
Authored the golden-eval set for `security-lead` (opus tier) under
`evals/security-lead/`, mirroring `evals/README.md` and the `evals/cto/`
gate-owner shape (security-lead is a gate-owning "lead" role like `cto`, so
its evals mirror `cto`'s gate-check / trade-off / escalation-routing pattern
rather than `qa-eng`'s bug-hunting pattern):

- `security-gate-check/` — GATE-2/4/5 security sign-off checklist (cumulative
  required evidence sections per gate level: threat-model docs → red-team
  report + risk-acceptance log → pen-test + secrets-scan). Deterministic,
  partial credit on the `missing` set.
- `vuln-severity-triage/` — CVSS + exploit/exposure-driven severity
  classification (critical/high/medium/low) and the resulting block/accept
  gate decision, including a PII-carve-out rule for medium severity.
- `delegation-routing/` — delegate-to-`security-eng` vs escalate-to-`cto`
  decision from blast-radius / policy-exception / remediation-cost fields,
  mirroring the role's actual `governance/communication-flows.yaml` routes.

Each task dir has `task.md` + `fixtures/` (inputs only, no real secrets, all
synthetic) + a deterministic `verify.py` (fractional credit, empty submission
→ 0.0, answer key lives only in `verify.py`) + `submissions/` with k=3
attempts.

Acceptance run (in worktree `.claude/worktrees/DAS-1529`, repo root):

```
$ python3 scripts/agent_eval.py --role security-lead --tier opus --enforce
security-lead [opus]: accuracy=0.884 over 3 task(s) [PASS @>=0.80], cost=n/a (inert)
EXIT: 0

$ python3 scripts/agent_eval.py --check-gaming
OK: no gameable golden tasks.
EXIT: 0
```

`git diff --stat scripts/agent_eval.py docs/AGENT-ROSTER.md` is empty —
neither file was touched (per the ticket's "extend, don't fork" instruction;
the roster scorecard update is deferred to the synthesis ticket DAS-1535).

**Escalation / next-wave note (security-touching content):** this eval set
encodes security-lead's actual triage/gate judgment calls (CVSS thresholds,
gate evidence requirements, escalation ceilings). Per this ticket's own
"never review your own work" discipline and because the content is
security-domain-sensitive, routing to `qa-lead` for review, who should loop in
`security-lead`/`security-eng` if the triage rules themselves need a security
sanity-check before this is treated as ground truth for role scoring.

Set `status: in_review`, `assignee: qa-lead` (per `board/ROUTING.md`, my
reviewer). Committed locally on branch
`feat/das-1529-golden-eval-security-lead` in worktree
`.claude/worktrees/DAS-1529` — no push, no PR (hard local-only per dispatch).

### 2026-07-04 — QA Lead (GATE-4 review)
Reviewed independently (adversarial). enforce PASS (accuracy=0.884), deterministic verifiers, empty→0.0, answer-key not leaked, tasks meaningful & distinct. Approved → done.
