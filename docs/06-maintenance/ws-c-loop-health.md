# WS-C loop/sandbox health/eval — AADL Stage 6 Maintenance (GATE-6)

> Closes GATE-6 for WS-C LOOP (ADR-0035). Accountable: COO. Responsible:
> Product Analyst. Consulted: Support Lead. Ticket: DAS-1569.

## What this is

A **recurring, read-only** health/eval check for the WS-C durable LangGraph
loop substrate (`scripts/dgox/langgraph_loop.py`) and its per-task sandbox
edge (`tools/sandbox/local_stub.py`), wired into the **existing**
Maintenance-stage cadence (`scripts/stage_gate.py:maintenance_schedule()`)
rather than a new daemon or scheduler. Per the AI-agent-lifecycle policy §3
(Stage 6), the schedule descriptor is **data, not an installer** — cadence
lives in the Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here
deploys or auto-runs itself, and nothing here flips the `ws_c_langgraph_loop`
flag.

Check script: `scripts/ws_c_loop_health_check.py`
Registered as the `ws-c-loop-health` entry in `maintenance_schedule()`'s
`recurring_runs` list, alongside `health-tick` (WS4), `golden-eval` (WS6),
`memory-hygiene` (ArcRift), `ws-a-tool-edge-health` (WS-A), `ws-b-runner-health`
(WS-B), and `ws-d-lens-health` (WS-D).

## What it checks

All three checks **reuse the real modules' own logic verbatim** — no parallel
reconciliation, wall, or ban implementation lives in the health check itself.

1. **Board-canonical drift** (checkpoint never a tiebreaker). Builds a real
   `dgox.state.GraphState`, projects it through
   `langgraph_loop.project`, injects a divergence into the projected
   channels (simulating a stale or forked checkpoint value), then calls
   `langgraph_loop.reconcile` — the actual function, unmodified — and asserts:
   the divergence is detected; the returned `board_state` still carries the
   **original board value**, never the projected/checkpoint value; and the
   emitted reconciliation event still carries
   `rule: board_wins_reconciliation`. A change that makes the checkpoint or
   projection win over the board — silently or otherwise — is a finding
   (ADR-0035 LG-1/FR-002/C2 regression: LangGraph state is a projection of
   `graph_state`, itself a mirror of `board/tickets/*.md`; a divergence
   resolves **up** to the board, never down from the checkpoint).
2. **Sandbox-wall drift**. Drives the real `LocalStubSandbox` (ADR-0035 LG-5)
   through its four fail-closed walls with a live probe each:
   - **host escape** — a `..` traversal, an absolute path, and an embedded
     NUL byte, each attempted as a `read`;
   - **cross-task** — an `exec` call using a handle for a `task_id` with no
     live registration;
   - **unscoped credential** — an `open()` call whose `SandboxScope` carries a
     `ScopedSecret` scoped to a different task than the one being opened;
   - **unscoped/non-allow-listed egress** — a `net` call with no
     `egress_profile`/allow-list grant.

   Each probe must still come back **denied** (`ExecResult.ok is False` or a
   raised `SandboxEscapeError`, per the wall). A wall that stops denying —
   even one of the four — is a finding.
3. **Import-ban carve-out drift**. Reuses `scripts/check_import_ban.py`'s own
   `SANCTIONED_IMPORT_PATHS` table, `_is_sanctioned_import` helper, `BANNED`
   list, and `check()` entry point (never re-implemented) to assert the
   ADR-0035 carve-out has not widened: `langgraph` is sanctioned **only**
   under `scripts/dgox/`; the same lib is still denied everywhere else
   (`scripts/wave_runner.py`, `tests/`, and the core `requirements*.txt`
   manifests); none of the other four banned donor libraries
   (`agent-framework`, `crewai`, `agency-swarm`, `superagi`) has gained a
   carve-out anywhere, including inside `scripts/dgox/`; the full `BANNED`
   set is still all five libraries; and a live `check_import_ban.check(ROOT)`
   run over the repo is still clean. A carve-out that grows to a new path, a
   new lib, or the core manifest is a finding — the CTO-ratified ADR-0035
   narrowing (2026-07-24) must not silently widen.

## Cadence and registration

- **Cadence:** daily (declared in `maintenance_schedule()["recurring_runs"]`,
  entry `ws-c-loop-health`).
- **Command:** `python3 scripts/ws_c_loop_health_check.py --json`.
- **Exit code:** `0` = healthy; `1` = a finding (board-canonical, sandbox-wall,
  and/or import-ban-carve-out drift) — the caller MUST treat this as an
  alert, never swallow it.
- Same registration point every other Maintenance-stage run uses (WS4
  `health-tick`, WS6 `golden-eval`, ArcRift `memory-hygiene`, WS-A
  `ws-a-tool-edge-health`, WS-B `ws-b-runner-health`, WS-D
  `ws-d-lens-health`) — no second scheduling mechanism was introduced.

## Alerting — a failure is never silent

A non-zero exit from `scripts/ws_c_loop_health_check.py` is treated the same
way any other Maintenance-cadence finding is treated:

1. The run's output (`--json`) is attached as evidence.
2. A follow-up board ticket is filed in `board/tickets/` (org-engine scope —
   this is a platform/governance concern, not a project) with
   `labels: [governance]` (or `[security]` for a sandbox-wall or
   import-ban finding), `dept: engineering`, routed per
   `governance/policies/raci.md` (Security Lead consulted, SRE/COO informed) —
   the same path DAS-1547/1549/1551/1559/1577 used for prior WS-A/B/D
   findings.
3. The ticket is **never** auto-remediated: a board-canonical finding means a
   human reviews and fixes the reconcile regression before the
   `ws_c_langgraph_loop` flag is ever considered for shadow (it ships OFF —
   `docs/runbooks/ws-c-langgraph-loop.md`); a sandbox-wall finding means a
   human closes the specific wall regression before any live sandbox work
   proceeds; an import-ban finding means a human reviews the
   `check_import_ban.py`/ADR-0035 diff and restores or explicitly
   re-ratifies the change. All three are `security_sensitive` /
   `governance_or_policy` categories per `config/risk_taxonomy.yaml` — CI's
   never-auto-approve check (`scripts/check_never_auto_approve.py`) rejects an
   `approval: auto*` on any of them. The `ws_c_langgraph_loop` flag itself is
   never touched by this check or by its remediation.

## Founder-reviewed learnings → `daslab-learn` (ADR-0029 G5)

A **repeated or systemic** finding from this check (e.g. the same reconcile
drift class recurring, the same wall regressing more than once, or a
carve-out drifting again after a prior fix) is a candidate **lesson**, not
just a one-off ticket. Per ADR-0029 §G5, lessons flow through the existing
`daslab-learn` distillation:

- The finding + its accepted remediation is logged in the relevant ticket
  (this doc's §Alerting above).
- `daslab-learn` distills **Founder-accepted** feedback only into a role's
  `## Learned` section (bounded, confidence-scored) — it is **governed
  compounding**, never autonomous self-modification. This health check does
  not write to any `## Learned` section itself; it only produces evidence for
  a human (Founder/CPO/Security Lead) to accept or reject at the normal
  `daslab-learn` cadence.
- Likely destination roles: `sre-lead` (substrate/reconcile-integrity and
  sandbox-wall patterns) and `security-lead`/`cto` (import-ban carve-out
  patterns) per `governance/agent-templates/*.md` overlays — routing the
  specific lesson to a role is a `daslab-learn` decision, not this script's.

## Verification

```
python3 scripts/ws_c_loop_health_check.py            # human-readable
python3 scripts/ws_c_loop_health_check.py --json      # machine-readable, for the alert payload
python3 -m pytest tests/test_ws_c_loop_health_check.py -q
```
