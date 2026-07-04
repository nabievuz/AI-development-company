# SPEC 001 — ORGANISM WS6/P19 golden-eval coverage completion

- **Goal:** organism-ws6-guild
- **Owner:** qa-lead
- **Status:** draft

<!--
  Extends WS6 GUILD / P19 (DAS-1484, DAS-1487, DAS-1488). The eval HARNESS and
  its runner (scripts/agent_eval.py) already exist and are green on a 6/32
  representative slice; this spec completes COVERAGE to all 32 roles. WHAT/WHY
  only — the harness contract (task.md + fixtures/ + verify.py + submissions/)
  is fixed by evals/README.md, not re-designed here.
-->

## User Scenarios

- **P1 —** Given the org has 32 specialist roles but golden evals for only 6,
  when an operator runs `scripts/agent_eval.py --enforce`, then every one of the
  32 roles is measured against ≥3 deterministic golden tasks and none is
  silently unmeasured.
- **P2 —** Given a role's eval set, when it is scored over k=3 recorded
  submissions offline, then the role earns ≥0.80 mean credit at its assigned
  model tier or the enforce run fails with an actionable, role-named message.
- **P3 —** Given the coverage is complete, when the operator reads
  `docs/AGENT-ROSTER.md`, then an accuracy×cost scorecard row exists for all 32
  roles, and any tier correction the data implies is recorded.
- **P4 —** Given these authoring tickets run as `/daslab-cycle` waves, when a
  wave dispatches, then real `run_start`/`run_end`/span events accrue in the
  org event store — the sustained shadow-window evidence R-4 (HEARTBEAT
  go-live) is blocked on.

## Functional Requirements

- **FR-001** — Each of the 26 remaining roles MUST have ≥3 golden tasks under
  `evals/<role>/<task-id>/` (`task.md` + `fixtures/` + a DETERMINISTIC
  `verify.py` returning fractional credit in [0.0, 1.0]); an empty/degenerate
  submission MUST score 0.0 (anti-gaming). The graded answer key lives ONLY in
  `verify.py` — never in `fixtures/`.
- **FR-002** — Each role's tasks MUST carry recorded `submissions/` (k=3) so the
  role is graded end-to-end OFFLINE without dispatching a live subagent, and the
  task must exercise that role's core competencies per its overlay
  (`.claude/agents/<role>.md`). Soft/rubric scoring (`RUBRIC = True`,
  haiku-as-judge) is permitted ONLY for genuinely subjective tasks and MUST reuse
  the T7 rubric via `check_t7_quality.py` (no forked scorer).
- **FR-003** — `scripts/agent_eval.py --enforce` MUST pass for all 32 roles at
  each role's assigned tier (`governance/policies/model-allocation.md`), and
  `--check-gaming` MUST stay green.
- **FR-004** — `docs/AGENT-ROSTER.md` MUST carry an accuracy×cost scorecard row
  for all 32 roles; any tier correction the eval data justifies MUST be recorded
  (data replaces judgment).
- **FR-005** — Authoring MUST EXTEND the existing harness; `scripts/agent_eval.py`
  and `evals/README.md`'s contract MUST NOT be rewritten or forked.

## Success Criteria

- **SC-001** — Golden-eval coverage = 32/32 roles (was 6/32), each with ≥3
  deterministic tasks. Closes §5 contract row 8.
- **SC-002** — `agent_eval.py --enforce` exit 0 across all 32 roles; every role
  ≥0.80 at its assigned tier; `--check-gaming` exit 0.
- **SC-003** — `docs/AGENT-ROSTER.md` scorecard complete (32 rows); ≥1 tier
  correction documented if the data warrants one.
- **SC-004** — `diagnostics.py` stays 100/100 and `board_lint.py` clean after the
  wave set closes.
