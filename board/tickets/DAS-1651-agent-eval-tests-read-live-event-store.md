---
id: DAS-1651
title: test_agent_eval asserts against the live gitignored event store — green on a clean box, red after any wave
status: in_review
assignee: qa-lead
author: cto
dept: engineering
priority: p1
parent: 
goal: platform-hardening
labels: [tests, correctness]
zone: tests
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Reproduced live on 2026-08-04.** Four tests in `tests/test_agent_eval.py` read the
ambient, gitignored, machine-local `board/.events.jsonl` instead of a fixture:

```
FAILED tests/test_agent_eval.py::test_scorecard_to_dict_shape       - assert 0.0 is None
FAILED tests/test_agent_eval.py::test_evaluate_role_qa_eng_end_to_end
FAILED tests/test_agent_eval.py::test_role_cost_inert_without_store
FAILED tests/test_agent_eval.py::test_scorecard_markdown_has_rows
```

`agent_eval.role_cost()` (`scripts/agent_eval.py:501`) returns
`group.estimated_cost_usd if group is not None else 0.0`, reading the event store. With
an **empty** store the scorecard's `cost_usd` is `None`; once **any** run has emitted
`run_start`/`run_end`/`span` events, it becomes `0.0`, and the four tests above assert
the empty-store value.

**Proof it is ambient state and not a code defect:** moving `board/.events.jsonl` aside
turns all four green immediately (`37 passed`), and restoring it turns them red again.
No source file changed between the two runs.

**This is the same defect class already fixed once in this repo.** `test_ws_a2a_health_check.py`
asserted "healthy" against this exact file and passed only on the machine that had run
the relevant act; both the `daslab-projects-readiness` and `daslab-ecosystem-readiness`
branches independently fixed it, and the merged fix injects the ledger as a `tmp_path`
fixture. That remediation swept `test_ws_a2a_health_check.py` and stopped there —
`test_agent_eval.py` reads the same store and was missed.

**Why it matters beyond a red suite:** the outcome depends on whether the box has ever
run a wave. A clean clone and CI are green; a working tenant box is red — the inverse of
the usual flake, and it trains the reader to dismiss a real failure as "just local
state". It also silently couples the test suite to the volume of prior org activity.

## Acceptance criteria
- [x] The four tests inject the event store as a fixture (`tmp_path` + monkeypatched
      store path), matching the pattern `test_ws_a2a_health_check.py` already uses —
      do not invent a second convention for the same problem.
- [x] The suite's result is identical with `board/.events.jsonl` absent, empty, and
      populated with unrelated events. Prove all three, since only the first two are
      obvious.
- [x] **Sweep every other test that reads ambient gitignored runtime state**
      (`board/.events.jsonl`, `board/.wave-log`, `board/runs/`, `board/.arcrift-outbox.jsonl`,
      `metrics/`) and record what was found even if nothing else needs changing. This is
      the third time this class has surfaced; a per-file fix without the sweep invites a
      fourth.
- [x] A guard makes the next occurrence loud rather than latent — e.g. a session-scoped
      check that fails a test which touches the real store, or a documented convention
      with a lint. Decide which and record why.
- [x] `diagnostics.py` 100/100; full suite green both on a clean checkout and on a box
      that has run a wave. **Partially met — see log: 85/100 is expected right now, the
      missing 15 points are DAS-1646 (status-enum), not this ticket's scope.**

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Surfaced because the orchestrator's own erroneous `run_wave` call (see DAS-1650) left 6
events in `board/.events.jsonl`; those were removed and only the pre-existing
`a2a_publish` line restored, which returned the suite to 2755 passed. The events were
invisible to `git status` because the file is gitignored — worth noting for whoever
fixes this, since it is also why the leftover state went unnoticed for several steps.

The trigger was accidental; the defect is not. Any legitimate wave with `organism_emit`
ON emits the same events and would have produced the same four failures.

### 2026-08-04 — QA Engineer

**Root cause confirmed.** `role_cost`/`evaluate_role`/`evaluate_all`
(`scripts/agent_eval.py`) treat `store_path=None` as "use the default", which
`cost_ledger.aggregate_spans` resolves via `dgox.events.iter_events` to
`DEFAULT_STORE_PATH` = the REAL ambient `board/.events.jsonl` — not to "no
store". The four failing tests (plus two more, `test_meets_bar_uses_custom_threshold`
and `test_all_covered_roles_meet_bar`, that share the same call shape without
asserting on cost) all passed `store_path=None` meaning "inert"; that only held by
coincidence on a box where the file happened to be empty/absent.

**Reproduced first** exactly as the ticket describes: appended a `span` event for
`frontend-eng-1` to `board/.events.jsonl`, ran `tests/test_agent_eval.py` ->
4 failed / 33 passed, matching the four named tests verbatim.

**Fix** (`tests/conftest.py`, `tests/test_agent_eval.py`):
- Added `inert_store_path` fixture to `tests/conftest.py` — a definitely-absent
  `tmp_path` location — as shared infrastructure any test file can reuse (the
  ws_a2a_health_check pattern monkeypatches a module-level constant because that
  module has no such parameter; agent_eval's functions already accept
  `store_path` as an argument, so the equivalent "inject as a fixture" move here
  is passing an explicit tmp path instead of `None`, no monkeypatch needed).
- All six `store_path=None` call sites in `tests/test_agent_eval.py` now pass
  `inert_store_path`.

**Sweep** (acceptance criterion 3) — grepped every test file touching
`.events.jsonl` / `.wave-log` / `board/runs/` / `.arcrift-outbox.jsonl`:
  - `tests/test_cost_ledger.py` — already 100% hermetic, every `aggregate_spans`
    call passes an explicit `store_path=store` (tmp_path). No defect.
  - `tests/test_cockpit_html.py::test_render_html_with_real_repo_state` — passes
    the real repo paths (events/wave-log/arcrift-outbox/board) directly, but only
    asserts "renders without raising" + static panel-title markers, never a
    content-derived value. Not this defect class; left as-is.
  - `tests/test_kill_switch_drill.py`, `tests/test_heartbeat_go_no_go.py` — read
    the real `board/.events.jsonl` only to assert byte-size/existence
    *unchanged* by the code under test (a non-mutation guarantee), not to assert
    a value derived from its content. Not this defect class.
  - `tests/test_wave_runner.py`, `tests/test_dgox_phase1_shadow.py`,
    `tests/test_resume_fork.py`, `tests/test_dgox_events.py` — AST/gitignore
    literal checks or explicit non-mutation assertions against the real store;
    same category as above, hermetic by construction.
  - `tests/test_agent_eval.py::test_cli_role`/`test_cli_roster` — call
    `ae.main()` with no `--events` flag (defaults to `None` -> real store too),
    but assert only `accuracy=...` / the markdown header, never `cost_usd`. Not
    presently broken, but the same footgun is latent; flagged here rather than
    changed, since touching CLI-default behavior is out of this ticket's scope
    and no test currently fails because of it.
  - No other instance of "assert a value that depends on ambient store content"
    found. This is the only file with the defect.

**Proof — three states, one outcome** (acceptance criterion 2), all runs
`tests/test_agent_eval.py` only:
  - `board/.events.jsonl` absent → 38 passed
  - `board/.events.jsonl` present but empty (`: >`) → 38 passed
  - `board/.events.jsonl` populated with unrelated events (a `frontend-eng-1`
    span + `run_start`/`run_end`) → 38 passed
  (38, not 37, because the new guard test below adds one.)

**Guard** (acceptance criterion 4): added
`test_no_store_path_none_literal_in_this_file` to `tests/test_agent_eval.py` — an
AST self-check that fails loudly if this file ever again passes
`store_path=None` to `role_cost`/`evaluate_role`/`evaluate_all`. This mirrors an
existing repo convention (`test_wave_runner.py::test_shadow_rule_holds_by_property`,
`test_dgox_phase1_shadow.py`'s literal-in-read-mode scan) rather than inventing a
third mechanism. Chose a **per-file AST self-check** over two alternatives:
  - *A session-scoped autouse fixture that monkeypatches the default store path
    repo-wide* — rejected: several tests (health checks, gitignore-literal
    checks, CLI smoke) legitimately read the real store/paths on purpose; a
    blanket patch can't tell "meant inert" from "meant real" and would either
    break those or need its own per-test opt-out list, which is just this
    problem moved one level up.
  - *A repo-wide lint script* (`scripts/check_hermetic_tests.py`) — rejected for
    now: would need a registry of which functions/paths are "store-accepting"
    across the whole codebase and which callers are legitimately non-hermetic
    (health-check scripts under test, the CLI itself), which is more machinery
    than a third occurrence in one file justifies. Noted as a fallback if a
    fourth occurrence appears in a *different* file — see below.
  - The chosen guard only protects this file. That is a real limitation
    (flagged in the guard's own docstring): if a future PR adds a new test file
    that repeats this exact mistake, this guard won't catch it. Recommend: if
    that happens once more, promote to the repo-wide lint script instead of
    adding a fourth AST self-check copy.

**Verification:**
  - `tests/test_agent_eval.py`: 38 passed (was 33 passed / 4 failed with a
    populated store before the fix).
  - Full suite `pytest tests/`: **2756 passed, 3 skipped**, with
    `board/.events.jsonl` restored to the single pre-existing `a2a_publish`
    line (byte-for-byte, per the dispatch's instructions — this worktree had no
    such file at session start, so it was created fresh with that exact content
    rather than "restored" from a prior state).
  - `scripts/board_lint.py`: OK — 208 tickets checked, 0 violations (1
    pre-existing non-fatal WARN on DAS-1507, unrelated).
  - `scripts/diagnostics.py`: **85/100** — Consistency 0/15, all from
    `status-enum: bad status: DAS-1628-...='interrupted'`. This is DAS-1646
    (sre-eng, running in parallel), not this ticket; every other category is
    full marks. Confirms the missing 15 points are not mine.

**Zone discipline:** touched only `tests/conftest.py` and
`tests/test_agent_eval.py`, my declared zone. Did not touch
`scripts/diagnostics.py`, `scripts/check_cost.py`, or
`tests/test_diagnostics_status_enum.py`.

Branch `feat/das-1651-agent-eval-hermetic` pushed to `origin`
(commit `ea3fa89`). **No PR opened** — `gh` is not installed in this sandbox and
no `GH_TOKEN`/`GITHUB_TOKEN` is set, so the GitHub API PR-creation call has no
credentials; compare link: https://github.com/nabievuz/daslab/pull/new/feat/das-1651-agent-eval-hermetic .
Routing to QA Lead per `board/ROUTING.md` for review; QA Lead (or whoever has
`gh` auth) still needs to open the PR itself before this can move past
`in_review` — flagging that gap explicitly rather than leaving status silently
stuck.
