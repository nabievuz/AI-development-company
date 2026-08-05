
from __future__ import annotations

import json
import socketserver
import sys
import threading
import time
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import cockpit
import cockpit_html
import interrupt_roundtrip as irt


def _write_card(interrupts_dir: Path, ticket_id: str, options: list[str], cid: str) -> Path:
    card = {
        "question": "Ship despite the failing canary?",
        "options": options,
        "ticket": ticket_id,
        "payload": {"wave": 2, "note": "pre-interrupt context"},
        "created_by": "sre-eng",
    }
    path = interrupts_dir / f"{cid}.json"
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


def _write_interrupted_ticket(board_dir: Path, ticket_id: str, resume_value: str | None) -> Path:
    body = (
        f"---\n"
        f"id: {ticket_id}\n"
        f"title: A parked ticket\n"
        f"status: interrupted\n"
        f"assignee: sre-eng\n"
        f"author: cto\n"
        f"dept: engineering\n"
        f"priority: p1\n"
        f"created: 2026-07-04\n"
        f"updated: 2026-07-04\n"
        f"---\n\n"
        f"Body text describing the parked work.\n"
    )
    if resume_value is not None:
        body += f"\nresume:{resume_value}\n"
    path = board_dir / f"{ticket_id}-fixture.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_action_console_surfaces_card_with_resume_stub(tmp_path: Path) -> None:
    interrupts = tmp_path / "interrupts"
    interrupts.mkdir()
    _write_card(interrupts, "DAS-7002", ["ship", "hold"], "DAS-7002-stall-1")
    text = "\n".join(cockpit.panel_action_console(interrupts))
    assert "DAS-7002" in text
    assert "resume:ship" in text and "resume:hold" in text
    assert "<60s" in text


def test_roundtrip_resume_under_60s(tmp_path: Path) -> None:
    board = tmp_path / "tickets"
    board.mkdir()
    interrupts = tmp_path / "interrupts"
    interrupts.mkdir()
    ticket_id = "DAS-7001"

    card_path = _write_card(interrupts, ticket_id, ["ship", "hold"], "DAS-7001-stall-1")


    _write_interrupted_ticket(board, ticket_id, resume_value="hold")


    start = time.perf_counter()
    resumed = irt.detect_resumed_tickets(board, interrupts)
    elapsed = time.perf_counter() - start

    assert len(resumed) == 1
    rt = resumed[0]
    assert rt.ticket_id == ticket_id
    assert rt.resume_value == "hold"
    assert rt.card_path == card_path
    assert "hold" in rt.injection_text and "RESUME CONTEXT" in rt.injection_text
    assert elapsed < 5.0


def test_invalid_resume_value_is_skipped(tmp_path: Path) -> None:
    board = tmp_path / "tickets"
    board.mkdir()
    interrupts = tmp_path / "interrupts"
    interrupts.mkdir()
    _write_card(interrupts, "DAS-7003", ["ship", "hold"], "DAS-7003-stall-1")
    _write_interrupted_ticket(board, "DAS-7003", resume_value="explode")

    assert irt.detect_resumed_tickets(board, interrupts) == []


def test_unanswered_ticket_stays_parked(tmp_path: Path) -> None:
    board = tmp_path / "tickets"
    board.mkdir()
    interrupts = tmp_path / "interrupts"
    interrupts.mkdir()
    _write_card(interrupts, "DAS-7005", ["ship", "hold"], "DAS-7005-stall-1")
    _write_interrupted_ticket(board, "DAS-7005", resume_value=None)
    assert irt.detect_resumed_tickets(board, interrupts) == []


def test_serve_smoke_get_200(tmp_path: Path) -> None:
    interrupts = tmp_path / "interrupts"
    interrupts.mkdir()
    _write_card(interrupts, "DAS-7004", ["ship", "hold"], "DAS-7004-stall-1")

    handler = cockpit_html._make_handler(
        events_path=tmp_path / ".events.jsonl",
        wave_log=tmp_path / ".wave-log",
        experiments=tmp_path / "experiments",
        board_path=tmp_path,
        mem_store=tmp_path / ".arcrift-outbox.jsonl",
        mem_config=tmp_path / "memory_governance.yaml",
        interrupts=interrupts,
        refresh_s=30,
    )


    with socketserver.TCPServer(("127.0.0.1", 0), handler) as srv:
        port = srv.server_address[1]
        worker = threading.Thread(target=srv.handle_request, daemon=True)
        worker.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8")
        finally:
            worker.join(timeout=5)

    assert "Action Console" in body
    assert "DAS-7004" in body
