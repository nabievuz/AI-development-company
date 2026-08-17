from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import loop_controller as lc


def _org(tmp_path: Path) -> Path:
    org = tmp_path / "org.yaml"
    org.write_text(
        textwrap.dedent(
            """\
            gates: [GATE-1, GATE-2]
            roles:
              backend-eng-1: {model: sonnet}
            """
        ),
        encoding="utf-8",
    )
    return org


def _board(tmp_path: Path) -> Path:
    board = tmp_path / "tickets"
    board.mkdir(parents=True, exist_ok=True)
    return board


def _write(board: Path, ticket_id: str, **fields: str) -> None:
    lines = [f"id: {ticket_id}", "assignee: backend-eng-1"]
    lines += [f"{key}: {value}" for key, value in fields.items()]
    body = "---\n" + "\n".join(lines) + "\n---\n\nbody\n"
    (board / f"{ticket_id}-work.md").write_text(body, encoding="utf-8")


def test_no_actionable_work_on_an_empty_board(tmp_path: Path) -> None:
    assert lc.actionable_work_exists(_board(tmp_path), _org(tmp_path)) is False


def test_a_todo_ticket_is_actionable_work(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="todo", zone="scripts")
    assert lc.actionable_work_exists(board, _org(tmp_path)) is True


def test_an_in_progress_ticket_is_pending_work(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="in_progress", zone="scripts")
    assert lc.actionable_work_exists(board, _org(tmp_path)) is True


def test_a_blocked_ticket_is_not_pending_work(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="blocked", zone="scripts")
    assert lc.actionable_work_exists(board, _org(tmp_path)) is False


def test_a_dependency_blocked_ticket_is_not_pending_work(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="blocked", zone="a")
    _write(board, "DAS-2", status="todo", zone="b", depends_on="[DAS-1]")
    assert lc.actionable_work_exists(board, _org(tmp_path)) is False


def test_a_missing_board_reports_no_work_instead_of_crashing(tmp_path: Path) -> None:
    assert lc.actionable_work_exists(tmp_path / "absent", _org(tmp_path)) is False


def test_a_missing_org_model_reports_no_work_instead_of_crashing(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="todo", zone="scripts")
    assert lc.actionable_work_exists(board, tmp_path / "absent.yaml") is False


def test_tick_reads_the_board_when_pending_work_is_not_supplied(tmp_path: Path) -> None:
    board = _board(tmp_path)
    _write(board, "DAS-1", status="todo", zone="scripts")
    flags = tmp_path / "features.yaml"
    flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")

    result = lc.tick(
        schedule_path=tmp_path / "schedule.yaml",
        loop_config=tmp_path / "loop.yaml",
        experiments=tmp_path / "experiments",
        metrics_history=tmp_path / "history.jsonl",
        events_path=tmp_path / "events.jsonl",
        budgets_path=tmp_path / "budgets.yaml",
        feature_flags_path=flags,
        board_dir=board,
        org_path=_org(tmp_path),
        trigger="cron_tick",
    )
    assert result["decision"]["action"] == "dispatch"


def test_tick_finds_no_work_on_an_empty_board(tmp_path: Path) -> None:
    flags = tmp_path / "features.yaml"
    flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")

    result = lc.tick(
        schedule_path=tmp_path / "schedule.yaml",
        loop_config=tmp_path / "loop.yaml",
        experiments=tmp_path / "experiments",
        metrics_history=tmp_path / "history.jsonl",
        events_path=tmp_path / "events.jsonl",
        budgets_path=tmp_path / "budgets.yaml",
        feature_flags_path=flags,
        board_dir=_board(tmp_path),
        org_path=_org(tmp_path),
        trigger="cron_tick",
    )
    assert result["decision"]["action"] != "dispatch"


def test_an_explicit_pending_work_claim_still_wins(tmp_path: Path) -> None:
    flags = tmp_path / "features.yaml"
    flags.write_text("heartbeat_enabled: false\n", encoding="utf-8")

    result = lc.tick(
        schedule_path=tmp_path / "schedule.yaml",
        loop_config=tmp_path / "loop.yaml",
        experiments=tmp_path / "experiments",
        metrics_history=tmp_path / "history.jsonl",
        events_path=tmp_path / "events.jsonl",
        budgets_path=tmp_path / "budgets.yaml",
        feature_flags_path=flags,
        board_dir=_board(tmp_path),
        org_path=_org(tmp_path),
        trigger="cron_tick",
        pending_work=True,
    )
    assert result["decision"]["action"] == "dispatch"
