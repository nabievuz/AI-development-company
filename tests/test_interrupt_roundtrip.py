
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from board_lint import warn_interrupted_idempotency
from interrupt_roundtrip import (
    ResumedTicket,
    build_resume_injection,
    detect_resumed_tickets,
    parse_resume_marker,
    validate_resume_value,
)

_CARD_TEMPLATE = {
    "question": "Which deployment strategy should we use?",
    "options": ["blue-green", "canary", "rolling"],
    "ticket": "DAS-9100",
    "payload": {"current_stage": "GATE-3", "risk": "medium"},
    "created_by": "backend-eng-1",
}


def _make_ticket_file(
    tmp_path: Path,
    ticket_id: str,
    status: str,
    resume_line: str = "",
    body_extra: str = "",
) -> Path:
    path = tmp_path / f"{ticket_id}-fixture.md"
    lines = [
        "---",
        f"id: {ticket_id}",
        "title: Fixture ticket",
        f"status: {status}",
        "assignee: backend-eng-1",
        "author: ceo",
        "dept: engineering",
        "priority: p1",
        "created: 2026-07-03",
        "updated: 2026-07-03",
        "---",
        "",
        "## Description",
        "Some description.",
    ]
    if body_extra:
        lines.append(body_extra)
    if resume_line:
        lines.append(resume_line)
    lines += ["", "## Log", "### 2026-07-03 — CEO", "Created."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_card_file(
    interrupts_dir: Path,
    card_id: str,
    card: dict,
) -> Path:
    interrupts_dir.mkdir(parents=True, exist_ok=True)
    path = interrupts_dir / f"{card_id}.json"
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return path


def test_parse_resume_marker_found() -> None:
    text = textwrap.dedent(
        """\
        ---
        id: DAS-9100
        status: interrupted
        ---

        ## Description
        Some work.

        resume:blue-green

        ## Log
        Created.
        """
    )
    assert parse_resume_marker(text) == "blue-green"


def test_parse_resume_marker_absent() -> None:
    text = textwrap.dedent(
        """\
        ---
        id: DAS-9100
        status: interrupted
        ---

        ## Description
        Some work.

        ## Log
        Created.
        """
    )
    assert parse_resume_marker(text) is None


def test_parse_resume_marker_strips_whitespace() -> None:
    text = "---\nid: DAS-9100\nstatus: interrupted\n---\nresume:  canary  \n"
    assert parse_resume_marker(text) == "canary"


def test_parse_resume_marker_ignores_frontmatter() -> None:
    text = textwrap.dedent(
        """\
        ---
        id: DAS-9100
        status: interrupted
        resume: ignored-in-frontmatter
        ---

        ## Description
        No resume marker in body.
        """
    )

    assert parse_resume_marker(text) is None


def test_validate_resume_value_valid() -> None:
    card = {"options": ["blue-green", "canary", "rolling"]}
    assert validate_resume_value("canary", card) is True


def test_validate_resume_value_invalid() -> None:
    card = {"options": ["blue-green", "canary", "rolling"]}
    assert validate_resume_value("unknown", card) is False


def test_validate_resume_value_case_sensitive() -> None:
    card = {"options": ["Blue-Green", "canary"]}
    assert validate_resume_value("blue-green", card) is False
    assert validate_resume_value("Blue-Green", card) is True


def test_validate_resume_value_empty_options() -> None:
    assert validate_resume_value("anything", {"options": []}) is False


def test_validate_resume_value_missing_options() -> None:
    assert validate_resume_value("anything", {}) is False


def test_build_resume_injection_contains_value() -> None:
    card = dict(_CARD_TEMPLATE)
    text = build_resume_injection("blue-green", card)
    assert "blue-green" in text


def test_build_resume_injection_contains_question() -> None:
    card = dict(_CARD_TEMPLATE)
    text = build_resume_injection("canary", card)
    assert "Which deployment strategy" in text


def test_build_resume_injection_contains_options() -> None:
    card = dict(_CARD_TEMPLATE)
    text = build_resume_injection("rolling", card)
    assert "canary" in text
    assert "blue-green" in text
    assert "rolling" in text


def test_build_resume_injection_contains_idempotency_warning() -> None:
    card = dict(_CARD_TEMPLATE)
    text = build_resume_injection("canary", card)

    assert "dempoten" in text.lower() or "guard" in text.lower()


def test_build_resume_injection_contains_payload() -> None:
    card = dict(_CARD_TEMPLATE)
    text = build_resume_injection("blue-green", card)
    assert "GATE-3" in text


def test_roundtrip_full(tmp_path: Path) -> None:
    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    interrupts_dir = tmp_path / "interrupts"


    card = dict(_CARD_TEMPLATE)
    card["ticket"] = "DAS-9100"
    _make_card_file(interrupts_dir, "DAS-9100-1", card)
    _make_ticket_file(board_dir, "DAS-9100", "interrupted")


    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert resumed == [], "Unanswered ticket must stay parked"


    _make_ticket_file(board_dir, "DAS-9100", "interrupted", resume_line="resume:blue-green")


    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert len(resumed) == 1, "Exactly one resumed ticket expected"

    rt: ResumedTicket = resumed[0]
    assert rt.ticket_id == "DAS-9100"
    assert rt.resume_value == "blue-green"


    assert "blue-green" in rt.injection_text, (
        f"Resume value 'blue-green' not found in injection_text:\n{rt.injection_text}"
    )

    assert (
        "dempoten" in rt.injection_text.lower()
        or "guard" in rt.injection_text.lower()
    ), "Idempotency reminder missing from injection_text"


def test_roundtrip_unanswered_stays_parked(tmp_path: Path) -> None:
    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    interrupts_dir = tmp_path / "interrupts"
    _make_card_file(interrupts_dir, "DAS-9101-1", {**_CARD_TEMPLATE, "ticket": "DAS-9101"})
    _make_ticket_file(board_dir, "DAS-9101", "interrupted")

    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert resumed == [], "Unanswered gate must never be auto-dispatched"


def test_roundtrip_invalid_value_skipped(tmp_path: Path) -> None:
    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    interrupts_dir = tmp_path / "interrupts"
    _make_card_file(interrupts_dir, "DAS-9102-1", {**_CARD_TEMPLATE, "ticket": "DAS-9102"})
    _make_ticket_file(board_dir, "DAS-9102", "interrupted", resume_line="resume:INVALID-VALUE")

    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert resumed == [], "Invalid resume value must be rejected (not dispatched)"


def test_roundtrip_missing_card_skipped(tmp_path: Path) -> None:
    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    interrupts_dir = tmp_path / "interrupts"
    interrupts_dir.mkdir()
    _make_ticket_file(board_dir, "DAS-9103", "interrupted", resume_line="resume:blue-green")

    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert resumed == [], "Missing card must prevent dispatch (no auto-answer)"


def test_roundtrip_non_interrupted_ticket_ignored(tmp_path: Path) -> None:
    board_dir = tmp_path / "tickets"
    board_dir.mkdir()
    interrupts_dir = tmp_path / "interrupts"

    _make_ticket_file(
        board_dir, "DAS-9104", "in_progress", resume_line="resume:blue-green"
    )
    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    assert resumed == [], "Non-interrupted tickets must not be treated as resumed"


def test_idempotency_warning_emitted_for_unguarded_interrupted(tmp_path: Path) -> None:
    from board_lint import warn_interrupted_idempotency

    ticket_path = tmp_path / "DAS-9200-fixture.md"
    ticket_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: DAS-9200
            title: Fixture
            status: interrupted
            assignee: backend-eng-1
            author: ceo
            dept: engineering
            priority: p1
            created: 2026-07-03
            updated: 2026-07-03
            ---

            ## Description
            This ticket will merge the PR and send a notification.

            ## Log
            Created.
            """
        ),
        encoding="utf-8",
    )
    fm = {
        "id": "DAS-9200",
        "status": "interrupted",
        "assignee": "backend-eng-1",
        "author": "ceo",
    }
    warnings = warn_interrupted_idempotency([(ticket_path, fm)])
    assert warnings, "Expected at least one idempotency warning"
    assert "DAS-9200" in warnings[0]
    assert "merge" in warnings[0] or "send" in warnings[0]


def test_idempotency_no_warning_when_guarded(tmp_path: Path) -> None:
    ticket_path = tmp_path / "DAS-9201-fixture.md"
    ticket_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: DAS-9201
            title: Fixture
            status: interrupted
            assignee: backend-eng-1
            author: ceo
            dept: engineering
            priority: p1
            created: 2026-07-03
            updated: 2026-07-03
            ---

            ## Description
            This ticket will merge the PR — idempotent (guard: check-if-already-done).

            ## Log
            Created.
            """
        ),
        encoding="utf-8",
    )
    fm = {
        "id": "DAS-9201",
        "status": "interrupted",
        "assignee": "backend-eng-1",
        "author": "ceo",
    }
    warnings = warn_interrupted_idempotency([(ticket_path, fm)])
    assert not warnings, f"Expected no warnings but got: {warnings}"


def test_idempotency_no_warning_for_non_interrupted(tmp_path: Path) -> None:
    ticket_path = tmp_path / "DAS-9202-fixture.md"
    ticket_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: DAS-9202
            title: Fixture
            status: in_progress
            assignee: backend-eng-1
            author: ceo
            dept: engineering
            priority: p1
            created: 2026-07-03
            updated: 2026-07-03
            ---

            ## Description
            This ticket will merge the PR and send a notification.

            ## Log
            Created.
            """
        ),
        encoding="utf-8",
    )
    fm = {
        "id": "DAS-9202",
        "status": "in_progress",
        "assignee": "backend-eng-1",
        "author": "ceo",
    }
    warnings = warn_interrupted_idempotency([(ticket_path, fm)])
    assert not warnings, f"Non-interrupted ticket must not be warned: {warnings}"


def test_idempotency_clean_board_no_interrupted(tmp_path: Path) -> None:
    ticket_path = tmp_path / "DAS-9203-fixture.md"
    ticket_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: DAS-9203
            title: Fixture
            status: todo
            assignee: backend-eng-1
            author: ceo
            dept: engineering
            priority: p1
            created: 2026-07-03
            updated: 2026-07-03
            ---

            ## Description
            A normal todo ticket.

            ## Log
            Created.
            """
        ),
        encoding="utf-8",
    )
    fm = {
        "id": "DAS-9203",
        "status": "todo",
        "assignee": "backend-eng-1",
        "author": "ceo",
    }
    warnings = warn_interrupted_idempotency([(ticket_path, fm)])
    assert not warnings, "Clean board must produce zero idempotency warnings"
