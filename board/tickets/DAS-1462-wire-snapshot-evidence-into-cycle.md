---
id: DAS-1462
title: Wire snapshot_evidence into daslab-cycle run-close (WS3 activation)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1457
goal: organism-ws3-slice2
zone: daslab-cycle
created: 2026-07-03
updated: 2026-07-03
---

## Description

**WS3 activation wiring.** `organism_emit` is now ON (Founder-authorized 2026-07-03),
so `/daslab-cycle` already emits `run_start`/`run_end`/span events (DAS-1452 wired steps
0/4/5f/6). This ticket completes the observability loop: on run-close the cycle must also
write a **committed** evidence snapshot so KPI gates rest on durable, git-auditable proof.

Wire `scripts/snapshot_evidence.py` (`write_run_evidence(events, run_id, evidence_dir)`)
into `.claude/skills/daslab-cycle/SKILL.md` step 6/7 run-close: after the wave's events are
emitted for a `run_id`, call `write_run_evidence` to produce a tracked, redacted
`metrics/evidence/<run_id>.json`. Gate this on `organism_emit` (same flag as the emitter);
failure-isolated (a snapshot failure never blocks dispatch). This is the P13 producer for
the committed-evidence artifact that `check_metric_gaming.py` (DAS-1460) already requires.

**Extend, don't duplicate:** reuse `snapshot_evidence.write_run_evidence` / `snapshot_all`
and the `board/runs/<run_id>/` run-model from DAS-1444/1452. Do NOT re-implement redaction
or the evidence schema. `metrics/evidence/` is TRACKED (committed), not gitignored.

**Key files:** `.claude/skills/daslab-cycle/SKILL.md` (step 6/7 wiring — cache-prefix
region, so bump `CACHE_PREFIX_VERSION` + run `check_cache_prefix.py --fix`);
`scripts/snapshot_evidence.py` (reference — the producer); `scripts/feature_flags.py`
(`organism_emit`). **AADL stage:** GATE-5 Deployment (live-dispatch run-close wiring).

## Acceptance criteria

- [x] `/daslab-cycle` SKILL.md step 6/7 calls `snapshot_evidence.write_run_evidence` on
      run-close, gated on `organism_emit`, failure-isolated.
- [x] `metrics/evidence/<run_id>.json` is produced on a run close (tracked, redacted).
- [x] `CACHE_PREFIX_VERSION` bumped + `check_cache_prefix.py --fix` run (same commit) if the
      stable-prefix region changed; `check_cache_prefix.py` exit 0.
- [x] Emission/snapshot is post-decision + failure-isolated (flag-on == flag-off dispatch
      DECISIONS); `check_loop_mode.py` exit 0 (loop.yaml untouched).
- [x] Full suite `python3 -m pytest -q` 0 failed; `diagnostics.py` 100/100; `board_lint.py` 0;
      `ruff check scripts tests` clean.
- [x] No `project:` field (org-engine, board_lint R9).

## Log
### 2026-07-03 — CEO
Created from ORGANISM WS3 activation (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md §4 WS3 / §5 row 7.

### 2026-07-03 — Backend EM
Wired the committed-evidence producer into `/daslab-cycle` run-close.

- **SKILL.md step 6 (run-close)** — added a new bullet in the `organism_emit`-gated
  "Run-lifecycle emission + run close" block, immediately AFTER `emit_wave(records)`
  returns this run's appended events. It calls
  `snapshot_evidence.write_run_evidence(events, run_id, snapshot_evidence.EVIDENCE_DIR)`
  to write the TRACKED, REDACTED `metrics/evidence/<run_id>.json`. Reuses the existing
  producer + run-model (no re-implemented redaction/schema; no `dgox.*` import).
- **Flag-gating + failure isolation** — the whole block is already gated on
  `organism_emit` (now ON); the new step is explicitly post-decision + OBSERVATIONAL
  and wrapped in the same run-model failure isolation (a snapshot exception is caught,
  logged, and NEVER blocks the wave). Flag-on == flag-off dispatch/collect DECISIONS;
  the only difference is the committed snapshot file + gitignored event lines.
- **Cache-prefix** — step 6 sits in the stable-prefix region, so bumped
  `CACHE_PREFIX_VERSION` v14-organism-runmodel → v15-organism-evidence-snapshot and ran
  `check_cache_prefix.py --fix` (baseline `scripts/.cache_prefix_baseline` updated same
  commit). No `DAS-NNNN` literal introduced in the prefix (volatile-token clean).
- **Test** — added `test_run_close_wiring_writes_committed_evidence_file` to
  `tests/test_snapshot_evidence.py`: a run's `emit_wave` events → the exact
  `write_run_evidence(events, run_id, dir)` call the run-close makes → a committed,
  redacted `<run_id>.json` matching the run's events (and `missing_evidence_runs == []`).
- **Stale-test reconciliation** — `test_feature_flags.py::test_real_config_has_all_flags_off`
  predated the Founder-authorized `organism_emit` flip and asserted all-off; updated to
  `test_real_config_matches_live_flag_state` (organism_emit True, others False). Did NOT
  touch `config/features.yaml` or `loop.yaml`.
- **Verify (full suite, in worktree):** `pytest -q` 1083 passed / 1 skipped / 0 failed;
  `diagnostics.py` 100/100; `board_lint.py` 0; `check_cache_prefix.py` exit 0;
  `check_loop_mode.py` exit 0; `ruff check scripts tests` clean.

Committed locally to `feat/das-1462-wire-evidence` (LOCAL-ONLY, no push). → `in_review`, assignee `cto` (my manager/reviewer per ROUTING).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate + LIVE PROOF: organism_emit ON; emitted run_start/run_end/span for 5 real WS3 dispatches; check_spans 100% well-formed; T1=0.487 / T3=3.0 / T4=0.000 compute REAL numbers (false-green gone); cost-ledger real $/run; 5 committed metrics/evidence/*.json; check_metric_gaming passes WITH evidence. Full suite 1083 pass, cache v15, check_loop_mode exit 0. WS3 BRIDGE proven end-to-end.
