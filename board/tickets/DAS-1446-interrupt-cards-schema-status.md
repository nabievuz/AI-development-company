---
id: DAS-1446
title: Interrupt-cards schema + interrupted status enum (P3)
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1440
goal: organism-ws1-pulse
depends_on: [DAS-1442]
zone: scripts/board_lint
created: 2026-07-03
updated: 2026-07-03
---

## Description

**AADL stage: GATE-2 Design.** This is a **design + schema** ticket in the ORGANISM
"Pulse" workstream (WS1). It defines how a running agent can *pause itself* and ask
the Founder a question mid-flight — an **interrupt card** — and adds a new ticket
status, `interrupted`, so a ticket can legally sit in a "waiting on a human answer"
state without being mistaken for `blocked` (external dependency) or `in_review`.

**What & why.** Today an agent that hits an ambiguous decision has only two poor
options: guess, or mark the ticket `blocked` (which the board treats as an
external-dependency stall that is never auto-dispatched). Neither captures "I need
a quick human choice to keep going." The **interrupt card** is a small JSON object
that carries a question + the answer options to the Founder; the Founder answers by
writing `resume:<value>`, and the ticket flows back into the wave. This ticket
produces the **schema + enum + transition rules + a clean consumer sweep** so that a
later implementation ticket (DAS-1447) can wire the runtime behavior on top of a
board that already accepts the new status.

**Extend-vs-new posture.** EXTEND the existing board machinery; do not fork it.
- `interrupted` is added to the SAME `VALID_STATUSES` frozenset that already holds
  `backlog | todo | in_progress | blocked | in_review | done` — one enum, one source
  of truth mirrored in `board/README.md`.
- Interrupt cards get their OWN directory `board/interrupts/` (new), parallel to
  `board/tickets/`, so they never pollute the ticket glob (`board_lint` only reads
  `DAS-*.md`) and are trivially removable.
- Do NOT invent a parallel status system, a new lint script, or a second enum copy.

**Interrupt-card object (to be documented + specified here).**
Path: `board/interrupts/<id>.json` (one file per open question), shape:
```json
{
  "question": "free-text prompt shown to the Founder",
  "options": ["option-a", "option-b", "..."],
  "ticket": "DAS-####",
  "payload": { "arbitrary": "agent context needed to resume" },
  "created_by": "<role-key>"
}
```
The Founder answers by writing `resume:<value>` (where `<value>` is one of `options`)
— the exact write target/mechanism is specified by DAS-1447 (consumer), but the
answer contract (`resume:<value>`) is fixed HERE.

**Legal status transitions (recommended, to be documented as the design of record):**
- `in_progress` → `interrupted` — agent raises an interrupt card and yields.
- `interrupted` → `in_progress` — Founder supplies `resume:<value>`; the ticket
  re-enters the wave with the answer available to the agent.
- `interrupted` → `blocked` — the question is abandoned / cannot be answered; the
  ticket falls back to the normal blocked path (requires a log reason, per board rules).

**Key existing files this ticket touches (with paths):**
- `scripts/board_lint.py` — line ~46-48 `VALID_STATUSES` frozenset (add `interrupted`);
  R8 `in_review == author` check at lines ~181-186 (verify it does not touch, reject,
  or strand an `interrupted` ticket — R8 keys off `status == "in_review"`, so an
  `interrupted` ticket is out of its scope; confirm and record this).
- `board/README.md` — **line 27**, the status enum comment
  `# backlog | todo | in_progress | blocked | in_review | done` (add `interrupted`),
  plus the Rules section (~line 73+) if a transition note is warranted.
- `board/ROUTING.md` — the `in_review` reviewer-routing logic (verify `interrupted`
  does not get mis-routed to a reviewer; `interrupted` has no reviewer semantics).
- `/daslab-cycle` triage (the cycle skill / orchestrator) — verify triage neither
  auto-dispatches an `interrupted` ticket as actionable work nor strands it; an
  `interrupted` ticket is NOT actionable until it becomes `in_progress` again via
  `resume:<value>`. Document the intended triage handling.

**Consumer sweep (mandatory).** Enumerate every place that reads ticket `status` and
state, for each, exactly how it treats `interrupted`:
1. `board_lint.py` R2 status-enum check — now accepts `interrupted` (the add).
2. `board_lint.py` R8 in_review self-review check — untouched (scoped to `in_review`).
3. `/daslab-cycle` triage / actionability — `interrupted` is non-actionable (parked),
   not dispatched, not treated as `blocked`.
4. `board/ROUTING.md` in_review routing — `interrupted` is not routed to a reviewer.
No consumer may reject a validly-formed `interrupted` ticket or silently drop it.

**Spec-of-record:** `docs/research/ORGANISM-PROGRAM-PLAN.md`.
**Constraint:** this is org-engine (platform) work — the frontmatter carries NO
`project:` field (board_lint R9). **Produces:** `interrupt-schema` (consumed by DAS-1447).

## Acceptance criteria

- [x] Interrupt-card JSON schema is documented (fields `question`, `options`,
      `ticket`, `payload`, `created_by`; path `board/interrupts/<id>.json`; the
      `resume:<value>` answer contract stated). → `board/interrupts/README.md` +
      `board/interrupts/schema.json` (JSON Schema draft 2020-12).
- [x] `interrupted` is added to `scripts/board_lint.py` `VALID_STATUSES`.
- [x] `interrupted` is added to the status enum on `board/README.md` **line 27**
      (and any other enum echo in that file kept in sync).
- [x] Legal transitions are documented: `in_progress`→`interrupted`;
      `interrupted`→`in_progress` (via `resume:<value>`); `interrupted`→`blocked`
      (abandoned). → `board/interrupts/README.md`, `board/README.md` Rules,
      and a comment on `VALID_STATUSES` in `board_lint.py`.
- [x] Consumer sweep is complete and written down — each consumer listed with how it
      handles `interrupted`: (1) board_lint R2, (2) board_lint R8, (3) /daslab-cycle
      triage, (4) ROUTING in_review logic — none rejects or strands an `interrupted`
      ticket. → `board/interrupts/README.md` §Consumer sweep.
- [x] `board_lint` accepts a well-formed `interrupted` ticket (a sample/fixture
      ticket with `status: interrupted` lints clean, exit 0). →
      `test_load_tickets_interrupted_file` (end-to-end via `load_tickets`).
- [x] Tests cover the new status: a positive case (`interrupted` accepted) and a
      negative case (an unknown/invalid status still rejected) pass. →
      `test_interrupted_status_accepted`, `test_unknown_status_still_rejected`,
      `test_interrupted_not_subject_to_self_review_r8` (25 passed).

## Log
### 2026-07-03 — CEO
Created from ORGANISM program-plan decomposition (/daslab-plan). Spec-of-record: docs/research/ORGANISM-PROGRAM-PLAN.md.

### 2026-07-03 — Security Lead
Built P3 interrupt-cards schema + `interrupted` status (GATE-2 Design). Extended
existing machinery, did not fork it.

**Schema.** New `board/interrupts/` dir (parallel to `board/tickets/`, outside the
`DAS-*.md` glob). `board/interrupts/README.md` = design-of-record: object shape
`{question, options, ticket, payload, created_by}` at path
`board/interrupts/<id>.json`, the `resume:<value>` answer contract (`<value>` ∈
`options`; exact write mechanism deferred to DAS-1447), and the legal transitions.
`board/interrupts/schema.json` = machine-checkable JSON Schema (draft 2020-12) for
the DAS-1447 consumer. Nothing reads the schema yet — additive only.

**Enum (single source of truth).** Added `interrupted` to `VALID_STATUSES` in
`scripts/board_lint.py` (with a transition-doc comment) AND to the enum comment on
`board/README.md` line 27 — one enum, mirrored. Added an `interrupted` rule bullet
to the board Rules section.

**Legal transitions (design of record):** `in_progress`→`interrupted` (agent raises
card, yields); `interrupted`→`in_progress` (Founder `resume:<value>`, re-enters
wave); `interrupted`→`blocked` (abandoned; needs a log reason).

**Consumer sweep (all 4 clean — no consumer rejects or strands an `interrupted`
ticket):** (1) board_lint R2 status-enum → now ACCEPTS it. (2) board_lint R8
in_review self-review → UNTOUCHED, keys off `status == "in_review"` only (added a
docstring note + a regression test). (3) `/daslab-cycle` triage → `interrupted` is
NON-actionable (not in the `p0`→`in_review`→`in_progress`→`todo` selection order),
so it is parked, not dispatched, not treated as `blocked`; the step-2 in_review
reassignment guard does not touch it. (4) `board/ROUTING.md` in_review reviewer map
→ NO reviewer semantics for `interrupted`, never routed to a reviewer. Documented in
`board/interrupts/README.md` §Consumer sweep and in the board Rules bullet.

**Tests (tests/test_board_lint.py, 25 passed):** positive `test_interrupted_status_accepted`;
end-to-end `test_load_tickets_interrupted_file`; R8-scope `test_interrupted_not_subject_to_self_review_r8`;
negative `test_unknown_status_still_rejected` (enum stays closed — a typo status is
still rejected); updated `test_valid_statuses_are_accepted` to include `interrupted`.

**Validators (all green):** `board_lint` 0 violations (17 tickets); `check_never_auto_approve`
clean (17 tickets — re-run as required for a governance/validator change);
`pytest tests/test_board_lint.py` 25 passed; `diagnostics` 100/100.

Committed LOCAL-ONLY to `feat/das-1446-interrupt-schema` (no push/PR per ORGANISM
LOCAL-ONLY git strategy). This is security/governance-touching → set `in_review`,
assignee `cto` for a CTO review in the next wave (no same-wave compression, per the
cycle security guard). Produces `interrupt-schema`, consumed by DAS-1447.

### 2026-07-03 — CTO (blocking security review — PASS)
Reviewed the full `git diff main` as security reviewer (LAW 2, no compression —
this touches the status enum + a validator). **Verdict: PASS → done.** Note:
LOCAL-ONLY build, so "done" here = green local validators + this review, not a
merged remote PR (no push/PR per the ORGANISM LOCAL-ONLY strategy).

**What I checked against source (not just the ticket's own claims):**
1. **`interrupted` strands/mis-handles nothing.** R8 (`board_lint.py`) guards
   `status == "in_review" and assignee == author` — verified at the source line;
   an `interrupted` ticket is out of scope, never rejected/stranded. `/daslab-cycle`
   step-3 selection order is `p0 → in_review → in_progress → todo` (SKILL.md:78-79)
   — `interrupted` is absent, so it is parked (non-actionable), not dispatched, not
   coerced to `blocked`; step-2 reassignment guard is scoped to `in_review` only, so
   it does not touch it. `board/ROUTING.md` reviewer map applies only to `in_review`
   — no `interrupted` reviewer semantics. Consumer sweep matches the code.
2. **Schema + `resume:<value>` contract is sound, no smuggling.** `schema.json`
   sets `additionalProperties: false` (no extra field injection), `options` is a
   non-empty `uniqueItems` array of non-empty strings, `ticket` is pinned to
   `^DAS-[0-9]+$`, `payload` must be an object. The answer contract is fixed here:
   `<value>` MUST be one of `options` — runtime enforcement is correctly deferred to
   the DAS-1447 consumer; the design does not permit an out-of-set value by contract.
3. **Idempotency (DAS-1447 scope) is not precluded.** One card = one file at
   `board/interrupts/<id>.json`; the schema carries no answered/consumed field but
   nothing in it prevents DAS-1447 from removing/marking the card on resume or making
   injection idempotent. Additive-only, no consumer reads the schema yet.
4. **Tests cover the new status:** positive (`test_interrupted_status_accepted`),
   end-to-end on disk (`test_load_tickets_interrupted_file`), R8-scope regression
   (`test_interrupted_not_subject_to_self_review_r8`), and negative — enum stays
   closed, a typo status is still rejected (`test_unknown_status_still_rejected`).

**Validators re-run in the worktree (all green):** `board_lint` 0 violations (17
tickets); `check_never_auto_approve` clean (17); `pytest tests/test_board_lint.py`
25 passed; `diagnostics` 100/100; `schema.json` parses as valid JSON.

Signed off. Ready for DAS-1447 (runtime consumer) to build on the accepted schema.
