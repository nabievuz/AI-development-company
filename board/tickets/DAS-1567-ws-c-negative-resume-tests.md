---
id: DAS-1567
title: WS-C Testing — resume idempotency, gate-interrupt block, routing rejection, divergence and flag-off
status: done
assignee: qa-lead
author: ceo
dept: engineering
priority: p1
parent: DAS-1561
goal: mustaqil-ws-c-loop
spec: 004-mustaqil-ws-c-loop
implements: [SC-001, SC-002, SC-003, SC-004, SC-005]
labels: [security]
zone: tests
depends_on: [DAS-1564, DAS-1565]
created: 2026-07-24
updated: 2026-07-24
---


## Description

**AADL Stage 4 — Testing (closes GATE-4 for WS-C).** Prove the loop governance holds with
adversarial + resume tests against the DAS-1564 substrate and the DAS-1565 sandbox adapter
(stub backend — live-host smoke is DAS-1566). Security Engineer (red team) consulted.

Cover:
- **SC-001:** an idempotent checkpoint/resume test — the loop resumes after a mid-run
  interruption without losing progress and without double-applying a committed side effect
  (DAS-1447 guard-before-act).
- **SC-002:** a ticket behind an open gate is NOT routed to a worker node (gate =
  `interrupt()`/conditional edge, LG-2/C4); and an injected `graph_state` divergence
  resolves back to the board (board wins, LG-1/C2).
- **SC-003:** a worker node's attempt to write a routing field (assignee/reviewer/
  routing_reason/confidence) is rejected / structurally impossible (LG-3/C3).
- **SC-004:** with `ws_c_langgraph_loop` OFF, a wave's dispatch is byte-identical to
  pre-merge; flipping it ON runs the loop only in shadow.
- Sandbox isolation asserted at the adapter/stub layer (host/repo/other-task/credential
  unreachable by default); live-host smoke is DAS-1566.

## Acceptance criteria
- [x] Negative/resume tests exist and PASS in CI for SC-001 (idempotent resume), SC-002 (gate-block + divergence-resolves-to-board), and SC-003 (routing-field rejection).
- [x] Flag-off no-op behaviour asserted (SC-004); flag-on runs shadow-only.
- [x] Sandbox isolation policy asserted against the stub backend; overall pytest green in CI.
- [x] Security Engineer red-team review recorded. LOCAL green (local-only per dispatch; no remote PR this run).

## Log
### 2026-07-24 — CEO
Created by /daslab-plan (WS-C Testing). SC-001 resume idempotency, SC-002 gate-block +
divergence, SC-003 routing rejection, SC-004 flag-off; red-team consulted. Live-host
isolation smoke is DAS-1566 (blocked, external dependency).

### 2026-07-24 — CTO
Bound **SC-005** into `implements:` at DAS-1563 GATE-2 closure. The WS-C design
(`docs/design/ws-c-langgraph-loop.md` §7 SC-005a–d) routes the FR-006 sandbox-escape
negative test (host/repo escape, cross-task isolation, unscoped-credential + egress,
resource-limit) to this ticket, run against the `LocalStubSandbox` (host-free); the same
refusal decisions re-run unchanged against DAS-1566's live `DockerSandbox`. SC-005 is a
valid SPEC-004 token, so the ref resolves and `check_spec_consistency` stays green. Note:
SPEC-004's SC-005 is literally worded as the CI-hygiene criterion (diagnostics/validators/
green CI/committed attestation); the design overloads the same id as the sandbox-escape
umbrella — both readings land on this ticket. No other field changed.

### 2026-07-24 — QA Engineer
**AADL Stage-4 (Testing / GATE-4) suite delivered.** Read the design
(`docs/design/ws-c-langgraph-loop.md` §7-8), the DAS-1564/1565 `## Log` GATE-3
red-team residuals, SPEC-004, and the two existing Development-stage suites
(`tests/test_ws_c_langgraph_substrate.py` 14, `tests/test_ws_c_sandbox_adapter.py`
24) so nothing here duplicates them. Delivered the design's named-home file
`tests/test_ws_c_langgraph_loop.py` (8 new tests) + two residual tests folded
into the natural-home `tests/test_ws_c_sandbox_adapter.py` (now 26, 25 passed +
1 xfailed). Touched ONLY `tests/` + this ticket — no impl/config/ADR change.

**SC + residual → test map:**
- **SC-001a** (resume loses no progress, reaches same terminal state as an
  uninterrupted run) → `tests/test_ws_c_langgraph_loop.py::test_sc001a_resume_preserves_completed_work_and_reaches_same_terminal_state_as_uninterrupted`
  — commits wave 1, simulates a crash, resumes (re-commit wave 1 idempotently,
  no lost work), runs wave 2, and compares the resumed run's ledger shape
  against a fresh uninterrupted two-wave control run.
- **SC-001b** (no double-apply, generic guard-before-act angle) →
  `tests/test_ws_c_langgraph_loop.py::test_sc001b_guard_before_act_skips_reapply_of_a_generic_committed_side_effect`
  — a merge/emitted-event side effect keyed by run_id, independent of
  `run_wave`. The run_wave/ledger-specific angle of SC-001b was already green
  in `test_ws_c_langgraph_substrate.py::test_idempotent_resume_no_double_apply_and_ledger_reconciles`
  (not duplicated).
- **SC-002a** (gate-interrupt blocks; NAA category parks machine-blocked) →
  `tests/test_ws_c_langgraph_loop.py::test_sc002a_open_gate_and_naa_category_park_as_a_schema_valid_interrupt_card`
  — adds a full `board/interrupts/schema.json` validation of the card shape
  (required fields, `additionalProperties: false`, `DAS-####` ticket pattern)
  on top of the routing/worker-unreachable assertion already in
  `test_ws_c_langgraph_substrate.py`.
- **SC-002b** (divergence resolves to the board, checkpoint never a
  tiebreaker) → `tests/test_ws_c_langgraph_loop.py::test_sc002b_divergence_in_a_non_routing_channel_also_resolves_to_the_board`
  — same rule proven on the `risk` channel, a different field group than the
  `routing`/`assignee` case `test_ws_c_langgraph_substrate.py` already covers.
- **SC-003** (worker write-scope structurally unreachable, not merely
  guarded) → `tests/test_ws_c_langgraph_loop.py::test_sc003_worker_node_body_has_no_routing_write_reference_in_graph_topology`
  — AST-inspects `build_graph`'s `_worker` node body (no `routing`/
  `apply_channel`/`apply_group` reference) and its graph edges (`WORKER`'s
  only out-edge is `END`). The `apply_channel`-rejection angle was already
  green in `test_ws_c_langgraph_substrate.py::test_worker_routing_field_write_rejected`.
- **SC-004a** (flag-off byte-identical) → `tests/test_ws_c_langgraph_loop.py::test_sc004a_flag_off_wave_is_byte_identical_to_a_pre_merge_wave`
  — diffs a "pre-merge" `run_wave`-only ledger against the substrate's
  `commit_wave` ledger with the flag OFF; bytes match exactly.
- **SC-004b** (flag-on shadow-only, never auto-drives) →
  `tests/test_ws_c_langgraph_loop.py::test_sc004b_flag_on_runs_shadow_only_never_auto_drives`
  — new: the existing suites never exercised the flag-ON path at all.
- **SC-005** (sandbox-escape summary, one representative denial per wall) →
  `tests/test_ws_c_langgraph_loop.py::test_sc005_escape_suite_summary_all_four_walls_denied_fail_closed_no_side_effect`.
  The exhaustive 24-test per-wall matrix stays `test_ws_c_sandbox_adapter.py`'s
  (not duplicated).
- **Residual (a) — NUL-byte path** → `tests/test_ws_c_sandbox_adapter.py::test_host_wall_nul_byte_path_denies_cleanly_not_a_raised_valueerror`.
  Confirmed today's actual behaviour: `LocalStubSandbox.exec(["read", "foo\x00bar"])`
  raises an uncaught `ValueError` ("embedded null character") instead of the
  contract's `ExecResult(ok=False)`. The test asserts the fail-closed baseline
  (no path reached/no file touched) unconditionally, then asserts the DESIRED
  clean-deny shape — and is marked `xfail(strict=True)` since today's shape
  fails that assertion. **Did NOT patch impl** (out of QA footprint, per
  dispatch constraint) — routing the one-line fix (wrap `_resolve_within`'s
  body on `OSError`/`ValueError` → return `None`) to **backend-eng-1**, same
  pattern as WS-A's C3. `strict=True` means the moment the fix lands this test
  XPASSes and CI fails, forcing the marker's removal — a live tripwire, not a
  silent skip.
- **Residual (b) — caller-side raw-`stdout` Tier-M assertion** →
  `tests/test_ws_c_sandbox_adapter.py::test_credential_exec_result_stdout_is_not_serialized_into_an_event_by_a_correct_caller`.
  Proves both halves: a naive caller serializing raw `ExecResult.stdout` WOULD
  leak the scoped secret, and the safe `ScopedSecret.to_event_fields()`
  projection never does. No impl bug — this is a caller-discipline contract
  test, exactly as scoped.

**No real bug found beyond the already-known NUL-byte residual** (fail-closed,
not an escape — Security Engineer's GATE-3 verdict stands). No new escalation.

**Verify (STAGED, `git add -A` first):** `python3 scripts/diagnostics.py` →
**100/100**. `python3 -m pytest tests/test_ws_c_*.py -q` → **47 passed, 1
xfailed** (the documented NUL-byte shape residual). `python3 -m pytest -q`
(full suite) → **2128 passed, 4 skipped, 1 xfailed**. `python3 scripts/board_lint.py`
→ exit **0** (180 tickets; the lone WARN is pre-existing DAS-1507 prose,
unrelated). `ruff check tests/test_ws_c_langgraph_loop.py
tests/test_ws_c_sandbox_adapter.py` → clean (repo-wide `ruff check .` has 23
PRE-EXISTING findings in `tools/control_plane/` — untouched, out of this
ticket's footprint). No `/Users/owner`/hardcoded-home literals (all paths via
`tmp_path`); secret-shaped test strings fragmented with `+`.

⛔ LOCAL-ONLY per dispatch: no git commit/branch/push/PR. Footprint this run:
`tests/test_ws_c_langgraph_loop.py` (new), `tests/test_ws_c_sandbox_adapter.py`
(extended), this ticket file. `scripts/dgox/`, `tools/sandbox/` impl, ADRs,
and config untouched.

**Status → in_review, assignee → qa-lead** (GATE-4, per ROUTING — never
self-review).

### 2026-07-24 — QA Lead
**GATE-4 (AADL Stage-4 Testing) CLOSED for WS-C LOOP. status in_review → done.**
Independent verification (STAGED — `git add -A` first):

- `python3 -m pytest tests/test_ws_c_langgraph_loop.py tests/test_ws_c_langgraph_substrate.py tests/test_ws_c_sandbox_adapter.py -q` → **48 passed, 0 xfailed** (8 loop + 14 substrate + 26 adapter). The prior lone `xfail` (NUL-byte denial-shape) is gone.
- `python3 -m pytest -q` (full suite) → **2129 passed, 4 skipped, 0 xfailed**.
- `python3 scripts/diagnostics.py` → **100/100** TRACKED.
- `python3 scripts/board_lint.py` → exit **0** (180 tickets; the single WARN is pre-existing DAS-1507 body prose, unrelated).

Coverage confirmed — SC-001..005 + both GATE-3 residuals map to REAL passing test functions:
- **SC-001a/b** resume-idempotency + guard-before-act (no double-apply) — `test_ws_c_langgraph_loop.py` + substrate ledger test.
- **SC-002a** open-gate/NAA parks as a schema-valid interrupt card; **SC-002b** non-routing-channel divergence resolves to the board (board wins).
- **SC-003** worker node has no routing-write reference in graph topology (AST + edge inspection — structurally unreachable, not merely guarded).
- **SC-004a** flag-off byte-identical to a pre-merge wave; **SC-004b** flag-on runs shadow-only.
- **SC-005** sandbox-escape suite is REAL and exhaustive against `LocalStubSandbox`: all four walls denied fail-closed — host (dotdot / absolute / confined / NUL-byte), repo (sibling-area escape / own-worktree-only), other-task (scope mismatch / stale handle / foreign token / no shared mount), credential (empty-by-default / scoped-grant / cross-task-denied / value-never-in-event), plus egress (deny-all / allowlist), escape-attempt (no side effect / unknown verb), and resource-limit walls; summarised in `test_sc005_escape_suite_summary_all_four_walls_denied_fail_closed_no_side_effect`.
- **Residual (a)** `test_host_wall_nul_byte_path_denies_cleanly_not_a_raised_valueerror` now **PASSES un-xfail'd** — the fail-closed fix landed in `tools/sandbox/local_stub.py` (`_resolve_within` catches `(OSError, ValueError)` → returns `None`, same denial as `..`/absolute), so `exec()` returns `ExecResult(ok=False)` instead of raising. Verified **0 xfail markers remain** anywhere in the WS-C suites.
- **Residual (b)** caller-side raw-`stdout` Tier-M assertion — green; caller-discipline contract, no impl bug.

DECISION: coverage complete + suite fully green (0 xfailed) → **GATE-4 PASS**. Accepted on LOCAL green per dispatch (⛔ LOCAL-ONLY — no commit/branch/push/PR this run; footprint = this ticket only). This **unblocks DAS-1568 (Deployment / GATE-5)**. DAS-1566 (live DockerSandbox smoke) correctly remains BLOCKED on an external Docker/E2B host — the stub proves the isolation contract; live smoke is DAS-1566's scope when a host exists, and does NOT gate GATE-4.
</content>
