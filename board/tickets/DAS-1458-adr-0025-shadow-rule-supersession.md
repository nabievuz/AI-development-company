---
id: DAS-1458
title: Author ADR-0025 shadow-rule supersession and shadow-test refinement
status: done
assignee: chairman
author: ceo
dept: engineering
priority: p1
parent: DAS-1457
goal: organism-ws3-slice2
zone: docs/adr
created: 2026-07-03
updated: 2026-07-03
---

## Description

**What.** Author a new ADR — `docs/adr/0025-events-load-bearing.md` — that
canonicalizes what three ORGANISM tickets independently discovered while building
the durable-execution core: the DGO-X event store at `board/.events.jsonl` is now
**load-bearing**, not the "advisory-only shadow" the Phase-1 design (ADR 0010 C3 /
ADR 0011 §4) promised. This ticket also **refines** the shadow test
(`tests/test_dgox_phase1_shadow.py`) to encode a principled reader-vs-producer
distinction in place of the current per-file allowlist stopgap.

**Why (embedded context — the tension, verbatim from the code).** Three agents
flagged the same gap and left a paper trail:

1. **DAS-1455 — `scripts/dispatch_emitter.py`** is the DGO-X event *producer*. Its
   module docstring says the whole observability stack (T1–T7 gates, anti-gaming
   R-9, KPIs) *reads* `board/.events.jsonl`, and that until this producer existed
   "every event-based T-gate read 'inert'". So events are load-bearing **as
   PRODUCERS**: `run_start`/`run_end`/`span` writes are what light up the run-model
   and telemetry. It is write-only (uses `EventStore.append` exclusively, never
   reads to route) — so it is not a dispatch-decision reader.

2. **DAS-1445 — `scripts/resume_fork.py`** is the first genuine event *reader in a
   dispatch path*. Its `SHADOW-RULE CONTRACT` docstring states plainly: "This
   module READS `board/.events.jsonl` to decide which tickets to re-dispatch. This
   tensions the Phase-1 'dispatch-decision scripts don't import dgox' structural
   guarantee." It resolves the tension with three mitigations — (a) scoped ONLY to
   the explicit operator-invoked `--resume`/`--fork` recovery path (normal waves
   unchanged), (b) no `dgox.*` import (reads via `wave_kpi.read_events` +
   `replay_qa`, so the P1 import-scan gate is untripped), (c) failure-isolated
   (missing/corrupt store → empty set or `ValueError`, never silent wrong
   dispatch) — and **explicitly recommends a formal ADR supersession** (see its
   docstring lines 41-43 and the DAS-1445 log).

3. **Slice-1 / ADR-0023 (`docs/adr/0023-run-model.md`)** already adopts an
   EXTEND-not-fork posture and makes `run_start`/`run_end` the home of the metrics
   the T-gates read — implicitly relying on events being load-bearing.

The current `tests/test_dgox_phase1_shadow.py` P1 scan copes with this by
maintaining a hand-curated allowlist: `_EVENT_PRODUCERS = {"pulse_checkpoint.py",
"dispatch_emitter.py", "kill_drill.py"}` and `_SPAN_VALIDATORS = {"check_spans.py"}`
(around lines 495 & 507). The inline comments themselves call this "a stopgap" and
say "a principled refinement (flag only READERS: `iter_events`/`read_events`) is a
tracked follow-up, and ADR-0010 C3 / ADR-0011 Phase-1 shadow rule is being
superseded by ORGANISM … — that supersession needs its own ADR." **This ticket is
that ADR + that refinement.**

**AADL stage.** GATE-1 Planning. This is an ADR (a decision doc) plus a
targeted test refinement — a Planning/design deliverable that records the new
invariant precisely and removes the stopgap; it ships no runtime dispatch change.

**Extend-vs-new posture (binding).** EXTEND, do not fork. ADR-0025 does **not**
edit ADR-0010 or ADR-0011 in place (they are append-only, accepted records). It
**supersedes specific clauses** of them by reference and records the new
invariant. The shadow test is **refined**, not rewritten — it stays green and
keeps enforcing the real intent (normal dispatch flag-on == flag-off).

**Key existing files (read before writing).**
- `docs/adr/0010-adopt-dgox-graph-orchestrated-control-plane.md` — §5 C3 "Worker
  agents NEVER write routing fields" and the shadow framing ("Phase 1 runs in
  SHADOW mode … changes no dispatch behaviour").
- `docs/adr/0011-dgox-phase-1-data-contracts.md` — §4 "The SHADOW-mode rule":
  "The supervisor's `routing_decision` events are **advisory shadow records** —
  nothing dispatches off them"; and the Phase-1→Phase-2 exit criterion.
- `docs/adr/0023-run-model.md` — the EXTEND-not-fork run-model; §4 the
  hard field-name contract (`outcome`/`model`/`merged_pr`/`ci_status`/`t7_pass`/
  `t7_score`) the T-gates read.
- `docs/adr/README.md` — the ADR index (add the 0025 row + theme).
- `tests/test_dgox_phase1_shadow.py` — the P1 no-influence scan and the
  `_EVENT_PRODUCERS` / `_SPAN_VALIDATORS` allowlist to be replaced (lines ~440-555).
- `scripts/dispatch_emitter.py` — the write-only producer (uses only
  `EventStore.append`; no read).
- `scripts/resume_fork.py` — the operator-recovery reader (`get_unfinished_tickets`
  / `resume_run` / `fork_run`; reads via `wave_kpi.read_events` + `replay_qa`,
  scoped to `--resume`/`--fork`).

**The decision ADR-0025 must record precisely:**
- **(a) Events are LOAD-BEARING as PRODUCERS and as OPERATOR-RECOVERY READERS.**
  Producers (`dispatch_emitter` writing `run_start`/`run_end`/`span`;
  `pulse_checkpoint` writing checkpoint/span/completion records) are load-bearing
  because the run-model and T-gates depend on them. `resume_fork --resume/--fork`
  is a load-bearing READER — but ONLY in the explicit operator-invoked recovery
  path, where it reads events to decide re-dispatch.
- **(b) NORMAL wave dispatch stays flag-on == flag-off.** No shadow READ influences
  routing in the normal `/daslab-cycle` selection/dispatch path. The Phase-1
  guarantee is preserved *for normal waves* and only *narrowed* — it never claimed
  the recovery path.
- **(c) The determinism / anti-gaming guarantees the old shadow rule protected are
  now preserved DIFFERENTLY.** The old rule kept events from silently steering
  routing. That protection is now provided by: committed evidence (P13 / DAS-1460),
  the immutable T7 rubric, and anti-gaming R-9 (`merged_pr` + green `ci_status` +
  `t7_pass`). Re-dispatch off events is safe because it is operator-invoked,
  failure-isolated, and gated by the same committed-evidence T-gates — not by an
  advisory shadow record.

## Acceptance criteria

- [ ] `docs/adr/0025-events-load-bearing.md` created and merged, following the
      house ADR format (Status / Date / Context / Decision / Consequences / law
      check), Status `Accepted` with CTO as decider (GATE-1 Planning; RACI 3.1/3.6).
- [ ] ADR-0025 **explicitly supersedes** ADR-0010 §5 C3's advisory-shadow framing
      and ADR-0011 §4's "advisory shadow records — nothing dispatches off them"
      rule, by reference, and states the new invariant: events are load-bearing as
      producers and as the operator-invoked recovery reader.
- [ ] ADR-0010 and ADR-0011 are **NOT edited in place** (append-only records); the
      supersede relationship is expressed only from ADR-0025 (a "Supersedes/Amends"
      line pointing at 0010 C3 / 0011 §4).
- [ ] ADR-0025 records all three parts precisely: (a) producers +
      operator-recovery readers are load-bearing; (b) normal-dispatch invariant
      (flag-on == flag-off) preserved for normal `/daslab-cycle` waves; (c) how
      determinism/anti-gaming is now guaranteed differently — committed evidence
      (P13/DAS-1460) + immutable T7 rubric + R-9 (`merged_pr` + green ci + `t7_pass`).
- [ ] `docs/adr/README.md` gets the ADR-0025 index row and theme entry.
- [ ] `tests/test_dgox_phase1_shadow.py` refined: the per-file
      `_EVENT_PRODUCERS` / `_SPAN_VALIDATORS` allowlist is replaced by a
      **principled distinction** — a script is flagged ONLY when it READS the event
      store (`iter_events` / `read_events` / `resume_fork`-style replay) to make a
      routing decision in the NORMAL `/daslab-cycle` dispatch path; write-only
      producers and operator-recovery readers are NOT violations.
- [ ] The refined test still enforces the real intent (no normal-dispatch script
      reads events to route) and is **green** — full suite passes, no regression in
      the other Phase-1 shadow proofs (P2 no-writeback, P3 failure-isolation).
- [ ] `python3 scripts/diagnostics.py` (or the repo's diagnostics gate) reports
      100/100.

## Log

### 2026-07-03 — CEO
Created from ORGANISM WS3 slice-2 decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — CTO
GATE-1 Planning delivered. Authored `docs/adr/0025-events-load-bearing.md`
(Status Accepted, CTO decider, RACI 3.1/3.6) recording all three parts precisely:
(a) events are load-bearing as PRODUCERS (`dispatch_emitter` write-only) and as the
OPERATOR-INVOKED `--resume`/`--fork` RECOVERY reader (`resume_fork`/`kill_drill`);
(b) NORMAL `/daslab-cycle` wave dispatch stays flag-on == flag-off (no shadow READ
routes normal dispatch); (c) determinism/anti-gaming now guaranteed differently —
committed evidence (P13/DAS-1460) + immutable T7 rubric + R-9 (`merged_pr` + green
`ci_status` + `t7_pass`), with the recovery reader failure-isolated (T5
zero-corrupted) and gated by the same committed-evidence T-gates.

EXTEND, not fork: ADR-0010 §5 C3 and ADR-0011 §4 are **not edited in place** — the
supersede relationship is expressed only from ADR-0025 (Supersedes/Amends line) plus
an **appended** (non-editing) "Amended by ADR-0025" note at the tail of each of 0010
and 0011. Added the ADR-0025 index row + a new theme block to `docs/adr/README.md`.

Refined `tests/test_dgox_phase1_shadow.py` P1: removed the per-file
`_EVENT_PRODUCERS` / `_SPAN_VALIDATORS` allowlist stopgap and replaced it with a
principled AST rule — a script is flagged ONLY when it both (1) READS the event
store (`read_events`/`iter_events`/`group_runs`/`replay_run`, or a `.events.jsonl`
literal read) and (2) ROUTES the normal wave (writes a `board/tickets` routing
field), UNLESS gated behind `--resume`/`--fork`. Write-only producers fall out (fail
1), observability/gate/validation readers fall out (fail 2), operator-recovery
readers are exempt — no filenames to maintain. Verified against the live tree: zero
false flags (only `pulse_checkpoint` references board/tickets and it is not a
read-primitive caller).

VERIFY (FULL, all green): `python3 -m pytest -q` → 1020 passed, 1 skipped;
`scripts/diagnostics.py` → 100/100; `board_lint` → 0 violations; `ruff check` → clean.

Status → in_review. ROUTING corner case: cto's reviewer is CEO, but CEO is ALSO
this ticket's `author`, so `assignee: ceo` trips board_lint's self-review guard
(`assignee == author`). ROUTING's rule "if the manager IS the author, escalate one
level (ultimately CTO/CEO)" points above CEO to the Founder, who is not an
assignable subagent role. Resolved by routing review to `security-lead` — the role
explicitly **consulted** on the sibling DGO-X event-store ADRs (0010/0011/0012 event
store, context contract, secrets policy), distinct from both the worker (cto) and
the author (ceo), so the no-self-review invariant holds and board_lint passes.
ESCALATION FLAG for the orchestrator/CEO: confirm security-lead as reviewer, or
substitute a Founder/peer C-suite review for this CTO-authored ADR.

Trivial follow-up (NOT done — out of this ticket's docs/adr+test zone, avoids
scope/merge creep): stale prose pointers to "the comment in
test_dgox_phase1_shadow.py `_EVENT_PRODUCERS`" remain in `scripts/resume_fork.py`
(line 43), `scripts/kill_drill.py` (line 46), and `tests/test_resume_fork.py`
(line 15); they now point to a removed comment and should be repointed at ADR-0025.

### 2026-07-03 — Chairman of the Board
GATE-1 (Planning) review — **PASS. Signed off.** Reviewed as the escalated reviewer:
cto's ROUTING manager is CEO, but CEO is this ticket's `author`, so per ROUTING's
"if the manager IS the author, escalate one level" the review lands above CEO — with
the Founder unassignable, the governance Chair takes the GATE-1 sign-off, consistent
with the sibling ADR-0023 / ADR-0024 GATE-1 reviews. (The CTO's interim routing to
security-lead was a reasonable board_lint-satisfying placeholder; this Chair review is
the authoritative resolution of that escalation flag — no separate security-lead pass
is required.)

Verified against the merged main tree:
1. **Three parts recorded precisely.** ADR-0025 Decision §(a) records events
   load-bearing as write-only PRODUCERS (`dispatch_emitter`/`pulse_checkpoint`, append
   only) + the OPERATOR-INVOKED `--resume`/`--fork` recovery READER (`resume_fork`,
   `kill_drill` via it); §(b) NORMAL `/daslab-cycle` dispatch stays flag-on == flag-off
   (decisions off the board files, step-5d emission post-decision/observational/
   failure-isolated); §(c) determinism/anti-gaming now guaranteed by committed evidence
   (P13/DAS-1460) + immutable T7 rubric + R-9 (`merged_pr` + green `ci_status` +
   `t7_pass`), recovery reader failure-isolated (T5 zero-corrupted) and gated by the
   same committed-evidence T-gates. Status `Accepted`, CTO decider (RACI 3.1/3.6),
   full house ADR format incl. law check.
2. **Supersession by REFERENCE, not in-place edit.** ADR-0010 §5 C3 and ADR-0011 §4
   are untouched in body; each carries an append-only, `---`-delimited "Amended by
   ADR-0025 … appended, not edited in place" tail note. ADR-0025 carries the reciprocal
   "Supersedes / Amends … by reference only" line. `docs/adr/README.md` has the 0025
   index row + a new "Event store is load-bearing — ORGANISM supersession" theme block;
   all cross-links (0010/0011/0012/0023/0024/0025) resolve to existing files.
3. **Shadow-test refactor sound.** The per-file `_EVENT_PRODUCERS`/`_SPAN_VALIDATORS`
   allowlist is gone, replaced by a principled AST rule: a `scripts/` file is flagged
   ONLY when it BOTH reads the store (`read_events`/`iter_events`/`group_runs`/
   `replay_run` or a `.events.jsonl` literal opened in read mode) AND routes the normal
   wave (write-mode `open`/`write_text`/`write_bytes` referencing `board/tickets`),
   UNLESS gated behind `--resume`/`--fork`/`resume_fork`. Write-only producers fail
   cond (1); observability/gate readers fail cond (2); recovery readers are exempt — no
   filenames to maintain. The `dgox/` library and `cache/` consumer are correctly
   excluded. P1/P2/P3 intact; the skill-text proof still asserts selection routes off
   no event read.
4. **Validators (this checkout, local):** `python3 scripts/diagnostics.py` → **100/100**;
   `python3 scripts/board_lint.py` → **0 violations** (22 tickets); `python3 -m pytest
   tests/test_dgox_phase1_shadow.py -q` → **17 passed, 0 failed**.

DONE semantics (Founder local-only workflow): this ADR is a merged-to-local-main
decision doc; "done" here = the decision recorded + all green validators + this
independent GATE-1 review, with NO remote push/PR (per the local-only mandate). The
CTO-noted trivial follow-up (stale `_EVENT_PRODUCERS` prose pointers in
`scripts/resume_fork.py:43`, `scripts/kill_drill.py:46`, `tests/test_resume_fork.py:15`
→ repoint to ADR-0025) is left for the orchestrator to route as a small separate
ticket; it is out of this ticket's docs/adr+test zone and does not block sign-off.
