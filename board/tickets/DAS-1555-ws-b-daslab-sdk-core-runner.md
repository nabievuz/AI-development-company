---
id: DAS-1555
title: WS-B Development — daslab_sdk core runner, loads the repo charter, calls run_wave
status: in_review
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1552
goal: mustaqil-ws-b-runner
spec: 003-mustaqil-ws-b-runner
implements: [FR-001, FR-003, FR-004]
labels: [security]
zone: daslab_sdk
depends_on: [DAS-1554]
created: 2026-07-24
updated: 2026-07-24
---

## Description

**AADL Stage 3 — Development (closes GATE-3 for WS-B, part 1).** Build the
`daslab_sdk` core runner per the DAS-1554 design.

- **SR-1:** a thin module (`daslab_sdk/`) whose entrypoint sets `cwd` = repo
  root and `setting_sources=["project"]`, loading the existing
  `.claude/agents`, skills, `CLAUDE.md`, hooks, and `.mcp.json` (ArcRift
  included) unmodified. No porting of the 32 roles to another agent
  abstraction.
- **SR-3:** the entrypoint makes no routing/selection/re-tier decision of its
  own — it calls `scripts/wave_runner.py:run_wave(plan, results)` with the
  plan/results the caller supplies, and emits the same
  `run_start`/`run_end`/`span`/checkpoint/attestation event stream a wave
  already emits (ADR-0023/0024/0031/0032) rather than forking a second
  producer.
- **SR-4:** the runner reads/writes `board/tickets/*.md` exactly as
  `/daslab-cycle` does; it does not implement its own board-mutation path.
- **Flag OFF (SR-5, shared with DAS-1556):** the runner is inert unless
  `ws_b_agent_sdk_runner` is `true`; with the flag OFF (default), calling the
  entrypoint is a documented no-op / import-only — nothing about interactive
  waves changes.

Distinct repo zone from DAS-1556 so the two Development tickets can proceed
without a same-zone wave collision.

## Acceptance criteria
- [ ] `daslab_sdk` module present; entrypoint sets `cwd`/`setting_sources=["project"]` and loads the repo's own agents/skills/`CLAUDE.md`/hooks/`.mcp.json` unmodified.
- [ ] Entrypoint calls the existing `scripts/wave_runner.py:run_wave` (no reimplementation, no second dispatch/selection logic) and emits the standard event/attestation stream.
- [ ] Board read/write path identical to `/daslab-cycle`; no new board-mutation code path.
- [ ] Feature-flagged OFF by default; flag-off behaviour is a documented no-op. `diagnostics.py` 100/100. Merged PR, green CI.

## Log
### 2026-07-24 — Senior PM
Created by `/daslab-plan` (WS-B Development, part 1). SR-1/SR-3/SR-4 core runner;
distinct zone (`daslab_sdk`) from DAS-1556 (`scripts`) for parallel wave dispatch.

### 2026-07-24 — Backend EM
**AADL Stage-3 / GATE-3 (WS-B RUNNER, part 1) — `daslab_sdk` core headless runner built, behind `ws_b_agent_sdk_runner` (OFF). LOCAL-ONLY (no commit/PR).**

Files created (footprint held to the ticket's zone):
- `daslab_sdk/__init__.py` — package + public surface re-exports.
- `daslab_sdk/contracts.py` — the typed seam (`RunnerStatus`, `TicketDispatchResult`, `WaveDispatchResult`, and the admission interface `AdmissionOutcome`/`AdmissionDecision`/`Admitter` that DAS-1556 fills). Zero SDK/scripts import at load.
- `daslab_sdk/runner.py` — the core: `dispatch_ticket`, `dispatch_wave`, `results_from_dispatches`, `build_agent_options`, `isolate_env`, `sdk_available`, `runner_flag_enabled`.
- `daslab_sdk/requirements-sdk.txt` — the OPT-IN Agent-SDK extra (kept OUT of core `requirements.txt`).
- `daslab_sdk/README.md` — documents the flag-off no-op + absent-SDK posture.
- `tests/test_ws_b_daslab_sdk_runner.py` — 18 tests, all green.

SR/FR → file + test mapping:
- **SR-1 / FR-001** (load repo's own agents; no ported-role path) → `runner.build_agent_options` pins `cwd`=`REPO_ROOT` + `setting_sources=["project"]`; no `create_agent`/ported constructor exists → `test_happy_dispatch_pins_load_shape_and_drops_metered_key`, `test_no_ported_agent_constructor_path_exists`.
- **SR-3 / FR-003** (no mechanical decision; call `run_wave`; one producer) → `runner.dispatch_wave` is a NEW CALLER of `scripts/wave_runner.py:run_wave` (never re-implemented, never a second producer) → `test_dispatch_wave_calls_run_wave_and_ledger_reconciles` (wave-ledger reconciles via `verify_wave_ledger` ⇒ one producer), `test_dispatch_wave_inherits_organism_gate_no_second_toggle` (inherits `organism_emit` gate, zero post-decision writes).
- **SR-4 / FR-004** (board canonical; no self-merge; no routing writes) → `results_from_dispatches` sets `merged_pr=None` and close-status = plan routing target (never merge-`done`); runner source carries no `gh pr merge`/`git push`/`--admin`/`git commit`/`gh pr create` path → `test_runner_has_no_self_merge_or_push_path`, `test_assembled_results_never_self_merge`.
- **SR-5 / FR-005** (flag OFF ⇒ inert; SDK opt-in ⇒ unavailable-not-broken; constructed env) → flag gate first in `dispatch_ticket`/`dispatch_wave`; `sdk_available()` via `find_spec` (never imports); `isolate_env` constructs the child env and drops metered-key vars → `test_dispatch_ticket_flag_off_is_inert_noop`, `test_dispatch_ticket_flag_off_by_default`, `test_dispatch_wave_flag_off_never_calls_run_wave`, `test_absent_sdk_is_unavailable_not_broken`, `test_isolate_env_is_constructed_not_passthrough`.
- **FR-002 (explicit model, fail-closed)** — build-time floor even though the admission verdict is DAS-1556's → absent/empty model refused before any model call → `test_missing_model_rejected_before_query`, `test_build_agent_options_rejects_empty_model`.
- **SR-2 admission (DAS-1556's)** — depended on by INJECTION (`Admitter` seam), never duplicated: no admitter wired ⇒ fail-closed refuse; a HOLD ⇒ no dispatch → `test_no_admitter_wired_is_fail_closed`, `test_admission_hold_blocks_dispatch`.

Flag-off evidence: with `ws_b_agent_sdk_runner` OFF (repo default), `dispatch_ticket`/`dispatch_wave` return `INERT_FLAG_OFF` — no SDK import, no admission, no `run_wave` call, no board/ledger write (tmp ledger never created). Interactive `/daslab-cycle` is byte-identical. Absent-SDK evidence: flag ON + `sdk_available()` False ⇒ `UNAVAILABLE_NO_SDK` clean result, no crash.

Verify (exact): `python3 scripts/diagnostics.py` = **100/100**; `python3 scripts/board_lint.py` exit **0** (180 tickets, 0 violations; the DAS-1507 body-`status` WARN is pre-existing/unrelated, non-fatal); `python3 -m pytest` = **1992 passed, 4 skipped** (my 18 included; no collateral); `ruff check daslab_sdk tests/test_ws_b_daslab_sdk_runner.py` = clean.

Notes routed to reviewer/orchestrator (not decided here):
1. **Admission wiring adapter (integration seam).** DAS-1556 landed `scripts/ws_b_admission.py` concurrently with its OWN richer `AdmissionDecision`/`AdmissionOutcome` (ADMIT/REJECTED/IDLE_AND_ALERT/SANCTIONED_PAUSE/UNAVAILABLE) and an `admit(...)` whose signature differs from this runner's `Admitter` protocol (`(*, ticket_id, role, model) -> daslab_sdk.AdmissionDecision`). The runner correctly depends on admission by injection and does NOT duplicate the budget/auth logic; a thin adapter mapping DAS-1556's outcomes to the runner's ADMIT/HOLD is a small wiring step at the integration point (DAS-1557 tests / DAS-1558 flip) — left undone to avoid a same-file collision with the concurrent `scripts/` agent.
2. **CODEOWNERS.** `daslab_sdk/` is a new top-level dir. `check_codeowners` reads git-tracked dirs, so diagnostics stays 100/100 while the package is untracked; at commit time the merger must re-run `scripts/gen_codeowners.py` (as WS-A did for `tools/`) so `/daslab_sdk/` gets its CODEOWNERS line and the drift check stays green.
3. **Live dispatch** is not exercised (needs subscription auth + flag ON) — bound on DAS-1558; the SDK boundary is injected (`query_fn`) and the SDK is an opt-in extra.

Handing to **CTO** (GATE-3 accountable) for review. Not self-merging (SR-4 / role DoD).
