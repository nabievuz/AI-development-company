---
id: DAS-1646
title: diagnostics.py duplicates the status enum and is missing 'interrupted' — a valid ticket costs 15/15
status: in_review
assignee: sre-lead
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
- [x] `diagnostics.py` derives the enum from `board_lint.VALID_STATUSES` instead of
      redeclaring it — one definition, not two agreeing by luck.
- [x] A regression test fails if the two ever diverge again (assert the sets are
      identical, not that both happen to contain `interrupted`).
- [x] A board containing an `interrupted` ticket scores 100/100 with the venv active.
- [x] `board/interrupts/README.md` §"Consumer sweep" corrected to include
      `diagnostics.py`, so the next status addition does not repeat this.
- [x] Sweep for any OTHER duplicated enum/constant between `diagnostics.py` and the
      validators it overlaps; record what was found even if nothing needs changing.
- [x] `board_lint`/validators green; `diagnostics.py` 100/100; no flag flipped; no
      `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Filed on the explicit routing request in `security-lead`'s DAS-1628 report. The
finding was verified independently by the orchestrator before filing: both source
lines read, and the 70/100 vs `board_lint`-clean split reproduced on the DAS-1628
branch with the venv active (so the score is not confounded by the separate
`ruff`-on-PATH issue tracked in DAS-1649).

### 2026-08-04 — SRE Engineer
Implemented on branch `feat/das-1646-status-enum-ssot` (worktree
`.claude/worktrees/DAS-1646`), commit `b1feb9e`.

- **Core fix**: `scripts/diagnostics.py` no longer redeclares the status enum.
  It now imports `scripts/board_lint.py` and sets
  `VALID_STATUS = frozenset(board_lint.VALID_STATUSES)`. The import is
  self-sufficient (inserts `scripts/` onto `sys.path` itself rather than
  assuming the caller already put it there) and is wrapped in a bare
  `try/except` that falls back to an **empty frozenset** — never a crash — if
  `board_lint` cannot be imported at all; a new `status-enum-ssot-importable`
  check in the Consistency dimension surfaces that failure explicitly instead
  of letting every ticket fail silently with no explanation. Checked the
  import direction both ways: `board_lint.py` imports only `_paths`,
  `artifact_schemas`, `merge_reducers`, and lazily `stage_gate` — none of
  which import `diagnostics`, so there is no cycle.
- **Regression test**: new file `tests/test_diagnostics_status_enum.py` (does
  not touch `tests/test_agent_eval.py` or `tests/conftest.py`, DAS-1651's
  zone). It asserts `diagnostics.VALID_STATUS == set(board_lint.VALID_STATUSES)`
  by re-deriving the SSOT independently rather than hard-coding the expected
  set — the assertion fails on ANY future divergence, not just a repeat of the
  "interrupted" omission. A second test guards against a future "fix" that
  hand-copies the values again (checks the module object was actually
  imported). A third is an end-to-end regression for the bug as originally
  reported: an `interrupted` ticket in a scratch tickets dir passes the
  `status-enum` check.
- **`board/interrupts/README.md`**: §"Consumer sweep" corrected — added item 5
  naming `diagnostics.py` as the consumer the original sweep missed, plus a
  process note that the next status addition must grep for independent
  enum redeclarations, not just known call sites.
- **Constant-duplication sweep** (item 3): checked `diagnostics.py`'s other
  inline constants (`required_scripts`, `required_tests`, the ADR list, the
  hardcoded-home needle, the `VERSION` regex, the secrets regex) against every
  validator it shells out to. Found one adjacent pattern worth recording:
  `scripts/check_secrets.py:SECRET_PAT` and `diagnostics.py`'s inline
  `secret_pat` in `check_security()` use the *same* regex (Anthropic key / AWS
  key / private-key patterns), but `diagnostics.py` never calls
  `check_secrets.py` — the two scan different targets (events/experiments vs.
  all git-tracked files) and were both hand-written independently rather than
  drifting from a shared SSOT, so there is no active divergence bug today.
  Left as-is (not fixed — different failure class than an enum drift, and
  fixing it would mean designing a shared secrets-pattern module, which is
  bigger than this ticket's scope). Flagging as a candidate follow-up, not
  filing a new ticket myself since it is a judgment call above a plain bug
  report. `diagnostics.py`'s `check_consistency()` also reimplements a
  lighter-weight version of `board_lint`'s R1 (required fields) and R8
  (self-review) checks rather than shelling out to `board_lint` — that is
  pre-existing parallel *logic*, not a duplicated *constant*, so left
  unchanged; noted here for visibility.
- **Verification** (venv on PATH, per the dispatch note — `ruff` lives in the
  main checkout's `.venv`):
  - `python3 scripts/board_lint.py` → `board_lint: OK — 208 ticket(s) checked,
    0 violations.` (one pre-existing, unrelated `DAS-1507` body-status warning,
    non-fatal, exit 0).
  - `python3 scripts/check_links.py` → OK.
  - `ruff check scripts tests` → all checks passed.
  - `python3 -m pytest -q` → 2758 passed, 3 skipped.
  - `python3 scripts/diagnostics.py` → `SCORE = 100/100`.
- No feature flag touched; no `project:` field added (R9 unaffected).
- Pushed `feat/das-1646-status-enum-ssot` to `origin`. `gh` CLI is not
  available in this environment, so the PR itself was **not** opened
  programmatically — GitHub's compare link from the push is
  `https://github.com/nabievuz/daslab/pull/new/feat/das-1646-status-enum-ssot`.
  Setting `status: in_review`, `assignee: sre-lead` (my manager, per
  `board/ROUTING.md`) per the no-self-review rule; `sre-lead` (or whoever has
  `gh`/GitHub UI access) should open the PR from the pushed branch to satisfy
  "in_review requires a pushed branch/PR" fully, then review and merge with
  green CI to close this out.
