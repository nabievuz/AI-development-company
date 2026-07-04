---
id: DAS-1457
title: ORGANISM WS3 — BRIDGE cost evidence and shadow-rule (slice 2)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws3-slice2
created: 2026-07-03
updated: 2026-07-03
---

## Description

**EPIC.** This ticket completes **WS3 — BRIDGE** (observability & cost) of Program ORGANISM,
delivering the **second and final slice** and killing the remainder of capability gaps
**G5 (telemetry)** and **G6 (cost)**. It re-derives the cost-ledger (P12) and committed-evidence
(P13) patterns, adds cost alerting, and formalizes the ADR-0011 Phase-1 shadow-rule supersession
that ORGANISM's now load-bearing dispatch events forced.

**Spec-of-record:** `docs/research/ORGANISM-PROGRAM-PLAN.md` — §4 "WS3 — BRIDGE" table, rows
**O3-T04** (cost-ledger P12), **O3-T05** (alerting), **O3-T06** (committed evidence P13). Companion
release-gate rows in §8: criterion **#7** ("100% dispatches emit valid spans; cost reconciles") and
the informational→hard-gate promotion of the cost metric per §9 default #6.

### Why now / embedded context

**Slice 1 already delivered the substrate** this slice builds on: the dispatch **emitter seam**
(`scripts/dgox/dispatch_emitter.py`) now emits `run_start` / `run_end` / `span` events per ticket at
`/daslab-cycle` step 5, and `scripts/metrics_lib.py` / `scripts/wave_kpi.py` compute **real** T1/T3/T4/T6
numbers from those spans (no longer "false green"). Each span already carries `in/out tokens`, `cached`,
`tier`, `status`, `duration`, and the OTel GenAI attribute names fixed in ADR-0024 (span schema).

**This slice adds three things on top of those spans:**
1. **Token/cost accounting** — a `cost_ledger` that aggregates per ticket / agent / tier / run from the
   already-emitted span token counts and a new `config/budgets.yaml`.
2. **Committed evidence** — because `board/.events.jsonl` and `board/runs/` are **gitignored** (Risk #8
   in the plan), a run's KPI + span aggregates must be snapshotted into a **separately tracked** artifact
   (`metrics/evidence/<run_id>.json`) so the §5/§8 v2.0 contract is auditable in git history.
3. **Cost alerting** — an alert that fires on `budgets.yaml` threshold breach, exposing a per-run budget
   governor that WS4 (HEARTBEAT) will later consume.

**Plus one governance closure.** ORGANISM made dispatch events **load-bearing** for operator-invoked
recovery (resume/kill-drill), which the original **ADR-0011 Phase-1 shadow-rule** treated events as
best-effort / shadow-only. That assumption is now superseded and must be **formally recorded** as an ADR
(ADR-0025 in this slice's numbering) rather than left as an implicit drift.

**Approved §9 default #6 (binding for this slice):** the new **cost metric is INFORMATIONAL-first**
(same posture as T6 review-efficiency) — it is added to `metrics/registry.yaml` as informational, and is
**promoted to a hard gate only after one clean window**. Do not wire the cost metric as a blocking gate in
this slice.

### Extend-vs-new posture (do not duplicate)

- **NEW files:** `scripts/cost_ledger.py`, `scripts/alerting.py`, `config/budgets.yaml`,
  `metrics/evidence/` (tracked dir + `.gitkeep`), the ADR file, and (per §5 ADR list) a registry entry.
- **EXTEND, never fork:**
  - `scripts/wave_kpi.py` / `scripts/metrics_lib.py` — the **single `read_events()` source of truth**;
    cost aggregation reads span token fields already parsed there. Do not add a second events reader.
  - `metrics/registry.yaml` — add the cost metric entry (informational) beside existing T1–T7.
  - `scripts/check_metric_gaming.py` — extend to **require** an evidence file for a counted run.
  - `docs/adr/README.md` — append the ADR index row.
- **REUSE the anti-gaming contract verbatim:** counted work still needs `merged_pr` + green `ci_status`
  + `t7_pass` (plan §4 WS3 constraints, R-9 binding). Events are **append-only**; corrections are
  compensating events; `created_at` is always caller-supplied. **The T7 rubric is immutable** — do not edit it.

### Key existing files (paths)

- `docs/research/ORGANISM-PROGRAM-PLAN.md` — spec-of-record (§4 WS3, §8 rows 6/7, §9 #6, Risk #8).
- `scripts/dgox/dispatch_emitter.py` — slice-1 emitter (producer of `run_start`/`run_end`/`span`).
- `scripts/dgox/events.py` — typed event builders/validators + `_VALID_EVENT_TYPES`.
- `scripts/wave_kpi.py` — `read_events()` + `busy_fraction_from_events`; natural home to sum tokens/cost.
- `scripts/metrics_lib.py` — de-facto schema; reads span token/status fields.
- `metrics/registry.yaml` — T1–T7 metric registry (add informational cost entry here).
- `scripts/check_metric_gaming.py` — anti-gaming validator (extend to require evidence).
- `docs/adr/README.md` — ADR index (append row).
- `governance/policies/ai-agent-lifecycle.md` — AADL gate definitions (this epic is stage-gated; GATE-3
  Development / GATE-4 Testing owners per §1 table: cto Accountable dev, qa-lead Accountable test).

### Children (this epic's PR-sized tickets)

- **DAS-1458** — ADR-0025 shadow-rule supersession (formalize ADR-0011 Phase-1 → events load-bearing).
- **DAS-1459** — cost-ledger (`scripts/cost_ledger.py` + `config/budgets.yaml` + informational registry entry).
- **DAS-1460** — committed-evidence (`metrics/evidence/<run_id>.json`; `check_metric_gaming` requires it).
- **DAS-1461** — cost alerting (`scripts/alerting.py`; budget-breach alert + per-run governor for WS4).

## Acceptance criteria

Epic is `done` when **all children (DAS-1458–1461) are `done`** and the following hold — this is the
**full WS3 AADL-gate closure across both slices**:

- [ ] **ADR-0025 merged** — records the ADR-0011 Phase-1 shadow-rule supersession (dispatch events are now
      load-bearing for operator-invoked recovery); a row is appended to `docs/adr/README.md`.
- [ ] **Cost-ledger** (`scripts/cost_ledger.py`) aggregates token + $ per **ticket / agent / tier / run**,
      and its totals **reconcile exactly with the span token sums** read via the single `read_events()`
      source of truth (no independent second reader).
- [ ] **`config/budgets.yaml`** exists with per-run / threshold budget entries consumed by the ledger and alerting.
- [ ] **Cost metric added to `metrics/registry.yaml` as INFORMATIONAL** (not a hard gate); it is **not**
      wired to block a wave in this slice (promotion to hard gate is deferred to one clean window per §9 #6).
- [ ] **Committed evidence** — each run snapshots its `wave_kpi` + span aggregates (redacted) into a
      **tracked** `metrics/evidence/<run_id>.json`; `metrics/evidence/` is committed (not gitignored, unlike
      `board/.events.jsonl` / `board/runs/`).
- [ ] **`check_metric_gaming.py` requires an evidence file** — a run **without** a committed evidence file
      **fails** the gate (verifiable: remove the evidence file → gate red; restore → green).
- [ ] **Cost alerting** (`scripts/alerting.py`) fires a **cost-breach alert** when `budgets.yaml` thresholds
      are exceeded, and exposes a **per-run budget governor** shape that WS4 can consume.
- [ ] **Anti-gaming preserved** — counted work still requires `merged_pr` + green `ci_status` + `t7_pass`;
      events remain append-only; the T7 rubric is unchanged.
- [ ] **§8 release-gate criterion #7 verifiable** — 100% of dispatches emit well-formed spans **and** cost
      reconciles against span sums (both slices considered together).
- [ ] **`diagnostics.py` stays 100/100** (all 8 buckets PASS) after the slice lands.
- [ ] **QONUN scope clean** — org-engine ticket: **no `project:` field** on any ticket (board_lint R9), no
      files created under `projects/`, all new files inside the engine tree.
- [ ] **AADL gate log updated** — WS3 epic note records GATE-3 (Development) and GATE-4 (Testing) checklists
      closed per `governance/policies/ai-agent-lifecycle.md` §1.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS3 slice-2 decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Orchestrator (/daslab-run)
Epic closed — WS3 BRIDGE now COMPLETE (both slices). Slice-2: ADR-0025 shadow-rule supersession (events load-bearing, principled shadow test); cost_ledger.py (P12, informational, reconciles with span sums); committed-evidence metrics/evidence/<run_id>.json (P13, tracked+redacted, check_metric_gaming requires it); alerting cost-breach + budget_governor. Children DAS-1458/1459/1460/1461 all done.
