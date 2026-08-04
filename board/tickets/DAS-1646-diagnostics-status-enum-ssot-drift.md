---
id: DAS-1646
title: diagnostics.py duplicates the status enum and is missing 'interrupted' — a valid ticket costs 15/15
status: todo
assignee: sre-eng
author: security-lead
dept: engineering
priority: p1
parent: 
goal: platform-hardening
labels: [validators, correctness]
zone: scripts
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Found by `security-lead` during DAS-1628, deliberately not fixed there** — that
ticket's zone is `config`, this is `scripts`. Routed out rather than reached into.

`scripts/diagnostics.py:68` hard-codes its own copy of the ticket status enum:

```python
VALID_STATUS = {"backlog", "todo", "in_progress", "blocked", "in_review", "done"}
```

The SSOT is `scripts/board_lint.py:111`, which has carried `"interrupted"` since the
interrupt-card work:

```python
VALID_STATUSES = frozenset(
    {"backlog", "todo", "in_progress", "blocked", "in_review", "done", "interrupted"}
)
```

**The consequence is not cosmetic.** Any validly-formed `interrupted` ticket makes
the `status-enum` check fail, which zeroes the whole **Consistency** section — 15 of
100 points — while `board_lint` passes the same board clean. Reproduced on the
DAS-1628 branch:

```
board_lint: OK — 202 ticket(s) checked, 0 violations.
[FAIL] Consistency     0/15
        XX status-enum: bad status: ["DAS-1628-...md='interrupted'"]
SCORE = 70/100
```

Two validators disagreeing about what a legal ticket is means the 100/100 release
gate now punishes the org for using a status the board model explicitly defines.
The perverse incentive is the real damage: the cheapest way to restore a green gate
is to give a parked ticket a *wrong* status (`blocked`), which is exactly the
"disable the gate rather than fix it" failure mode. The DAS-1628 agent hit this and
correctly refused to take that route.

**Why it slipped:** `board/interrupts/README.md` §"Consumer sweep" enumerated the
consumers that must learn the new status and listed four — `diagnostics.py` was not
among them. The sweep was the control, and the control had a hole.

## Acceptance criteria
- [ ] `diagnostics.py` derives the enum from `board_lint.VALID_STATUSES` instead of
      redeclaring it — one definition, not two agreeing by luck.
- [ ] A regression test fails if the two ever diverge again (assert the sets are
      identical, not that both happen to contain `interrupted`).
- [ ] A board containing an `interrupted` ticket scores 100/100 with the venv active.
- [ ] `board/interrupts/README.md` §"Consumer sweep" corrected to include
      `diagnostics.py`, so the next status addition does not repeat this.
- [ ] Sweep for any OTHER duplicated enum/constant between `diagnostics.py` and the
      validators it overlaps; record what was found even if nothing needs changing.
- [ ] `board_lint`/validators green; `diagnostics.py` 100/100; no flag flipped; no
      `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the explicit routing request in `security-lead`'s DAS-1628 report. The
finding was verified independently by the orchestrator before filing: both source
lines read, and the 70/100 vs `board_lint`-clean split reproduced on the DAS-1628
branch with the venv active (so the score is not confounded by the separate
`ruff`-on-PATH issue tracked in DAS-1649).
