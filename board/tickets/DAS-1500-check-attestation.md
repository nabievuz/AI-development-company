---
id: DAS-1500
title: Attestation validator wired into CI with a committed sample
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1497
goal: organism-ws8-attest
depends_on: [DAS-1499]
zone: attestation-gate
created: 2026-07-03
updated: 2026-07-04
---

## Description

GATE-4 of the ORGANISM ATTEST-phase. Build `scripts/check_attestation.py` — a validator that reads committed attestation records under `metrics/attestations/<run_id>.json` and verifies each is COMPLETE and internally consistent, then wire it into both the diagnostics run-check and CI as a gate step. This closes the loop opened by DAS-1499 (the end-to-end wave/attestation-emit path): DAS-1499 produces attestations; this ticket proves they are trustworthy and makes the gate BITE by committing a real sample so CI checks live data rather than sitting perma-inert.

Why: an attestation is the organism's self-certified evidence that a wave actually ran and was measured. Without a validator, a partial, tampered, or fabricated attestation could pass silently. GATE-4 makes attestations verifiable and non-optional in CI.

Extend-vs-new: this is a NEW validator script (`scripts/check_attestation.py`) plus edits to two existing files (`scripts/diagnostics.py`, `.github/workflows/ci.yml`) and a NEW committed sample under `metrics/attestations/`. It does not replace `check_metric_gaming.py` or `snapshot_evidence.py` — it composes with them (evidence presence is one of the completeness checks).

What the validator must verify for each committed attestation:
- every ticket in the attestation's plan has a `run_start` / `run_end` / span digest;
- `run_end` carries the `metrics_lib` fields;
- every counted run has committed evidence (cross-check against the evidence snapshot);
- the progress-ledger digest is present;
- the hash chain (`prev` / `self`) is intact across records.
- FAIL with exit 1 on any gap; inert-by-design (exit 0) ONLY when no attestations exist at all.

Key files/paths:
- `scripts/check_attestation.py` (new — the validator)
- `metrics/attestations/<run_id>.json` (new — committed sample, tracked)
- `scripts/wave_runner.py` (produces attestations — source of the sample, from DAS-1499's path)
- `scripts/check_metric_gaming.py`, `scripts/snapshot_evidence.py` (evidence/consistency reference)
- `scripts/diagnostics.py` (add a real RUN check; hold 100/100)
- `.github/workflows/ci.yml` (add gate step)

The committed SAMPLE attestation must be produced by `wave_runner` from a synthetic-but-real wave (the end-to-end path delivered by DAS-1499) and committed so the gate has real data to check.

## Acceptance criteria

- [x] `check_attestation.py` verifies committed attestations (completeness + hash chain); FAIL exit 1 on any gap, exit 0 only when none exist
- [x] a committed sample attestation exists (tracked) under `metrics/attestations/` so the gate has teeth in CI (not perma-inert)
- [x] wired into `scripts/diagnostics.py` as a real RUN check (100/100 held)
- [x] wired into `.github/workflows/ci.yml` as a gate step
- [x] tests: a tampered/incomplete attestation FAILS; the committed sample passes
- [x] full suite: 0 failed

## Log

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the closing self-audit.
READ: scripts/wave_runner.py, scripts/check_metric_gaming.py, scripts/snapshot_evidence.py, scripts/diagnostics.py, .github/workflows/ci.yml.
Scope+acceptance (expand; keep frontmatter exact): GATE-4. Build scripts/check_attestation.py: read committed metrics/attestations/<run_id>.json + verify each is COMPLETE and consistent — every ticket in the attestation's plan has a run_start/run_end/span digest, run_end carries the metrics_lib fields, every counted run has committed evidence, the progress-ledger digest is present, and the hash chain (prev/self) is intact. FAIL (exit 1) on any gap; inert-by-design (exit 0) only when no attestations exist. Commit a SAMPLE attestation (produced by wave_runner from a synthetic-but-real wave — from DAS-1499's end-to-end path) into metrics/attestations/ so CI has real data to check (the gate BITES, not perma-inert). Wire check_attestation into scripts/diagnostics.py (a real RUN check, keep 100/100) AND .github/workflows/ci.yml as a gate step. Tests: a tampered/incomplete attestation FAILS; the committed sample passes.
Acceptance: [ ] check_attestation.py verifies committed attestations (completeness + hash chain); [ ] a committed sample attestation exists (tracked) so the gate has teeth in CI (not perma-inert); [ ] wired into diagnostics (100/100 held) + ci.yml; [ ] tampered attestation fails, sample passes (tests); [ ] full suite 0 failed.
Constraints: org-engine, NO project: field.

### 2026-07-04 — QA Lead
GATE-4 built and verified. Delivered:
- `scripts/check_attestation.py` — fail-closed validator over committed `metrics/attestations/*.json`. Per receipt it checks: schema tag; every planned ticket has run_start/run_end/span (events_emitted == counts.dispatched == len(tickets)); the wave-open/close, ledger, and evidence mechanics fired; run_end carried the metrics_lib fields (cross-checked against each redacted evidence completion); every counted run has a committed `metrics/evidence/<run_id>.json` (via `snapshot_evidence.evidence_path`) and the attestation `evidence.digest` recomputes from those files with the counted tally matching; `ledger_digest` + `event_digest` present; and the prev/self hash chain is intact (`wave_runner.verify_attestation` self-hash recompute + `chain_errors` dangling-prev check). Exit 1 on ANY gap; inert exit 0 only when no attestations exist. REUSES wave_runner's schema/hashing/genesis + snapshot_evidence's path/vocabulary — no re-implementation.
- `scripts/gen_sample_attestation.py` — deterministic, idempotent regenerator that drives a synthetic-but-real 2-ticket wave through the REAL `wave_runner.run_wave` and commits the receipt + its two evidence snapshots. `--check` asserts the committed sample is byte-identical to a fresh regen (staleness guard).
- COMMITTED SAMPLE (tracked, gate now BITES): `metrics/attestations/01KWS8ATTEST00000000000001.json` + `metrics/evidence/01KWS8ATTEST00000000000001-DAS-900{1,2}.json`.
- Wired as a real RUN check in `scripts/diagnostics.py` (architecture dimension, `attestation-integrity`) — 100/100 held — and as a CI gate step in `.github/workflows/ci.yml` (after GATE-6 attestation).
- Tests: `tests/test_check_attestation.py` (13 tests) — committed sample PASSES + is up to date; inert on empty/absent dir; tampered counts/mechanic-flag FAIL (self-hash break); missing run_end coverage FAILS; missing committed evidence FAILS; missing ledger_digest FAILS; dangling chain (prior receipt dropped) FAILS; two-wave chain OK; corrupt JSON reported not crashed.
VERIFY (FULL, green): `pytest -q` 1680 passed / 1 skipped / 0 failed; `diagnostics.py` SCORE = 100/100; `board_lint.py` 0 violations; `ruff check scripts tests` clean; `check_attestation.py` exit 0 on committed sample; `check_metric_gaming.py` still inert-exit-0 (extra evidence files don't break it).
GIT: local-only per dispatch (STRICT no-push). Committing to the local DAS-1500 branch; NO push / NO PR.
Status → in_review; assignee → cto (reviewer per ROUTING; author is ceo — no self-review).

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1686; check_attestation.py verifies committed metrics/attestations/<run_id>.json (per-ticket run_start/run_end/span, run_end metrics fields, committed evidence, ledger digest, prev/self hash chain); fail-closed on any gap, inert only when none exist. Committed SAMPLE attestation (via gen_sample_attestation through the REAL wave_runner) so the gate BITES in CI (not perma-inert). Wired into diagnostics (architecture, 100/100 held) + ci.yml. 13 tests (tampered fails, sample passes).
