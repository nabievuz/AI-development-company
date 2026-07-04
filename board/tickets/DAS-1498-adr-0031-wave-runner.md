---
id: DAS-1498
title: Author ADR-0031 deterministic wave-runner and attestation
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1497
goal: organism-ws8-attest
zone: docs/adr
created: 2026-07-03
updated: 2026-07-04
---

## Description

**GATE-1 Planning.** Author `docs/adr/0031-wave-runner-attestation.md` to close the
final residual from the ORGANISM ATTEST-phase self-audit: the wave lifecycle event
gates (`organism_emit`) are currently *perma-inert* because the wave LIFECYCLE
MECHANICS live as SKILL prose that the orchestrator LLM is trusted to execute by
hand. Prose gates that nothing runs cannot be proven live. This ADR decides how they
get teeth.

**What/why.** Move the wave lifecycle mechanics out of SKILL prose and into a single
deterministic entry point `scripts/wave_runner.py` exposing `run_wave(plan, results)`.
The orchestrator LLM supplies the routing PLAN and collects RESULTS as *data* and
makes **no mechanical decision inside the runner** — the runner is strictly
post-decision mechanics, gated on `organism_emit`. This preserves the load-bearing
invariant from ADR-0025: **flag-on == flag-off DISPATCH DECISIONS** (the runner never
alters which tickets dispatch or to whom; it only mechanizes what happens after the
decision).

Given `(plan, results)`, `run_wave` deterministically:
- emits `run_start` / `run_end` / `span` events via `scripts/dispatch_emitter.py`;
- writes the wave checkpoint via `pulse_checkpoint`;
- invokes per-role guardrails via `guardrail_dispatch`;
- updates the progress / task-ledger;
- snapshots committed evidence via `snapshot_evidence`;
- writes a COMMITTED `WaveAttestation` to `metrics/attestations/<run_id>.json`
  (small, redacted, hash-chained to the prior attestation).

A new `check_attestation` validator gates CI on attestation completeness. Together this
makes the previously-perma-inert event gates real via (a) an end-to-end test that runs a
wave THROUGH the deterministic runner, and (b) committed attestations that CI checks.

**Residual (record honestly in the ADR):** whether the LLM actually *calls* `run_wave`
remains a compliance step — but the trust surface shrinks from a whole prose checklist to
a single call, and wave done-ness flows THROUGH that one call (no attestation → CI fails),
so non-compliance becomes detectable rather than silent.

**Extend-vs-new.** NEW ADR (0031) — it decides a new mechanism (wave_runner +
attestation) rather than amending run-model (0023) or events-load-bearing (0025); those
are referenced as the invariants it must preserve. `scripts/wave_runner.py`,
`scripts/check_attestation.py`, and `metrics/attestations/` are named as follow-on
build surfaces; this ticket is the DECISION doc only.

**Key files + paths.**
- Author: `docs/adr/0031-wave-runner-attestation.md`
- README row + theme: `docs/adr/README.md` (highest existing ADR is 0030 → you author 0031)
- Reference: `docs/adr/0023-run-model.md`, `docs/adr/0025-events-load-bearing.md`
- Reference: `.claude/skills/daslab-cycle/SKILL.md`, `scripts/dispatch_emitter.py`
- Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` + the closing self-audit
- Set ADR `assignee: chairman`.

## Acceptance criteria

- [x] `docs/adr/0031-wave-runner-attestation.md` authored, with a README row added (merge pending review)
- [x] `wave_runner` decided as the single deterministic post-decision mechanics entry point (`run_wave(plan, results)`)
- [x] flag-on == flag-off DISPATCH DECISIONS invariant explicitly preserved (runner makes no mechanical decision) — Decision §2
- [x] committed `WaveAttestation` (`metrics/attestations/<run_id>.json`, small + redacted + hash-chained) and a `check_attestation` CI gate decided — Decision §4–5
- [x] end-to-end testability + how the runner gives the event gates teeth explained — Decision §6 (a)+(b)
- [x] residual (LLM-must-call-run_wave compliance) recorded honestly, with the shrunk trust surface noted — Decision §7
- [x] ADR `assignee: chairman` set (ADR header + ticket frontmatter)
- [x] diagnostics 100/100 (verified below)

## Log

### 2026-07-03 — CEO
Created from ORGANISM ATTEST-phase decomposition (/daslab-plan, audit-closure). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md + the closing self-audit.
READ: docs/adr/README.md, docs/adr/0023-run-model.md, docs/adr/0025-events-load-bearing.md, .claude/skills/daslab-cycle/SKILL.md, scripts/dispatch_emitter.py.
Scope+acceptance (expand; keep frontmatter exact): GATE-1 Planning. Author docs/adr/0031-wave-runner-attestation.md deciding: the wave LIFECYCLE MECHANICS move from SKILL prose into a deterministic scripts/wave_runner.py (single entry point run_wave(plan, results)); the orchestrator LLM supplies the routing PLAN + collect RESULTS as DATA and makes NO mechanical decision inside the runner — so flag-on==flag-off DISPATCH DECISIONS is preserved (the runner is post-decision mechanics, gated on organism_emit). The runner deterministically: emits run_start/run_end/span (dispatch_emitter), writes wave checkpoint (pulse_checkpoint), invokes per-role guardrails (guardrail_dispatch), updates the progress/task-ledger, snapshots committed evidence (snapshot_evidence), and writes a COMMITTED WaveAttestation (metrics/attestations/<run_id>.json, small+redacted, hash-chained). A check_attestation validator gates CI on attestation completeness. This makes the previously-perma-inert event gates real by (a) an end-to-end test through the deterministic runner, (b) committed attestations checked in CI. Record the residual honestly (whether the LLM calls run_wave is still compliance, but the surface shrinks to one call + done-ness flows THROUGH it). README row + theme (highest ADR 0030 -> you author 0031). Set assignee: chairman.

### 2026-07-04 — CTO
Authored `docs/adr/0031-wave-runner-attestation.md` (Accepted, GATE-1 Planning / WS8 ATTEST O8-T01) + README index row + a "Provable waves — ORGANISM WS8 ATTEST" theme paragraph. Read all five references (0023/0025/SKILL/dispatch_emitter + 0024, snapshot_evidence) and confirmed the build surfaces are correctly absent (decision doc only): `scripts/wave_runner.py`, `scripts/check_attestation.py`, `metrics/attestations/` do not exist yet.
DECISION (6 parts): (1) `run_wave(plan, results)` is the single deterministic post-decision entry point — plan = the routing DECISION already taken, results = the collected OUTCOMES already observed; both are DATA arguments. (2) The runner makes NO mechanical decision → ADR-0025 flag-on==flag-off DISPATCH DECISIONS preserved at a function boundary; organism_emit-gated + failure-isolated; passes the ADR-0025 §(d) reader-vs-router shadow rule by property (write-only mechanics orchestrator, never reads the store to route). (3) `run_wave` REUSES the shipped primitives verbatim — `pulse_checkpoint` (open/close checkpoints + ticket-ledger), `dispatch_emitter.emit_wave` (run_start/run_end/span), `guardrail_dispatch`, `snapshot_evidence.write_run_evidence` (P13 committed evidence) — never re-implements them. (4) COMMITTED `WaveAttestation` → `metrics/attestations/<run_id>.json`: small, redacted (counts/booleans/hashes/ticket-ids only, presence-only PR/T7), tracked like metrics/evidence/, doubly hash-chained (`ledger_hashes` binds the ADR-0023 checkpoint chain; `attest_chain` links prior run's receipt, self-excluded preimage). (5) `check_attestation` CI gate mirrors `snapshot_evidence.missing_evidence_runs`/`check_metric_gaming`: completeness (every R-9 `counted_run_ids` run needs an attestation with all mechanics fired) + integrity (both chains verify + cross-check the evidence snapshot), fail-closed on counted runs, inert-by-design on an empty board (ADR-0020). (6) Teeth two ways: (a) an end-to-end test drives a synthetic wave THROUGH the clock-injected deterministic runner so CI exercises the full chain on real fixture data; (b) live waves commit attestations checked on merge.
RESIDUAL (honest, §7): whether the LLM CALLS run_wave is still compliance (runtime stays a markdown skill), but the trust surface shrinks from a ~6-paragraph prose checklist to ONE call, and done-ness flows THROUGH it — an omission leaves no committed attestation → check_attestation FAILS CI → non-compliance is detectable, not silent.
ADR authority: CTO decides (architecture RACI 3.1/3.6, as with ADR-0025); Chairman ratifies (board oversight of the org's own self-attestation mechanism). `assignee: chairman` set in both the ADR header and the ticket frontmatter.
VERIFY (full, in worktree): `python3 -m pytest -q` → 1662 passed, 1 skipped (0 failed); `scripts/diagnostics.py` → 100/100; `scripts/board_lint.py` → 0 violations (62 tickets); `scripts/check_links.py` → OK (new ADR cross-refs resolve).
Status → in_review; assignee → chairman (author is ceo — reviewer per ROUTING). Committed locally to feat/das-1498-adr-0031-wave-runner (STRICT LOCAL-ONLY; no push).

### 2026-07-04 — Chairman of the Board
GATE-1 sign-off / board ratification of ADR-0031 (deterministic wave-runner + attestation). Reviewed `docs/adr/0031-wave-runner-attestation.md` + `docs/adr/README.md` against the acceptance criteria and GATE-1. Verified all six load-bearing points:
1. `run_wave(plan, results)` is decided as the SINGLE deterministic post-decision mechanics entry point — `plan`/`results` are DATA supplied by the orchestrator LLM; the runner holds no routing/selection/model logic (Decision §1, docstring at ADR lines 100–112).
2. flag-on == flag-off DISPATCH DECISIONS preserved: dispatch decision happens entirely before/outside `run_wave`; runner is `organism_emit`-gated write-only mechanics, never reads the store to route — ADR-0025 §(d) reader-vs-router shadow rule held BY PROPERTY, no allowlist entry needed (Decision §2).
3. COMMITTED, small+redacted, doubly hash-chained `WaveAttestation` → `metrics/attestations/<run_id>.json` (tracked, NOT gitignored; `ledger_hashes` binds the ADR-0023 checkpoint chain, `attest_chain` links prior run with self-excluded preimage) + `check_attestation` CI gate deciding completeness (fail-closed on R-9 counted runs) + integrity + evidence cross-check, inert-by-design on an empty board per ADR-0020 (Decision §4–5).
4. Teeth for the perma-inert event gates recorded two ways: (a) an end-to-end test drives a synthetic wave THROUGH the clock-injected deterministic runner so CI exercises the full chain on real fixture data; (b) live waves commit attestations verified on merge (Decision §6 a+b).
5. Residual recorded HONESTLY: the LLM must still CALL `run_wave` (runtime stays a markdown skill), but trust surface shrinks from a ~6-paragraph checklist to ONE call and done-ness flows THROUGH it — omission → no committed attestation → `check_attestation` FAILS CI → non-compliance is DETECTABLE, not silent (Decision §7).
6. Numbering correct (0031, highest prior 0030); README index row (line 40) + "Provable waves — ORGANISM WS8 ATTEST" theme paragraph (line 195) present; cross-refs to 0023/0024/0025 resolve; build surfaces (`scripts/wave_runner.py`, `scripts/check_attestation.py`, `metrics/attestations/`) correctly ABSENT — decision doc only.
ONE clarity fix applied as ratifying signer (not a decision change): the `engine_version: "1.2.0"` in the WaveAttestation JSON was an unflagged illustrative value while the repo `VERSION` is authoritatively `1.0.0`. Annotated the example block as explicitly illustrative (every value a placeholder; `VERSION` file authoritative at 1.0.0; `run_wave` stamps the live value at write time) so the example cannot be misread as a version assertion.
GATES (re-run on MAIN): `scripts/diagnostics.py` → 100/100; `scripts/board_lint.py` → 0 violations (62 tickets); `python3 -m pytest -q` → 1662 passed, 1 skipped, 0 failed.
VERDICT: PASS — ADR-0031 ratified (CTO architecture decider, Chairman accountable signer). Status → done. Committed locally (STRICT LOCAL-ONLY; no push).
