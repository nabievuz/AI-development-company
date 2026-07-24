---
id: DAS-1554
title: WS-B Design — daslab_sdk call shape, admission gateway, run_wave boundary
status: todo
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-002, FR-003, FR-004]
labels: [security]
zone: docs/design
depends_on: [DAS-1553]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 2 — Design (closes GATE-2 for WS-B).** Design the runner contract
the Development tickets implement. No code beyond schemas/interface
signatures.

- **Load boundary (SR-1):** the `daslab_sdk` call shape — `cwd` = repo root,
  `setting_sources=["project"]` — that loads the existing `.claude/agents`,
  skills, `CLAUDE.md`, hooks, and `.mcp.json` (ArcRift included) unmodified;
  the explicit invariant that porting the 32 roles to another agent
  abstraction is forbidden.
- **Explicit-model + admission contract (SR-2):** how every dispatch pulls
  `model` from `governance/policies/model-allocation.md` (never trusting
  frontmatter alone); how the runner becomes the ADR-0009 admission
  gateway — what it governs (which model, under which per-dispatch budget,
  ADR-0027 SI-5) and what it does not (no routing/selection decision).
- **`run_wave` boundary (SR-3):** the exact function boundary calling
  `scripts/wave_runner.py:run_wave(plan, results)` with orchestrator-supplied
  data, preserving the ADR-0025 dispatch-equivalence guarantee; how the
  standard `run_start`/`run_end`/`span`/checkpoint/attestation stream
  (ADR-0023/0024/0031/0032) is reused, not forked by a second producer.
- **Board/git-law boundary (SR-4):** confirm the runner reads/writes
  `board/tickets/*.md` exactly as `/daslab-cycle` does; a code-touching ticket
  still requires a worktree/branch/PR; the runner must not merge its own PR.
- **Auth + budget/credit design:** the Claude-account/OAuth authentication
  path (Q9, distinct from an API-key path); how the monthly subscription
  credit composes with the `mustaqil:` per-run/per-day caps already landed in
  `config/budgets.yaml` (DAS-1543); the sanctioned-pause behaviour on credit
  exhaustion (idle + alert, resume on refresh, never a crash or false-green).
- **Isolation note:** the SDK reads host-level config regardless of
  `setting_sources` (ADR-0034's own accepted risk) — design the explicit
  `env`/`cwd` isolation the runner sets so a headless dispatch cannot leak or
  inherit host-level state across concurrent runs.

Security Lead consulted (accountable stage owner = CTO; responsible =
backend-em) — the same posture ADR-0034 itself calls for on this "second
runtime surface to maintain and secure."

## Acceptance criteria
- [ ] Design doc under `docs/design/` covering the SDK call shape, the explicit-model + admission-gateway contract, the `run_wave` call boundary + event/attestation reuse, the board/git-law boundary, and the auth/budget/credit-ceiling integration — each traced to its FR and ADR-0034 SR invariant.
- [ ] Explicit `env`/`cwd` isolation design so concurrent headless dispatches cannot leak host-level state (ADR-0034 accepted risk).
- [ ] Negative-path behaviour specified for SC-002 (missing-model dispatch rejected before the model call) and SC-004 (budget-breach / credit-exhaustion → idle+alert / sanctioned pause) so DAS-1557 can test it.
- [ ] Security Lead review recorded. `board_lint`/`check_spec_consistency` green. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Design). SR-1..SR-4 call-shape + admission +
run_wave-boundary + auth/budget design, per ADR-0034 and SPEC-003.
