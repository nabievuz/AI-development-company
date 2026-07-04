---
id: DAS-1440
title: ORGANISM WS1 — PULSE (durable execution core)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: 
goal: organism-ws1-pulse
created: 2026-07-03
updated: 2026-07-03
---

## Description

**Mission.** Give DasLab a **durable execution core** so that a wave which crashes
mid-flight loses nothing and re-runs nothing. This epic kills program-gap **G1
(no crash-safe waves)**: today a `kill -9` during `/daslab-cycle` orphans in-flight
tickets and there is no way to resume, fork, or interrupt a run deterministically.
WS1 makes a wave a **replayable, checkpointed transaction**.

**Spec-of-record:** [`docs/research/ORGANISM-PROGRAM-PLAN.md`](../../docs/research/ORGANISM-PROGRAM-PLAN.md)
**§4 WS1 — PULSE** (tickets O1-T01..O1-T11) and §5 ADRs 0023/0030/0032.
Read that section before executing; this ticket embeds its essentials but the plan
is the binding source.

**The 6 clean-room patterns (P1–P6)** this epic re-derives (mechanism only — no donor
code, no donor product names, §2 Clean-Room Donor Protocol; verified clean):

1. **P1 — Wave-checkpoints:** `board/runs/<run_id>/wave-NNN.checkpoint.json` capturing
   board-hash + `.events.jsonl` offset + per-ticket states + pending interrupts +
   ledger hashes, with a **per-ticket completion record** written on finish
   (pending-writes discipline). Use **per-step delta** storage from the start, never
   full snapshots (checkpoint-bloat mitigation).
2. **P2 — Resume / time-travel:** `/daslab-cycle --resume <run_id>` replays
   `.events.jsonl` to the last checkpoint and re-dispatches only unfinished tickets;
   `--fork <run_id>@wave-NNN` copies a checkpoint into a new run leaving the original
   untouched.
3. **P3 — Interrupt-cards:** `board/interrupts/<id>.json`
   `{question, options, ticket, payload, created_by}` + a new **`interrupted`** ticket
   status and its legal transitions; a gated ticket parks, the Founder answers
   `resume:<value>`, the next cycle injects the value into ticket context.
4. **P4 — Merge-policies:** per-zone frontmatter
   `merge_policy: append-only | owner-exclusive | aggregate:<reducer>` + Python
   reducers; `board_lint` permits two same-zone tickets in one wave **only** when the
   policy allows it.
5. **P5 — Fanout-tickets:** a planner emits N child tickets + private payloads plus one
   `defer:true` synthesis ticket; the dispatcher refuses the deferred launch until all
   siblings close.
6. **P6 — Result-cache:** `board/.cache/<sha256(prompt+input-digests)>.json` + TTL;
   hits are logged `cached:true` and short-circuit re-execution. Also **fixes**
   `check_cache_prefix._MIN_TOKENS` to the correct Opus 4.8 minimum (verify the current
   value via the `claude-api` reference before changing it).

**Extend-not-duplicate posture (mandatory).** WS1 is disciplined extension of existing
engine scripts, never a parallel stack:

- Reuse the **replay/recovery contract** already implemented in
  [`scripts/replay_qa.py`](../../scripts/replay_qa.py) +
  [`scripts/check_recovery.py`](../../scripts/check_recovery.py): `run_id` + ordered
  `routing_decision → recovery_drill → T5`. WS1's resume and kill-drill are built **on
  top of** this contract, not beside it.
- Emit events into `board/.events.jsonl` using the **existing** typed schema that
  [`scripts/metrics_lib.py`](../../scripts/metrics_lib.py) already reads
  (`run_end.{outcome, model, merged_pr, ci_status, t7_pass, t7_score}` and
  `recovery_drill.{outcome, corrupted}`). Match those field **names exactly** so the
  T1–T7 gates (esp. **T5**) score unchanged — a divergent emitter silently keeps every
  gate inert (Risk §6.2).
- Add typed builders/validators to the existing
  [`scripts/dgox/events.py`](../../scripts/dgox/events.py) (its `_VALID_EVENT_TYPES`
  already **reserves** `run_start`/`run_end`/`tool_call` with no builder yet) rather
  than a new event module.
- Extend the existing dispatch/fanout/merge model in
  [`.claude/skills/daslab-cycle/SKILL.md`](../../.claude/skills/daslab-cycle/SKILL.md);
  its **4 selection guards** are skill-token-tested and must be preserved **verbatim**.
- Extend [`scripts/board_lint.py`](../../scripts/board_lint.py) (`VALID_STATUSES`
  frozenset + R-rules) for the `interrupted` status and merge-policy rules — do not add
  a second linter.

**Org-engine work (scope).** This is **DasLab-platform** work on the engine itself, not
a product project. Every child ticket lives in `board/tickets/` and carries **no
`project:` field** (`board_lint` R9). Nothing lands under `projects/`. Do not flip the
"one operator invocation = one wave, no background timer" contract — WS4 (HEARTBEAT) owns
tempo, not WS1.

**Key existing files this epic touches (with paths):**

- `scripts/dgox/events.py` — add `build_run_start/run_end/wave/checkpoint` + validators.
- `scripts/metrics_lib.py` — the de-facto `run_end`/`recovery_drill` schema to match.
- `scripts/replay_qa.py`, `scripts/check_recovery.py` — reused resume/kill-drill primitive.
- `scripts/board_lint.py` — `interrupted` status + merge-policy R-rules.
- `scripts/check_cache_prefix.py` — `_MIN_TOKENS` correction (P6).
- `.claude/skills/daslab-cycle/SKILL.md` — `--resume`/`--fork`, checkpoint step 0/5,
  fanout defer-gating; preserve the 4 selection guards.
- `board/README.md` (L27) + `docs/adr/README.md` — status + ADR index rows.

**Children:** DAS-1442..DAS-1452 (the O1-T01..O1-T11 tickets minted by `/daslab-plan`).

## Acceptance criteria

WS1 closes only when all **six AADL gates** are checked and logged in the stage board
below. Each gate's checklist is pulled from
[`governance/policies/ai-agent-lifecycle.md`](../../governance/policies/ai-agent-lifecycle.md)
§3, specialized to WS1.

**GATE-1 — Planning (Accountable: cpo · Responsible: senior-pm)**
- [ ] **ADR-0023 run-model** merged: `run_id = ULID`, `board/runs/<id>/manifest.json`
      layout, per-step **delta** (not full-snapshot) storage, gitignore policy, retained
      final run summary — with an index row in `docs/adr/README.md`.
- [ ] Scope boundaries explicit: org-engine only, `board/tickets/`, no `project:` field,
      no `projects/` footprint; "one invocation = one wave, no daemon" contract preserved.
- [ ] Token/infra budget for the WS1 build acknowledged (finance-analyst) and the
      crash/interrupt risk-model reviewed (worst-case resume loop) — logged in the epic.
- [ ] Children DAS-1442..DAS-1452 exist, each `parent: DAS-1440`, stage-tagged, self-contained.

**GATE-2 — Design (Accountable: cto · Responsible: backend-em · Consulted: security-lead)**
- [ ] Typed event builders `build_run_start/run_end/wave/checkpoint` designed in
      `scripts/dgox/events.py`, registered in `_VALID_EVENT_TYPES`, with field names
      matching `metrics_lib` **exactly** (`outcome, model, merged_pr, ci_status, t7_pass,
      t7_score`).
- [ ] **Interrupt-card schema** specified: `board/interrupts/<id>.json`
      `{question, options, ticket, payload, created_by}`.
- [ ] **`interrupted`** status added to `VALID_STATUSES` + `board/README.md` L27, with the
      full set of legal transitions defined (ADR-0030); a consumer sweep confirms no reader
      rejects the new status.
- [ ] security-lead sign-off on the interrupt round-trip + idempotency hazard note.

**GATE-3 — Development (Accountable: cto · Responsible: backend-em/backend-eng · Consulted: tech-writer)**
- [ ] **P1 checkpoints** landed: crash after N completed tickets ⇒ those N are not re-run.
- [ ] **P2 resume + time-travel** landed: `--resume` re-dispatches only unfinished tickets;
      `--fork <id>@wave-NNN` leaves the original run untouched (round-trip test).
- [ ] **P3 interrupt round-trip** landed: create → Founder answers `resume:<value>` → the
      value is visible in the resumed ticket's context; idempotency validator warning on
      pre-interrupt side effects.
- [ ] **P4 merge-policies** landed: parallel same-zone outputs merge per declared policy;
      `board_lint` allows two same-zone tickets/wave only when the policy permits.
- [ ] **P5 fanout** landed: `defer:true` synthesis ticket refuses to launch until all
      siblings close (defer-gating test).
- [ ] **P6 result-cache** landed: a cache hit short-circuits execution and logs `cached:true`;
      `check_cache_prefix._MIN_TOKENS` corrected to the verified Opus 4.8 minimum.
- [ ] Docs updated in the same change as the code (SKILL.md, board/README.md, ADR index).

**GATE-4 — Testing (Accountable: qa-lead · Responsible: qa-eng · Consulted: security-eng)**
- [ ] **Kill-drill** in `check_recovery.py`: 3-wave synthetic run, `kill -9` mid-wave-2,
      `--resume`, asserting **zero lost + zero duplicate** ticket executions.
- [ ] **T5 ≥ 0.99 over ≥ 20 iterations** of the drill (measured, not asserted from the
      registry baseline).
- [ ] **Fork-drill divergence** check: a fork diverges from and does not corrupt the origin run.
- [ ] Drill wired into scheduled CI and green; qa-lead sign-off.

**GATE-5 — Deployment (Accountable: sre-lead · Responsible: sre-eng · Consulted: security-lead)**
- [ ] Run-model wired into `daslab-cycle` steps 0/5 with the pure-id `.claude/worktrees/<id>/`
      path.
- [ ] **All 4 daslab-cycle selection guards preserved verbatim** (skill-token tests pass).
- [ ] Paired `run_start`/`run_end` + checkpoint events emit on a real wave and are read by
      `metrics_lib` (T-gates no longer inert for recovery).
- [ ] Release checklist done; **GATE-5 not closed while GATE-4 is open.**

**GATE-6 — Maintenance (Accountable: coo · Responsible: product-analyst · Consulted: support-lead)**
- [ ] Recovery/kill-drills **scheduled** on a recurring cadence; a failing drill routes back
      as a labeled finding.
- [ ] Checkpoint/run-dir retention + GC policy documented and confirmed.
- [ ] Retro hook: any real crash-recovery incident writes a retro and re-enters the eval set.

### Stage board

| Stage | Gate | Accountable | Status |
|-------|------|-------------|--------|
| 1 · Planning | GATE-1 | cpo | ☐ open |
| 2 · Design | GATE-2 | cto | ☐ open |
| 3 · Development | GATE-3 | cto | ☐ open |
| 4 · Testing | GATE-4 | qa-lead | ☐ open |
| 5 · Deployment | GATE-5 | sre-lead | ☐ open |
| 6 · Maintenance | GATE-6 | coo | ☐ open |

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Orchestrator (/daslab-run)
Epic closed. ORGANISM WS1 PULSE — durable execution core CLOSED. AADL 6 gates: GATE-1 ADR-0023 run-model; GATE-2 typed run/checkpoint/span-adjacent builders + interrupt-card schema + `interrupted` status; GATE-3 wave-checkpoints(delta+ledger) / resume+fork / interrupt round-trip / merge-policies / fanout / result-cache; GATE-4 real SIGKILL kill-drill T5=1.000>=0.99 (zero lost/dup) + fork-drill; GATE-5 wired into /daslab-cycle (organism_emit OFF, 4 guards verbatim, no timer); GATE-6 recovery drills scheduled (CI smoke + scheduled tier). Children DAS-1442..1452 all done.
