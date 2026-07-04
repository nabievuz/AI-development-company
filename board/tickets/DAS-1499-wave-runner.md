---
id: DAS-1499
title: Build deterministic wave_runner lifecycle shim with end-to-end test
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1497
goal: organism-ws8-attest
depends_on: [DAS-1498]
zone: wave-runner
created: 2026-07-03
updated: 2026-07-04
---

## Description

GATE-3. Build `scripts/wave_runner.py` per ADR-0031: a DETERMINISTIC
`run_wave(plan, results, *, created_at, ...)` where `plan` = the LLM's routing
decisions (per-ticket ticket/role/model/from->to) and `results` = collect data
(per-ticket outcome/merged_pr/ci_status/t7_pass/t7_score/tokens/start/end) — ALL
supplied, NO LLM inside, caller-supplied timestamps.

It deterministically:
1. opens/continues the run (manifest via `pulse_checkpoint`),
2. emits `run_start`/`run_end`/`span` per dispatch via `dispatch_emitter.emit_wave`,
3. invokes per-role input/output guardrails via `guardrail_dispatch` on the outputs,
4. writes/updates the progress-ledger,
5. snapshots committed evidence via `snapshot_evidence`,
6. writes a COMMITTED `WaveAttestation` to `metrics/attestations/<run_id>.json`
   (small, REDACTED, hash-chained: run_id, wave, ticket set, event digest,
   evidence ref, ledger digest, prev/self hashes).

Failure-isolated only for OPTIONAL steps; the emission+attestation are
load-bearing (a wave's done-ness flows through `run_wave`).

CRITICAL end-to-end TEST: a synthetic plan+results through the REAL `run_wave`
-> assert `check_spans` reports 100% coverage WITH teeth, `run_end` fields match
`metrics_lib`, `check_metric_gaming` passes with the written evidence, the ledger
validates, and the attestation is well-formed — i.e. the event-based invariants
are now enforced through a tested code path, not prose.
`metrics/attestations/` is TRACKED (not gitignored).

**Why:** the ORGANISM ATTEST phase needs a single deterministic seam through
which a wave's done-ness is emitted, guardrailed, ledgered, evidenced, and
attested — replacing prose invariants with a tested code path.

**Extend vs new:** NEW file `scripts/wave_runner.py` that composes the EXISTING
seams (`dispatch_emitter`, `pulse_checkpoint`, `snapshot_evidence`,
`guardrail_dispatch`, `task_ledger`, `check_spans`, `metrics_lib`) — do not
re-implement their logic.

**Key files/paths:**
- `scripts/wave_runner.py` (new — the shim)
- `scripts/dispatch_emitter.py` (`emit_wave`)
- `scripts/pulse_checkpoint.py` (run manifest)
- `scripts/snapshot_evidence.py` (committed evidence)
- `scripts/guardrail_dispatch.py` (per-role guardrails)
- `scripts/task_ledger.py` (progress-ledger)
- `scripts/check_spans.py` (coverage-with-teeth)
- `scripts/metrics_lib.py` (`run_end` field source of truth)
- `metrics/attestations/<run_id>.json` (tracked, hash-chained)
- `docs/adr/0031-wave-runner-attestation.md` (spec-of-record)

## Acceptance criteria

- [ ] `wave_runner.run_wave` deterministic (no LLM, caller-supplied ts)
- [ ] emits events+checkpoint+guardrails+ledger+evidence+attestation in one call
- [ ] flag-on==flag-off decisions preserved (post-decision mechanics, `organism_emit`-gated)
- [ ] end-to-end test: synthetic wave -> `check_spans` 100% w/ teeth + `run_end`/metrics match + evidence + ledger + attestation all real
- [ ] `metrics/attestations/` tracked
- [ ] full suite 0 failed, diagnostics 100/100

Produces: `wave-runner` (consumed by DAS-1500/1501/1502).

## Log

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure).
Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the closing self-audit.
READ: scripts/dispatch_emitter.py, scripts/pulse_checkpoint.py,
scripts/snapshot_evidence.py, scripts/guardrail_dispatch.py, scripts/task_ledger.py,
scripts/check_spans.py, scripts/metrics_lib.py, docs/adr/0031-wave-runner-attestation.md.

### 2026-07-04 — Backend EM
Built `scripts/wave_runner.py` per ADR-0031 and the end-to-end seam test
`tests/test_wave_runner.py`. Branch `feat/das-1499-wave-runner` (LOCAL only).

Signature (deterministic, no LLM, caller-supplied timestamps):
`run_wave(plan: WavePlan, results: WaveResults, *, created_at, store_path=None,
runs_dir=None, attest_dir=None, evidence_dir=None, tickets_dir=None,
board_dir=None, routing_path=None, guardrails_dir=None, organism_emit=True,
run_guardrails=True) -> WaveAttestation | None`. `plan` = the routing DECISION
(per-ticket ticket/role/model/from->to); `results` = collected OUTCOMES
(per-ticket outcome/merged_pr/ci_status/t7_pass/t7_score/tokens/start/end +
progress-ledger flags). Inputs validated up front (fails loud before any write).

The 6 mechanics, in ADR-0031 §3 order, REUSING the shipped primitives verbatim:
1. wave-OPEN checkpoint — `pulse_checkpoint.write_wave_checkpoint` (emit_event=False).
2. `run_start`/`run_end`/`span` per dispatch — `dispatch_emitter.emit_wave`
   (LOAD-BEARING; each dispatch gets a per-dispatch run_id for pairing/evidence).
3. per-role INPUT/OUTPUT guardrails on the collected outputs —
   `guardrail_dispatch.guardrail_dispatch` with a no-op `run_agent` that replays
   the already-collected output (OPTIONAL / failure-isolated; verdicts recorded).
4. progress-ledger (`check_ledger.write_progress_ledger`) + task-ledger
   (`task_ledger.build_task_ledger`) + per-ticket completions
   (`pulse_checkpoint.append_ticket_completion`) + wave-CLOSE checkpoint.
5. committed redacted evidence per dispatch — `snapshot_evidence.write_run_evidence`.
6. COMMITTED, redacted, doubly hash-chained WaveAttestation →
   `metrics/attestations/<run_id>.json` (run_id, wave, ticket set, mechanics
   block, counts, event_digest, evidence ref+digest, ledger_digest, ledger_hashes
   from the close checkpoint, attest_chain{prev,self} with self-excluded preimage).

End-to-end test drives a synthetic (plan, results) through the REAL run_wave to a
tmp store, asserting with TEETH: `check_spans` prints "coverage 100%" + "2
dispatch(es)"/"2 span(s)" (real, not the inert no-events path); emitted `run_end`
fields fed through `metrics_lib.model_mix` == {ratio 0.0, low 0, total 2} and
`gaming_violations` == {completions 2, violations []} (RUN_END_METRICS_FIELDS
present); `check_metric_gaming` exits 0 given the written evidence; the
progress-ledger validates via `check_ledger.validate_ledger` == []; the
attestation is well-formed, `verify_attestation` == [], first prev == genesis,
and a second wave's `attest_chain.prev` == first `self` (chain intact).

Shadow rule (ADR-0025 §d) holds BY PROPERTY — no allowlist entry: wave_runner
reads its inputs from `plan`/`results` args and writes only via the append-only
producers; it never calls a read primitive (read_events/iter_events/group_runs/
replay_run) nor opens a `.events.jsonl` literal, so it is never a reader-vs-router
violation. `test_dgox_phase1_shadow.py` P1 scans it clean; a dedicated AST test
asserts the property directly. `organism_emit=False` is a byte-clean no-op
(returns None, zero writes) — flag-on == flag-off DISPATCH DECISIONS preserved.

`metrics/attestations/` is TRACKED (added `.gitkeep`; `.gitignore` does not cover
it — `git check-ignore` confirms NOT ignored).

VERIFY (full, in worktree): `python3 -m pytest -q` → 1667 passed, 1 skipped, 0
failed; `python3 scripts/diagnostics.py` → 100/100; `python3 scripts/board_lint.py`
→ 0 violations; `python3 scripts/check_loop_mode.py` → exit 0; `ruff check scripts
tests` → clean. Committed LOCAL only (no push/PR per dispatch constraint).
Status → in_review; assignee → cto (GATE-3 review). Note: `scripts/check_attestation.py`
(the CI gate) + `.github/workflows/ci.yml` wiring are the SEPARATE downstream
tickets (DAS-1500/1501/1502) consuming `produces: wave-runner`; not in this ticket's scope.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1667; wave_runner.run_wave deterministic (6 mechanics, primitives reused); END-TO-END teeth test makes check_spans 100%/metrics/evidence/ledger/attestation REAL through a tested code path; shadow-rule clean by property; organism_emit=False byte-clean no-op (flag-on==flag-off preserved).
