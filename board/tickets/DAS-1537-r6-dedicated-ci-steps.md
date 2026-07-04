---
id: DAS-1537
title: R-6 — wire check_import_ban / check-gaming / validate_commflows as dedicated CI steps
status: done
assignee: sre-lead
author: cto
dept: engineering
priority: p1
parent: DAS-1508
goal: organism-ws6-guild
zone: ci-workflow
created: 2026-07-04
updated: 2026-07-04
---

## Description

Remediation **R-6** (audit finding F-5): three shipped validators had CI coverage
only INDIRECTLY (inside `diagnostics.py` or via pytest), not as dedicated blocking
CI steps. This ticket wires them as first-class gates in `.github/workflows/ci.yml`
(`validate` job) so a regression fails CI directly and legibly:

1. **`check_import_ban.py`** — clean-room protocol (§2): no donor libraries
   (langgraph / crewai / agency-swarm / superagi / agent-framework). Was only
   inside `diagnostics.py`.
2. **`agent_eval.py --check-gaming`** — the golden-eval anti-gaming probe, now
   including the DAS-1536 task.md answer-key-leak detector. Was covered only via
   pytest; the `--all --enforce` step alone does not run the gaming probe.
3. **`validate_commflows.py`** — communication-flows.yaml shape + derivation
   validator (distinct from the closed-graph `check_comm_flows.py`, which was
   already wired). Was covered only via pytest.

CI teeth are preserved: zero `continue-on-error` / `|| true` escapes anywhere in
the workflows; all three run and must exit 0.

**VERSION 2.0.0 is intentionally NOT bumped here.** The §5 release contract is not
fully green — rows T1 (busy_fraction), T3 (concurrency), T4 (model-mix) stay
`unmeasured` until the HEARTBEAT loop goes live (R-4), which is Founder-gated
(push/CI resolution + ≥3-day counted shadow window + `heartbeat_enabled` flip).
Shipping v2.0.0 with contract rows red would violate §8. The VERSION bump +
CHANGELOG belong to the R-4 close, not here.

## Acceptance criteria
- [x] `check_import_ban.py`, `agent_eval.py --check-gaming`, `validate_commflows.py`
      each present as a dedicated blocking step in `.github/workflows/ci.yml`.
- [x] All three exit 0 on the current tree; CI YAML is valid; zero `continue-on-error`.
- [x] `diagnostics.py` 100/100; full suite green.
- [ ] VERSION 2.0.0 + CHANGELOG — DEFERRED to R-4 close (contract not yet all-green).

## Log
### 2026-07-04 — CTO
Added 3 dedicated blocking CI steps to ci.yml validate job (60 steps total):
clean-room import-ban, comm-flows shape/derivation (validate_commflows), and the
golden-eval anti-gaming probe (--check-gaming, now with the DAS-1536 leak detector).
All three exit 0 locally; YAML valid; zero continue-on-error escapes; diagnostics
100/100. VERSION 2.0.0 explicitly deferred to R-4 (loop-live) close per §5/§8 —
recorded as the one open acceptance box. Local-only (no push).
