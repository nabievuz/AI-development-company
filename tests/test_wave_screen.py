
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import guardrail_dispatch as gd

_ROUTING = """\
# Role routing

| Role key | Display name | Dept | Reports to (reviewer) |
|---|---|---|---|
| `backend-eng-1` | Backend Engineer 1 | engineering | Backend EM |
| `backend-em` | Backend EM | engineering | CTO |
| `cmo` | CMO | marketing | CEO |
"""


def _ticket(board: Path, tid: str, *, assignee: str, dept: str) -> Path:
    body = (
        f"---\nid: {tid}\ntitle: t\nstatus: todo\nassignee: {assignee}\nauthor: cto\n"
        f"dept: {dept}\npriority: p1\ncreated: 2026-07-04\nupdated: 2026-07-04\n---\n\nBody.\n"
    )
    p = board / f"{tid}-fixture.md"
    p.write_text(body, encoding="utf-8")
    return p


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    routing = tmp_path / "ROUTING.md"
    routing.write_text(_ROUTING, encoding="utf-8")
    board = tmp_path / "tickets"
    board.mkdir()
    return routing, board


def test_in_scope_ticket_accepted(tmp_path: Path) -> None:
    routing, board = _setup(tmp_path)
    t = _ticket(board, "DAS-1001", assignee="backend-eng-1", dept="engineering")
    res = gd.screen_wave_inputs([t], routing_path=routing, board_dir=board)
    assert res.accepted == ["DAS-1001"]
    assert res.all_accepted is True and res.rejected == []


def test_wrong_department_rejected_and_rerouted(tmp_path: Path) -> None:
    routing, board = _setup(tmp_path)

    t = _ticket(board, "DAS-1002", assignee="backend-eng-1", dept="marketing")
    res = gd.screen_wave_inputs([t], routing_path=routing, board_dir=board)
    assert res.accepted == []
    assert res.rejected_ids == ["DAS-1002"]
    r = res.rejected[0]
    assert r["reroute_to"] == "marketing"
    assert "wrong-department" in r["feedback"]


def test_gate_open_rejected(tmp_path: Path) -> None:
    routing, board = _setup(tmp_path)
    t = _ticket(board, "DAS-1003", assignee="backend-eng-1", dept="engineering")
    res = gd.screen_wave_inputs([t], routing_path=routing, board_dir=board, gate_open_ids={"DAS-1003"})
    assert res.rejected_ids == ["DAS-1003"]
    assert "gate-open" in res.rejected[0]["feedback"]


def test_mixed_wave_partitions(tmp_path: Path) -> None:
    routing, board = _setup(tmp_path)
    ok = _ticket(board, "DAS-2001", assignee="backend-eng-1", dept="engineering")
    bad = _ticket(board, "DAS-2002", assignee="backend-eng-1", dept="marketing")
    res = gd.screen_wave_inputs([ok, bad], routing_path=routing, board_dir=board)
    assert res.accepted == ["DAS-2001"]
    assert res.rejected_ids == ["DAS-2002"]
    assert res.all_accepted is False


def test_cli_screen_wave_exits_nonzero_on_reject(tmp_path: Path) -> None:
    routing, board = _setup(tmp_path)
    _ticket(board, "DAS-3001", assignee="backend-eng-1", dept="engineering")
    _ticket(board, "DAS-3002", assignee="backend-eng-1", dept="marketing")
    rc = gd.main(["--screen-wave", str(board), "--routing", str(routing), "--board", str(board)])
    assert rc == 1
    (board / "DAS-3002-fixture.md").unlink()
    rc2 = gd.main(["--screen-wave", str(board), "--routing", str(routing), "--board", str(board)])
    assert rc2 == 0
