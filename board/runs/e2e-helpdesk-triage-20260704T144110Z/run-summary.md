---
run_id: e2e-helpdesk-triage-20260704T144110Z
pack: helpdesk-triage
kind: spec-to-build-e2e
result: PASS
generated: 2026-07-04T14:41:10+00:00
---

# Run summary — e2e-helpdesk-triage-20260704T144110Z

Spec->build end-to-end for PROJECT-OS pack `helpdesk-triage` (`evals/e2e/sample-pack-2`). One pack driven sample-pack -> compiled stage-gated tickets -> all six AADL gates -> this committed summary.

## Outcome

- Result: **PASS**
- Goals: 5 (eval-harness, intent-classifier, queue-router, reply-drafter, ticket-ingest)
- Compiled tickets: 35 (zero hand-written)
- Gates walked: GATE-1..GATE-6 for every goal; 0 gate-order/deploy violation(s) across the walk
- D-5 health-check: **PASS**

## Pipeline driven (reused modules — nothing re-implemented)

1. `gateway_compile.run_pipeline` — compiled the copied pack into 35 self-contained stage-gated story tickets (zero hand-written; every board file is compiler output).
2. `stage_gate.gate_order_violations` / `production_deploy_violations` — drove every stage ticket to `done` in gate order (Stage 1->6) with no order violation at any step, and a NEGATIVE PROBE separately confirms the checker fires on a forced out-of-order state (so the clean walk is meaningful, not vacuous).
3. `run_workspace.create_workspace` — created the run workspace and staged the delivered board as the LOCAL D-5 artifact (scratch, gitignored, gc'd).
4. `board_lint.lint_tickets` + a `gateway_compile --gate-walk` probe — verified the delivered board is lint-clean and the gate-walk CLI exits 0.

## D-5 health-check — exactly what was verified

- [x] board_lint on the delivered board: 35 tickets, 0 violation(s)
- [x] all six AADL gates (GATE-1..GATE-6) walked to done for every goal; 0 gate-order/deploy violation(s) across the walk
- [x] gate-order checker proven to fire (negative probe): a forced out-of-order state (a stage-2 ticket advanced while its predecessor gate is open) is flagged
- [x] run workspace created and delivered board staged as the LOCAL artifact (e2e-helpdesk-triage-20260704T144110Z/workspace/delivered-board — scratch, gitignored)
- [x] probe `gateway_compile --gate-walk` over the delivered board exited 0 (0 = board may advance)
- [ ] pack-shipped tests: pack ships no runnable test suite (docs-only PROJECT-OS pack)

> D-5 semantics here = LOCAL artifact (the delivered board staged in the run workspace) + tests (this pack ships none) + health-check evidence. No external infra, no public push.

## Evidence (inlined)

`board/runs/*/workspace/` and any `evidence.json` are gitignored (only `run-summary.md` is tracked), so the machine-readable evidence lives here:

```json
{
  "run_id": "e2e-helpdesk-triage-20260704T144110Z",
  "pack": "helpdesk-triage",
  "pack_dir": "evals/e2e/sample-pack-2",
  "kind": "spec->build e2e (R12)",
  "generated_utc": "2026-07-04T14:41:10+00:00",
  "compiled": {
    "ticket_count": 35,
    "goals": [
      "eval-harness",
      "intent-classifier",
      "queue-router",
      "reply-drafter",
      "ticket-ingest"
    ],
    "hand_written_tickets": [],
    "zero_hand_written": true
  },
  "gate_walk": {
    "gates_walked": [
      1,
      2,
      3,
      4,
      5,
      6
    ],
    "per_stage": [
      {
        "stage": 1,
        "gate": "GATE-1",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      },
      {
        "stage": 2,
        "gate": "GATE-2",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      },
      {
        "stage": 3,
        "gate": "GATE-3",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      },
      {
        "stage": 4,
        "gate": "GATE-4",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      },
      {
        "stage": 5,
        "gate": "GATE-5",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      },
      {
        "stage": 6,
        "gate": "GATE-6",
        "tickets_advanced": 5,
        "order_violations": [],
        "deploy_violations": []
      }
    ],
    "gate_states": {
      "ticket-ingest": {
        "1": "done",
        "2": "done",
        "3": "done",
        "4": "done",
        "5": "done",
        "6": "done"
      },
      "intent-classifier": {
        "1": "done",
        "2": "done",
        "3": "done",
        "4": "done",
        "5": "done",
        "6": "done"
      },
      "reply-drafter": {
        "1": "done",
        "2": "done",
        "3": "done",
        "4": "done",
        "5": "done",
        "6": "done"
      },
      "queue-router": {
        "1": "done",
        "2": "done",
        "3": "done",
        "4": "done",
        "5": "done",
        "6": "done"
      },
      "eval-harness": {
        "1": "done",
        "2": "done",
        "3": "done",
        "4": "done",
        "5": "done",
        "6": "done"
      }
    },
    "all_goals_all_gates_done": true,
    "violations": [],
    "negative_probe": {
      "fired": true,
      "forced_ticket": "DAS-1003",
      "forced_stage": 2,
      "sample_violation": "DAS-1003: Stage-2 (Design) ticket is 'done' but GATE-1 (Planning) for goal 'ticket-ingest' is open \u2014 a stage may not advance past an open predecessor gate (AADL \u00a70)",
      "verifies": "gate_order_violations flags a stage>=2 ticket advanced while its predecessor gate is still open"
    }
  },
  "d5_health_check": {
    "passed": true,
    "board_lint": {
      "tickets": 35,
      "violations": [],
      "clean": true
    },
    "gate_walk_clean": true,
    "workspace_created": true,
    "workspace_path": "board/runs/e2e-helpdesk-triage-20260704T144110Z/workspace",
    "local_artifact": "board/runs/e2e-helpdesk-triage-20260704T144110Z/workspace/delivered-board",
    "probe": {
      "command": [
        "python3",
        "scripts/gateway_compile.py",
        "<ephemeral-scratch>/helpdesk-triage",
        "--gate-walk"
      ],
      "ephemeral": true,
      "note": "the pack arg was an ephemeral scratch copy (gc'd after the run; the literal path is machine-specific and intentionally elided); reproduce via `python3 scripts/e2e_run.py <pack_dir>`",
      "returncode": 0,
      "exit_ok": true,
      "verifies": "gate-walk CLI over the delivered board: 0 => board may advance"
    },
    "negative_probe": {
      "fired": true,
      "forced_ticket": "DAS-1003",
      "forced_stage": 2,
      "sample_violation": "DAS-1003: Stage-2 (Design) ticket is 'done' but GATE-1 (Planning) for goal 'ticket-ingest' is open \u2014 a stage may not advance past an open predecessor gate (AADL \u00a70)",
      "verifies": "gate_order_violations flags a stage>=2 ticket advanced while its predecessor gate is still open"
    },
    "pack_tests": {
      "present": false,
      "passed": null,
      "returncode": null,
      "detail": "pack ships no runnable test suite (docs-only PROJECT-OS pack)"
    },
    "checklist": [
      {
        "ok": true,
        "label": "board_lint on the delivered board: 35 tickets, 0 violation(s)"
      },
      {
        "ok": true,
        "label": "all six AADL gates (GATE-1..GATE-6) walked to done for every goal; 0 gate-order/deploy violation(s) across the walk"
      },
      {
        "ok": true,
        "label": "gate-order checker proven to fire (negative probe): a forced out-of-order state (a stage-2 ticket advanced while its predecessor gate is open) is flagged"
      },
      {
        "ok": true,
        "label": "run workspace created and delivered board staged as the LOCAL artifact (e2e-helpdesk-triage-20260704T144110Z/workspace/delivered-board \u2014 scratch, gitignored)"
      },
      {
        "ok": true,
        "label": "probe `gateway_compile --gate-walk` over the delivered board exited 0 (0 = board may advance)"
      },
      {
        "ok": null,
        "label": "pack-shipped tests: pack ships no runnable test suite (docs-only PROJECT-OS pack)"
      }
    ]
  },
  "result": "PASS"
}
```
