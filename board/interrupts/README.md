# board/interrupts/ — interrupt-card store (DAS-1446)

> Design-of-record for the **interrupt card** and the `interrupted` ticket
> status. Schema + enum + transitions + consumer sweep. The runtime that writes,
> reads, and resumes cards is wired by **DAS-1447**; this directory and the
> `resume:<value>` answer contract are fixed here.
> Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` (ORGANISM WS1 "Pulse").

## What an interrupt card is

When a running agent hits an ambiguous decision it cannot resolve on its own, it
has, historically, only two poor options: guess, or mark the ticket `blocked`
(which the board treats as an external-dependency stall that is never
auto-dispatched). Neither captures *"I need a quick human choice to keep going."*

An **interrupt card** is a small JSON object that carries a question and its
answer options to the Founder. The agent yields (its ticket moves
`in_progress` → `interrupted`); the Founder answers by writing `resume:<value>`;
the ticket flows back into the wave (`interrupted` → `in_progress`) with the
answer available to the resuming agent.

This directory is **parallel to `board/tickets/`** so cards never pollute the
ticket glob — `board_lint` reads only `board/tickets/DAS-*.md`, never this
folder — and the whole feature is trivially removable (`rm -rf board/interrupts/`).

## Object schema

Path: `board/interrupts/<id>.json` — one file per open question, where `<id>` is
a unique card id (recommended: `<TICKET-ID>-<n>`, e.g. `DAS-1450-1`).

```json
{
  "question": "free-text prompt shown to the Founder",
  "options": ["option-a", "option-b", "..."],
  "ticket": "DAS-1450",
  "payload": { "arbitrary": "agent context needed to resume" },
  "created_by": "backend-eng-1"
}
```

| Field | Type | Required | Meaning |
|---|---|---|---|
| `question`   | string        | yes | Free-text prompt shown to the Founder. Non-empty. |
| `options`    | array<string> | yes | The legal answers. Non-empty; each a non-empty string. The Founder's `resume:<value>` `<value>` MUST be one of these. |
| `ticket`     | string        | yes | The `DAS-####` id of the ticket that raised the card (matches a `board/tickets/` id). |
| `payload`    | object        | yes | Arbitrary agent context needed to resume the work. May be `{}` but the key must be present. |
| `created_by` | string        | yes | Role key of the agent that raised the card (a key from `board/ROUTING.md`). |

A machine-checkable JSON Schema is in [`schema.json`](schema.json) (draft 2020-12).
Nothing consumes it yet; DAS-1447 will validate cards against it.

## Answer contract (fixed here)

The Founder answers by writing **`resume:<value>`**, where `<value>` is exactly
one of the card's `options`. The exact write target / mechanism (where
`resume:<value>` is written and how the runtime observes it) is specified by
**DAS-1447**; only the *contract string* `resume:<value>` is fixed in this ticket.

## `interrupted` status — legal transitions

`interrupted` is one value in the single source-of-truth status enum
(`scripts/board_lint.py` `VALID_STATUSES`, mirrored in `board/README.md`). The
only legal transitions involving it are:

| From | To | Trigger |
|---|---|---|
| `in_progress` | `interrupted`  | Agent raises an interrupt card and yields. |
| `interrupted` | `in_progress`  | Founder writes `resume:<value>`; ticket re-enters the wave with the answer available. |
| `interrupted` | `blocked`      | Question abandoned / cannot be answered; falls back to the normal `blocked` path (requires a log reason, per board rules). |

## Consumer sweep (every reader of ticket `status`)

Enumerated so no consumer rejects or strands a validly-formed `interrupted`
ticket:

1. **`board_lint.py` R2 (status enum)** — now **accepts** `interrupted`
   (added to `VALID_STATUSES`). A well-formed `interrupted` ticket lints clean.
2. **`board_lint.py` R8 (in_review self-review)** — **untouched**. R8 keys off
   `status == "in_review"`, so an `interrupted` ticket is entirely out of its
   scope; it is never rejected or stranded by R8.
3. **`/daslab-cycle` triage / actionability** — `interrupted` is
   **non-actionable (parked)**. It is not in the selection priority order
   (`p0` → `in_review` → `in_progress` → `todo`), so triage neither
   auto-dispatches it as work nor treats it as `blocked`. It becomes actionable
   only after `resume:<value>` moves it back to `in_progress`. The step-2
   `in_review`-reassignment guard does not touch it (that guard is scoped to
   `status == "in_review"`).
4. **`board/ROUTING.md` (in_review reviewer routing)** — `interrupted` has **no
   reviewer semantics**. The reviewer map applies only to `in_review` tickets, so
   an `interrupted` ticket is never routed to a reviewer.
5. **`scripts/diagnostics.py` `status-enum` check (Consistency dimension)** —
   **missed by this sweep originally** (DAS-1646): it redeclared its own copy
   of the status enum instead of reading `board_lint.VALID_STATUSES`, so it
   silently fell out of sync the moment `interrupted` was added here. A
   validly-formed `interrupted` ticket then zeroed the whole 15-point
   Consistency dimension while `board_lint` passed the same board clean — the
   sweep was the control meant to catch exactly this, and the control had a
   hole. Fixed by deriving `diagnostics.VALID_STATUS` from
   `board_lint.VALID_STATUSES` (one definition, not two agreeing by luck) and
   pinned by `tests/test_diagnostics_status_enum.py`, which fails on ANY
   future divergence between the two, not just a repeat of this specific value.

**Invariant:** no consumer may reject a validly-formed `interrupted` ticket or
silently drop it. **Process note:** any status-enum addition/removal must
re-check this list AND grep the repo for other status-value literals before
closing the ticket — `scripts/diagnostics.py` was missed once already because
the sweep was written by inspecting known call sites, not by searching for
independent redeclarations of the enum.
