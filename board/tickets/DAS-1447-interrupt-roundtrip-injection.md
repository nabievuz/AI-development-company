---
id: DAS-1447
title: Interrupt round-trip — dispatch injection + idempotency guard (P3)
status: done
assignee: backend-em
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1446]
zone: daslab-cycle
created: 2026-07-03
updated: 2026-07-03
---

## Description

**AADL stage: GATE-3 (Development).** This ticket wires the *interrupt
round-trip* into the `/daslab-cycle` dispatch loop so a gated ticket can pause,
collect a Founder answer, and resume with that answer injected into its context.

### What & why

Today `/daslab-cycle` skips a ticket that is blocked on external/Founder input
(see `.claude/skills/daslab-cycle/SKILL.md` step 3, "Blocker-first" and the
`clarify-blocked` / gate-blocked handling). There is no mechanism for the
Founder to *answer* a paused ticket and have the next wave resume it with that
answer. This ticket adds that closed loop:

1. A ticket that hits a gate enters an **`interrupted`** state (it carries the
   interrupt-schema fields defined by DAS-1446 — this ticket's `depends_on`).
2. The **Founder writes `resume:<value>`** into the ticket (the exact
   frontmatter/marker key is defined by the interrupt-schema from DAS-1446 —
   consume it, do not re-invent it).
3. On the **next `/daslab-cycle` wave**, the orchestrator detects the resumed
   ticket, **injects the `resume:<value>` payload into the ticket's dispatch
   context** (the dynamic tail of the subagent prompt — slot 3 "specific ticket
   text", per the prompt-cache layout in the SKILL, NEVER the stable prefix),
   and **re-dispatches** the ticket.

### Idempotency (the load-bearing constraint)

Because a ticket can be dispatched, interrupted mid-flight, and then
**re-dispatched** after the Founder answers, dispatch of an interrupted ticket
MUST be **idempotent**. Any side effect that may have already run before the
interrupt — a real merge, a spend/charge, a message/notification send — must be
safe to re-run without double-applying (double-merge, double-charge,
duplicate message). This is enforced by two lightweight controls (NOT a heavy
transactional engine):

- a **ticket-template note** instructing agents to make pre-interrupt side
  effects idempotent (guard-before-act: check-if-already-done, use an
  idempotency key, or make the operation naturally re-runnable), and
- a **validator warning** that flags a ticket whose body describes a
  non-idempotent pre-interrupt effect (e.g. an unguarded merge/spend/send).

### Gates ALWAYS wait for the Founder

A gate is **never** auto-answered. The orchestrator must not synthesize,
default, or infer a `resume:` value on the Founder's behalf. A gated ticket
stays `interrupted` until a human Founder writes the answer. This is the
non-negotiable half of the round-trip.

### Extend-vs-new posture

**Extend, do not rebuild.** The round-trip is layered onto the *existing*
`/daslab-cycle` selection + dispatch steps — reuse the current blocker-first
skip logic, the dynamic-tail injection point, and the existing validator
plumbing. Do not fork a parallel dispatcher. This ticket consumes the
interrupt-schema produced by **DAS-1446** (its dependency) rather than defining
new state fields.

### Key existing files this touches

- `.claude/skills/daslab-cycle/SKILL.md` — the dispatch procedure. Add the
  resumed-ticket detection + `resume:<value>` injection into the dynamic tail
  (steps 3/5), and the "gates always wait for the Founder; never auto-answer"
  rule. The `zone: daslab-cycle` on this ticket is exactly this file's area.
- `scripts/board_lint.py` — the board validator. Add the **idempotency
  warning** here (or a sibling validator invoked by the same `validate` CI
  job): warn when an `interrupted`/gated ticket's body declares a
  non-idempotent pre-interrupt side effect. Follow the existing rule pattern
  (`R1`–`R9`, `lint_tickets`, the `err(...)` accumulator) — but a warning must
  NOT flip a clean board to a hard failure unless the project convention is
  fail-closed; emit it as a distinct warning line.
- The **ticket template** (the skeleton new tickets are authored from) — add
  the idempotency note so every future ticket carries the guidance.

## Acceptance criteria

- [ ] **Round-trip test:** a create → answer → resume flow is exercised end to
      end — a ticket enters `interrupted`, a Founder `resume:<value>` is written,
      and the next wave's dispatch context for that ticket **visibly contains
      the injected `<value>`** (assert the value appears in the subagent's
      dynamic-tail prompt / ticket context, not the stable prefix).
- [ ] **Idempotency note in the ticket template:** the ticket skeleton includes
      an explicit instruction that any pre-interrupt side effect (merge, spend,
      message send) must be made safe to re-run.
- [ ] **Validator warning:** `scripts/board_lint.py` (or the sibling validator
      in the same `validate` CI job) emits a warning when an interrupted/gated
      ticket describes a non-idempotent pre-interrupt effect; running it on a
      clean board still reports OK.
- [ ] **No auto-answering of gates:** the `/daslab-cycle` SKILL explicitly
      states gates are never auto-answered/defaulted/inferred by the
      orchestrator; a gated ticket stays `interrupted` until a human Founder
      writes the `resume:` value. (Verifiable by the SKILL text + a test that a
      gated-but-unanswered ticket is NOT dispatched.)
- [ ] **Consumes interrupt-schema (DAS-1446):** the resume marker/fields used
      are those defined by DAS-1446 — no new parallel state fields are invented.
- [ ] Frontmatter carries **no `project:` field** (org-engine work; board_lint
      R9), and `board_lint.py` passes on the board.

## Acceptance criteria

- [x] **Round-trip test:** a create → answer → resume flow is exercised end to
      end — a ticket enters `interrupted`, a Founder `resume:<value>` is written,
      and the next wave's dispatch context for that ticket **visibly contains
      the injected `<value>`** (assert the value appears in the subagent's
      dynamic-tail prompt / ticket context, not the stable prefix).
- [x] **Idempotency note in the ticket template:** the ticket skeleton includes
      an explicit instruction that any pre-interrupt side effect (merge, spend,
      message send) must be made safe to re-run.
- [x] **Validator warning:** `scripts/board_lint.py` emits a `WARN` when an
      interrupted ticket describes a non-idempotent pre-interrupt effect;
      running it on a clean board still reports OK (exit 0).
- [x] **No auto-answering of gates:** the `/daslab-cycle` SKILL explicitly
      states gates are never auto-answered/defaulted/inferred by the
      orchestrator; a gated ticket stays `interrupted` until a human Founder
      writes the `resume:` value.
- [x] **Consumes interrupt-schema (DAS-1446):** the resume marker/fields used
      are those defined by DAS-1446 — no new parallel state fields are invented.
- [x] Frontmatter carries **no `project:` field** (org-engine work; board_lint
      R9), and `board_lint.py` passes on the board.

## Log

### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Backend Engineer 1
Implemented the interrupt round-trip. All acceptance criteria met. Details:

**Injection mechanism** (`scripts/interrupt_roundtrip.py`):
- `parse_resume_marker(body)` — extracts `<value>` from `resume:<value>` in the ticket body (below frontmatter).
- `find_interrupt_card(ticket_id, interrupts_dir)` — locates the card whose `"ticket"` field matches; returns the lexicographically latest if multiple match.
- `validate_resume_value(value, card)` — case-sensitive exact match against `card["options"]`.
- `build_resume_injection(value, card)` — builds the dynamic-tail injection block (slot 3, after ticket body): includes Founder answer, question, options, payload, and idempotency reminder. Strictly after the last `cache_control` breakpoint — never in the stable prefix.
- `detect_resumed_tickets(board_dir, interrupts_dir)` — orchestrator entry point; returns a `ResumedTicket` list for all valid resumed `interrupted` tickets. Unanswered, invalid-value, or card-missing tickets are skipped (never auto-answered).

**Idempotency guard**:
- `warn_interrupted_idempotency()` added to `scripts/board_lint.py` — emits `WARN` (not `FAIL`) for `interrupted` tickets whose body contains unguarded side-effect verbs (merge, charge, send, notify, post, dispatch) without a guard phrase. Exit code unchanged — 0 on a clean board.
- Idempotency HTML comment added to the `## Description` skeleton in `board/README.md`.

**SKILL.md** (`.claude/skills/daslab-cycle/SKILL.md`):
- Step 3: added "Interrupted-resume detection" subsection — runs before normal priority selection; parks unanswered tickets; validates value; transitions `interrupted → in_progress`; records resume context for injection.
- Step 5c: added "Resume context injection" note — injection goes in dynamic tail slot 3, never in stable prefix.
- Bumped `CACHE_PREFIX_VERSION: v11-fanout-deferred → v12-interrupt-roundtrip`.
- Ran `python3 scripts/check_cache_prefix.py --fix` to update baseline.

**Tests** (`tests/test_interrupt_roundtrip.py`, 23 tests):
- `test_roundtrip_full` — the AC1 end-to-end test: create → answer → injected-value-visible.
- Parked (unanswered), invalid-value, and missing-card cases all reject dispatch.
- Idempotency warning: emitted for unguarded side effects, suppressed when guarded, absent on clean board.

**Validators**: `diagnostics.py` 100/100, `board_lint.py` 0 violations, `check_cache_prefix.py` exit 0, 48 tests pass (23 new + 25 existing `test_board_lint`).

Branch: `feat/das-1447-interrupt-roundtrip`. Setting `status: in_review`, routing to `backend-em`.

### 2026-07-03 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 945 pass + all validators green + combined-merge verification (events.py/SKILL union resolved). interrupt_roundtrip.py: resume-value injection (dynamic tail) + idempotency guard (board_lint WARN + template note); cache-prefix v13.
