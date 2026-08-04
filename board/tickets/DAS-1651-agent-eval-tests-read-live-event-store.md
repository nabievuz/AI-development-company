---
id: DAS-1651
title: test_agent_eval asserts against the live gitignored event store — green on a clean box, red after any wave
status: todo
assignee: qa-eng
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
- [ ] The four tests inject the event store as a fixture (`tmp_path` + monkeypatched
      store path), matching the pattern `test_ws_a2a_health_check.py` already uses —
      do not invent a second convention for the same problem.
- [ ] The suite's result is identical with `board/.events.jsonl` absent, empty, and
      populated with unrelated events. Prove all three, since only the first two are
      obvious.
- [ ] **Sweep every other test that reads ambient gitignored runtime state**
      (`board/.events.jsonl`, `board/.wave-log`, `board/runs/`, `board/.arcrift-outbox.jsonl`,
      `metrics/`) and record what was found even if nothing else needs changing. This is
      the third time this class has surfaced; a per-file fix without the sweep invites a
      fourth.
- [ ] A guard makes the next occurrence loud rather than latent — e.g. a session-scoped
      check that fails a test which touches the real store, or a documented convention
      with a lint. Decide which and record why.
- [ ] `diagnostics.py` 100/100; full suite green both on a clean checkout and on a box
      that has run a wave.

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Surfaced because the orchestrator's own erroneous `run_wave` call (see DAS-1650) left 6
events in `board/.events.jsonl`; those were removed and only the pre-existing
`a2a_publish` line restored, which returned the suite to 2755 passed. The events were
invisible to `git status` because the file is gitignored — worth noting for whoever
fixes this, since it is also why the leftover state went unnoticed for several steps.

The trigger was accidental; the defect is not. Any legitimate wave with `organism_emit`
ON emits the same events and would have produced the same four failures.
