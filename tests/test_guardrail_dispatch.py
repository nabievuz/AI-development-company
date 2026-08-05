from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "governance"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import guardrail_dispatch as gd

GUARDRAILS_DIR = _REPO_ROOT / "governance" / "guardrails"

_ROUTING = textwrap.dedent(
    """\
    # Role routing

    | Role key | Display name | Dept | Reports to (reviewer) |
    |---|---|---|---|
    | `security-lead` | Security Lead | engineering | CTO |
    | `cto` | CTO | engineering | CEO |
    | `ceo` | CEO | governance | Chairman of the Board |
    | `chairman` | Chairman of the Board | governance | — |
    | `backend-eng-1` | Backend Engineer 1 | engineering | Backend EM |
    | `backend-em` | Backend EM | engineering | CTO |
    """
)


def _fixed_now():
    return "2026-07-03"


def _make_env(tmp_path, *, dept="engineering", assignee="security-lead",
              author="ceo", title="Security review of auth", body="check auth vulns"):
    routing = tmp_path / "ROUTING.md"
    routing.write_text(_ROUTING, encoding="utf-8")
    board = tmp_path / "tickets"
    board.mkdir()
    ticket = board / "DAS-3000-work.md"
    ticket.write_text(
        textwrap.dedent(
            f"""\
            ---
            id: DAS-3000
            title: {title}
            status: in_progress
            assignee: {assignee}
            author: {author}
            dept: {dept}
            ---

            {body}

            ## Log
            ### 2026-07-03 — CEO
            Created.
            """
        ),
        encoding="utf-8",
    )
    return routing, board, ticket


def test_escalation_target_simple():
    from guardrails import runner

    routing = _REPO_ROOT / "board" / "ROUTING.md"
    role_table = runner.load_role_table(routing)

    assert gd.escalation_target("security-lead", "ceo", role_table) == "cto"


def test_escalation_target_manager_is_author_climbs(tmp_path):
    from guardrails import runner

    routing = tmp_path / "ROUTING.md"
    routing.write_text(_ROUTING, encoding="utf-8")
    role_table = runner.load_role_table(routing)

    assert gd.escalation_target("backend-eng-1", "backend-em", role_table) == "cto"


def test_input_reject_wrong_department_never_runs_agent(tmp_path):
    routing, board, ticket = _make_env(tmp_path, dept="marketing")
    calls = []

    def agent(ctx, attempt):
        calls.append(attempt)
        return "whatever"

    res = gd.guardrail_dispatch(
        ticket, agent, routing_path=routing, board_dir=board,
        guardrails_dir=GUARDRAILS_DIR, now=_fixed_now,
    )
    assert res.outcome == "input_rejected"
    assert res.accepted is False
    assert calls == []
    assert "wrong-department" in res.feedback


def test_self_corrects_within_two_retries(tmp_path):
    routing, board, ticket = _make_env(tmp_path)


    outputs = [
        "Looked at it, seems fine.",
        "Still reviewing, no decision yet.",
        "OWASP review complete; security sign-off granted.",
    ]

    def agent(ctx, attempt):
        return outputs[attempt]

    res = gd.guardrail_dispatch(
        ticket, agent, routing_path=routing, board_dir=board,
        guardrails_dir=GUARDRAILS_DIR, now=_fixed_now,
    )
    assert res.outcome == "passed"
    assert res.attempts == 3
    assert res.retries_used == 2

    text = ticket.read_text(encoding="utf-8")

    assert text.count(f"origin: {gd.OUTPUT_GUARDRAIL_ORIGIN}") == 2
    assert "Retry 1/2" in text and "Retry 2/2" in text
    assert "Re-dispatching security-lead" in text


def test_escalates_after_two_retries(tmp_path):
    routing, board, ticket = _make_env(tmp_path)

    def agent(ctx, attempt):
        return "Reviewed briefly, looks okay."

    res = gd.guardrail_dispatch(
        ticket, agent, routing_path=routing, board_dir=board,
        guardrails_dir=GUARDRAILS_DIR, now=_fixed_now,
    )
    assert res.outcome == "escalated"
    assert res.retries_used == 2
    assert res.attempts == 3
    assert res.escalated_to == "cto"

    text = ticket.read_text(encoding="utf-8")

    assert text.count(f"origin: {gd.OUTPUT_GUARDRAIL_ORIGIN}") == 4
    assert "Guardrail escalation (security-lead → cto)" in text

    assert "assignee: cto" in text
    assert "status: in_review" in text


def test_escalation_does_not_self_review(tmp_path):


    routing, board, ticket = _make_env(tmp_path)

    def agent(ctx, attempt):
        return "no decision"

    gd.guardrail_dispatch(
        ticket, agent, routing_path=routing, board_dir=board,
        guardrails_dir=GUARDRAILS_DIR, now=_fixed_now,
    )
    text = ticket.read_text(encoding="utf-8")
    assert "assignee: cto" in text
    assert "author: ceo" in text
