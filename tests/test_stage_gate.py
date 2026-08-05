#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import board_lint
import gateway_compile as gc
import stage_gate as sg

_KNOWN_ROLES = board_lint.load_known_roles()


def fm(**over: str) -> dict[str, str]:
    base = {
        "id": "DAS-9000",
        "title": "t",
        "status": "todo",
        "assignee": "sre-eng",
        "author": "ceo",
        "dept": "engineering",
        "priority": "p1",
        "goal": "acme-agent",
        "created": "2026-07-03",
        "updated": "2026-07-03",
    }
    base.update(over)
    return base


def pair(**over: str) -> tuple[Path, dict[str, str]]:
    return (Path(f"{over.get('id', 'DAS-9000')}.md"), fm(**over))


def _stage_board(*, stage4: str, stage5: str) -> list[tuple[Path, dict[str, str]]]:
    return [
        pair(id="DAS-9004", stage="GATE-4", status=stage4, title="Stage 4"),
        pair(id="DAS-9005", stage="GATE-5", status=stage5, title="Stage 5"),
    ]


def test_stage_of_reads_gate_field() -> None:
    assert sg.stage_of(fm(stage="GATE-5")) == 5
    assert sg.stage_of(fm(stage="GATE-1")) == 1
    assert sg.stage_of(fm()) is None


def test_gate_status_done_vs_open() -> None:
    tickets = _stage_board(stage4="done", stage5="todo")
    gs = sg.gate_status(tickets)
    assert gs["acme-agent"][4] == "done"
    assert gs["acme-agent"][5] == "open"


def test_stage5_blocked_while_gate4_open() -> None:

    tickets = _stage_board(stage4="todo", stage5="in_progress")
    v = sg.gate_order_violations(tickets)
    assert len(v) == 1
    assert "DAS-9005" in v[0]
    assert "GATE-4" in v[0]


def test_stage5_todo_while_gate4_open_is_not_a_violation() -> None:

    tickets = _stage_board(stage4="todo", stage5="todo")
    assert sg.gate_order_violations(tickets) == []


def test_stage5_advances_once_gate4_done() -> None:

    tickets = _stage_board(stage4="done", stage5="in_progress")
    assert sg.gate_order_violations(tickets) == []


def test_stage5_done_while_gate4_open_is_a_violation() -> None:
    tickets = _stage_board(stage4="in_review", stage5="done")
    v = sg.gate_order_violations(tickets)
    assert len(v) == 1 and "DAS-9005" in v[0]


def test_no_prior_stage_ticket_cannot_verify_is_skipped() -> None:

    tickets = [pair(id="DAS-9005", stage="GATE-5", status="in_progress")]
    assert sg.gate_order_violations(tickets) == []


def test_is_production_deploy_matches_stage_and_labels() -> None:
    matcher = sg.load_gate5_matcher()
    assert matcher is not None
    assert sg.is_production_deploy(fm(stage="GATE-5"), matcher)
    assert sg.is_production_deploy(fm(labels="[deploy]"), matcher)
    assert sg.is_production_deploy(fm(labels="deploy"), matcher)
    assert not sg.is_production_deploy(fm(stage="GATE-3"), matcher)
    assert not sg.is_production_deploy(fm(), matcher)


def test_gate5_open_blocks_production_deploy_action() -> None:


    tickets = [
        pair(id="DAS-9005", stage="GATE-5", status="todo", title="Stage 5 gate"),
        pair(id="DAS-9010", labels="[deploy]", status="in_progress", title="push to prod"),
    ]
    v = sg.production_deploy_violations(tickets)
    assert any("DAS-9010" in x and "GATE-5" in x for x in v)


def test_gate5_deploy_action_allowed_once_gate5_done() -> None:
    tickets = [
        pair(id="DAS-9005", stage="GATE-5", status="done", approval="human:founder",
             title="Stage 5 gate"),
        pair(id="DAS-9010", labels="[deploy]", status="in_progress", title="push to prod"),
    ]
    assert sg.production_deploy_violations(tickets) == []


def test_gate5_closed_without_a_named_human_approval_fails_closed() -> None:
    tickets = [pair(id="DAS-9005", stage="GATE-5", status="done", title="Stage 5 gate")]
    v = sg.production_deploy_violations(tickets)
    assert any("DAS-9005" in x and "no named human approval" in x for x in v)


@pytest.mark.parametrize("placeholder", ["", "pending", "TBD", "n/a", "none"])
def test_gate5_closed_with_a_placeholder_approval_fails_closed(placeholder: str) -> None:
    tickets = [pair(id="DAS-9005", stage="GATE-5", status="done", approval=placeholder)]
    v = sg.production_deploy_violations(tickets)
    assert any("DAS-9005" in x and "no named human approval" in x for x in v)


def test_auto_approved_gate5_deploy_is_blocked() -> None:

    tickets = [pair(id="DAS-9010", labels="[deploy, gate-5]", approval="auto", status="todo")]
    v = sg.production_deploy_violations(tickets)
    assert any("DAS-9010" in x and "never-auto-approve" in x for x in v)


def test_deployment_gate_ticket_not_flagged_against_itself() -> None:


    tickets = [pair(id="DAS-9005", stage="GATE-5", status="todo", title="Stage 5")]
    assert sg.production_deploy_violations(tickets) == []


def test_board_lint_r12_flags_gate_jump() -> None:
    tickets = _stage_board(stage4="todo", stage5="in_progress")
    errors = board_lint.lint_tickets(tickets, _KNOWN_ROLES)
    assert any("GATE-4" in e for e in errors)


def test_board_lint_r12_clean_when_gate_order_respected() -> None:
    tickets = _stage_board(stage4="done", stage5="in_progress")
    errors = board_lint.lint_tickets(tickets, _KNOWN_ROLES)
    assert errors == [], errors


def test_board_lint_unaffected_without_stage_tickets() -> None:

    tickets = [pair(id="DAS-9000", status="todo")]
    assert board_lint.lint_tickets(tickets, _KNOWN_ROLES) == []


def _write_board(tmp_path: Path, tickets: list[tuple[str, dict[str, str]]]) -> Path:
    board = tmp_path / "board-tickets"
    board.mkdir(parents=True, exist_ok=True)
    for tid, fields in tickets:
        lines = ["---"]
        lines += [f"{k}: {v}" for k, v in fields.items()]
        lines += ["---", "", "## Description", "body", ""]
        (board / f"{tid}.md").write_text("\n".join(lines), encoding="utf-8")
    return board


def test_walk_gates_blocks_and_lists_open_gates(tmp_path: Path) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9004", fm(id="DAS-9004", stage="GATE-4", status="todo")),
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="in_progress")),
    ])
    walk = sg.walk_gates(board)
    assert not walk.ok
    assert walk.order_violations
    assert ("acme-agent", 4, "DAS-9004") in walk.open_blocking_gates


def test_walk_gates_ok_when_gate_order_respected(tmp_path: Path) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9004", fm(id="DAS-9004", stage="GATE-4", status="done")),
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="in_progress")),
    ])
    walk = sg.walk_gates(board)
    assert walk.ok


def test_emit_gate_cards_conforms_to_schema_and_is_idempotent(tmp_path: Path) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9004", fm(id="DAS-9004", stage="GATE-4", status="todo")),
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="todo")),
    ])
    walk = sg.walk_gates(board)
    interrupts = tmp_path / "interrupts"
    written = sg.emit_gate_cards(walk, interrupts)
    assert written, "expected at least one gate card for the open blocking gate"

    card = json.loads(written[0].read_text(encoding="utf-8"))

    for key in ("question", "options", "ticket", "payload", "created_by"):
        assert key in card
    assert card["question"] and isinstance(card["question"], str)
    assert isinstance(card["options"], list) and card["options"]
    assert card["ticket"].startswith("DAS-")
    assert isinstance(card["payload"], dict)
    assert card["created_by"] in _KNOWN_ROLES


    again = sg.emit_gate_cards(walk, interrupts)
    assert again == []


def test_gate5_card_marks_never_auto_approve(tmp_path: Path) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="todo")),
        ("DAS-9006", fm(id="DAS-9006", stage="GATE-6", status="todo")),
    ])
    walk = sg.walk_gates(board)
    cards = sg.emit_gate_cards(walk, tmp_path / "interrupts")
    gate5 = [json.loads(c.read_text()) for c in cards if c.name.endswith("gate5.json")]
    assert gate5 and gate5[0]["payload"]["never_auto_approve"] is True


def test_maintenance_schedule_ws4_heartbeat_and_ws6_evals() -> None:
    sched = sg.maintenance_schedule()
    assert sched["gate"] == "GATE-6"
    assert sched["never_auto_approve"] is True
    assert sched["installs_os_scheduler_entry"] is False
    kinds = {r["kind"] for r in sched["recurring_runs"]}
    assert "ws4-heartbeat" in kinds
    assert "ws6-eval" in kinds

    cmds = " ".join(" ".join(r["command"]) for r in sched["recurring_runs"])
    assert "loop_controller.py" in cmds
    assert "agent_eval.py" in cmds


_MAINTENANCE_BASE_KEYS = {"name", "kind", "command", "cadence", "config", "safety"}
_MAINTENANCE_ALLOWED_KEYS = _MAINTENANCE_BASE_KEYS


def _assert_entry_conforms(r: dict, kinds: list[str]) -> None:
    label = r.get("name", "<unnamed>")


    missing = _MAINTENANCE_BASE_KEYS - r.keys()
    assert not missing, f"{label}: missing required key(s) {sorted(missing)}"


    extra = r.keys() - _MAINTENANCE_ALLOWED_KEYS
    assert not extra, f"{label}: unrecognized key(s) {sorted(extra)} (typo or rename?)"


    config_path = REPO_ROOT / r["config"]
    assert config_path.is_file(), (
        f"{label}: config {r['config']!r} does not resolve to a file on disk"
    )


    command = r["command"]
    assert isinstance(command, list) and command, f"{label}: command must be a non-empty list"
    if command[0] == "python3":
        assert len(command) >= 2, f"{label}: python3 command has no script argument"
        script_path = REPO_ROOT / command[1]
        assert script_path.is_file(), (
            f"{label}: command[1] {command[1]!r} does not resolve to a file on disk"
        )

    kinds.append(r["kind"])


def test_maintenance_schedule_entries_conform_to_schema() -> None:
    sched = sg.maintenance_schedule()
    runs = sched["recurring_runs"]
    assert runs, "maintenance_schedule() returned no recurring_runs entries"

    kinds: list[str] = []
    for r in runs:
        _assert_entry_conforms(r, kinds)

    assert len(kinds) == len(set(kinds)), f"duplicate 'kind' values across entries: {kinds}"


def test_new_config_less_entry_fails_schema() -> None:
    sched = sg.maintenance_schedule()
    scratch = list(sched["recurring_runs"])
    scratch.append({
        "name": "ws-z-future-health",
        "kind": "ws-z-eval",
        "command": ["python3", "scripts/agent_eval.py"],
        "cadence": "daily",

        "safety": "hypothetical future run with no linked runbook",
    })

    kinds: list[str] = []
    with pytest.raises(AssertionError, match="missing required key.*config"):
        for r in scratch:
            _assert_entry_conforms(r, kinds)


    real_kinds: list[str] = []
    for r in sg.maintenance_schedule()["recurring_runs"]:
        _assert_entry_conforms(r, real_kinds)


_MANIFEST = """\
name: {slug}
mission: >
  An AI support agent that resolves tier-1 billing questions in-chat for {slug}
  customers, deflecting tickets from the human queue while never fabricating state.
constraints:
  - "PII: mask account numbers before any model call (tightens org data baseline)"
stack:
  languages: [python]
budget:
  money: "USD 1200 / month ceiling"
success_metrics:
  - metric: "tier-1 containment rate"
    target: ">= 55%"
"""

_DISCOVERY = "# Founder Discovery\n\n" + "".join(
    f"Q{i}: discovery question number {i}?\nA{i}: the founder answer number {i}.\n\n"
    for i in range(1, 12)
)

_QUEUE = """\
# APPROVED-GOAL-QUEUE — {slug}

STATUS: TASDIQLANDI 2026-07-03 (Founder approved)

| order | goal_slug | outcome | why_now | research_basis | owner | status | ticket_refs |
|---|---|---|---|---|---|---|---|
| 1 | billing-agent | Deflect 55% of tier-1 billing tickets in-chat | launch | scan | cpo | founder_approved | - |
"""

_STAGE_DIRS = (
    "01-planning", "02-design", "03-development",
    "04-testing", "05-deployment", "06-maintenance",
)


def _build_pack(tmp_path: Path, slug: str = "acme-helpdesk") -> Path:
    root = tmp_path / "projects" / slug
    for d in _STAGE_DIRS:
        (root / "docs" / d).mkdir(parents=True, exist_ok=True)
    (root / "PROJECT-OS.yaml").write_text(_MANIFEST.format(slug=slug), encoding="utf-8")
    (root / "docs" / "01-planning" / "discovery.md").write_text(_DISCOVERY, encoding="utf-8")
    (root / "APPROVED-GOAL-QUEUE.md").write_text(_QUEUE.format(slug=slug), encoding="utf-8")
    (root / "README.md").write_text(f"# {slug}\n\nCharter.\n", encoding="utf-8")
    return root


def test_freshly_compiled_board_is_stage_gate_clean(tmp_path: Path) -> None:
    root = _build_pack(tmp_path)
    res = gc.run_pipeline(root)
    assert res.ok, [str(e) for e in res.errors]
    tickets = board_lint.load_tickets(root / "board-tickets")


    assert sg.stage_gate_violations(tickets) == []
    walk = sg.walk_gates(root / "board-tickets")
    assert walk.ok


def test_cli_returns_1_on_gate_violation(tmp_path: Path, capsys) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9004", fm(id="DAS-9004", stage="GATE-4", status="todo")),
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="in_progress")),
    ])
    rc = sg.main([str(board)])
    assert rc == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_cli_returns_0_when_clean(tmp_path: Path, capsys) -> None:
    board = _write_board(tmp_path, [
        ("DAS-9004", fm(id="DAS-9004", stage="GATE-4", status="done")),
        ("DAS-9005", fm(id="DAS-9005", stage="GATE-5", status="in_progress")),
    ])
    rc = sg.main([str(board)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_gateway_compile_gate_walk_mode(tmp_path: Path, capsys) -> None:
    root = _build_pack(tmp_path)
    res = gc.run_pipeline(root)
    assert res.ok
    rc = gc.main([str(root), "--gate-walk"])

    assert rc == 0
    assert "gate walk" in capsys.readouterr().out.lower()
