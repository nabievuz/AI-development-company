from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "governance"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import guardrail_dispatch as gd
from guardrails import runner

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


def test_escalation_target_simple(tmp_path):
    from guardrails import runner

    routing = tmp_path / "ROUTING.md"
    routing.write_text(_ROUTING, encoding="utf-8")
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


def _log_entry_count(text, marker):
    return text.count(marker)


def test_concurrent_feedback_writes_lose_nothing(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    _routing, _board, ticket = _make_env(tmp_path)
    writers = 8

    def write(index):
        gd.write_output_guardrail_feedback(
            ticket,
            f"feedback-{index}",
            role="security-lead",
            attempt=0,
            max_retries=2,
            now=_fixed_now,
        )

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(write, range(writers)))

    text = ticket.read_text(encoding="utf-8")
    for index in range(writers):
        assert f"feedback-{index}" in text
    assert _log_entry_count(text, f"origin: {gd.OUTPUT_GUARDRAIL_ORIGIN}") == writers


def test_concurrent_escalations_lose_no_update(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    _routing, _board, ticket = _make_env(tmp_path)
    writers = 8

    def escalate(index):
        gd.escalate_in_ticket(
            ticket,
            "cto",
            "security-lead",
            f"escalation-{index}",
            max_retries=2,
            now=_fixed_now,
        )

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(escalate, range(writers)))

    text = ticket.read_text(encoding="utf-8")
    for index in range(writers):
        assert f"escalation-{index}" in text, f"lost update: escalation-{index}"
    assert text.count("Guardrail escalation (security-lead → cto)") == writers
    assert "assignee: cto" in text
    assert "status: in_review" in text


def test_escalation_survives_a_concurrent_unrelated_ticket_write(tmp_path):
    import threading

    import filelock

    _routing, _board, ticket = _make_env(tmp_path)
    started = threading.Event()
    release = threading.Event()

    def slow_appender(text):
        started.set()
        release.wait(timeout=5)
        return text + "\n### concurrent writer note\n"

    other = threading.Thread(
        target=filelock.locked_update_text, args=(ticket, slow_appender)
    )
    other.start()
    assert started.wait(timeout=5)

    escalation = threading.Thread(
        target=gd.escalate_in_ticket,
        args=(ticket, "cto", "security-lead", "escalation-under-contention"),
        kwargs={"max_retries": 2, "now": _fixed_now},
    )
    escalation.start()
    release.set()
    other.join(timeout=5)
    escalation.join(timeout=5)

    text = ticket.read_text(encoding="utf-8")
    assert "concurrent writer note" in text
    assert "escalation-under-contention" in text


def test_role_table_falls_back_to_the_org_model_when_no_routing_markdown_exists():
    import org_model

    table = runner.load_role_table()
    assert set(table) == set(org_model.known_role_keys())
    assert table["backend-eng-1"]["dept"] == "engineering"
    assert table["backend-eng-1"]["display"] == org_model.role("backend-eng-1").title


def test_role_table_still_reads_an_explicitly_supplied_legacy_routing_markdown(tmp_path):
    legacy = tmp_path / "ROUTING.md"
    legacy.write_text(
        "| role | name | dept | reviewer |\n"
        "| --- | --- | --- | --- |\n"
        "| `only-role` | Only Role | engineering | Nobody |\n",
        encoding="utf-8",
    )
    assert runner.load_role_table(legacy) == {
        "only-role": {"display": "Only Role", "dept": "engineering", "reports_to": "Nobody"}
    }


def test_dispatch_default_routing_no_longer_points_at_the_deleted_routing_markdown():
    assert gd.DEFAULT_ROUTING is None
    assert not gd.LEGACY_ROUTING_MD.exists()


def _ticket(tmp_path: Path, status: str) -> Path:
    path = tmp_path / "DAS-1-x.md"
    path.write_text(
        f"---\nid: DAS-1\nstatus: {status}\nassignee: sre-eng\nupdated: 2026-08-01\n---\n\nbody\n",
        encoding="utf-8",
    )
    return path


def _escalate(path: Path) -> str:
    gd.escalate_in_ticket(
        path, "sre-lead", "sre-eng", "no runbook", max_retries=2, now=lambda: "2026-08-17"
    )
    return path.read_text(encoding="utf-8")


class TestEscalationDoesNotOverwriteAHalt:
    def test_a_blocked_ticket_stays_blocked(self, tmp_path):
        text = _escalate(_ticket(tmp_path, "blocked"))
        assert gd._frontmatter_field(text, "status") == "blocked"

    def test_the_reviewer_is_still_assigned_when_the_halt_is_kept(self, tmp_path):
        text = _escalate(_ticket(tmp_path, "blocked"))
        assert gd._frontmatter_field(text, "assignee") == "sre-lead"
        assert "Guardrail escalation" in text

    def test_a_working_ticket_still_goes_to_review(self, tmp_path):
        for status in ("todo", "in_progress"):
            text = _escalate(_ticket(tmp_path, status))
            assert gd._frontmatter_field(text, "status") == "in_review", status

    def test_a_halt_does_not_suppress_the_updated_stamp(self, tmp_path):
        text = _escalate(_ticket(tmp_path, "blocked"))
        assert gd._frontmatter_field(text, "updated") == "2026-08-17"


def _halting_board(tmp_path: Path, halt: bool):
    board = tmp_path / "tickets"
    board.mkdir()
    path = board / "DAS-1-x.md"
    path.write_text(
        "---\nid: DAS-1\nstatus: in_progress\nassignee: sre-eng\nauthor: cto\n"
        "dept: engineering\n---\n\nbody\n",
        encoding="utf-8",
    )
    calls: list[int] = []

    def run_agent(ctx, attempt):
        calls.append(attempt)
        if halt:
            text = path.read_text(encoding="utf-8").replace(
                "status: in_progress", "status: blocked"
            )
            path.write_text(text, encoding="utf-8")
        return "produced nothing the rubric accepts"

    result = gd.guardrail_dispatch(
        path, run_agent, routing_path=None, board_dir=board,
        max_retries=2, now=lambda: "2026-08-17",
    )
    return calls, result, path


class TestARoleThatHaltsIsNotRetried:
    def test_a_halt_costs_one_agent_call_not_three(self, tmp_path):
        calls, result, _ = _halting_board(tmp_path, halt=True)
        assert len(calls) == 1
        assert result.attempts == 1
        assert result.retries_used == 0
        assert result.outcome == "escalated"

    def test_a_genuinely_bad_output_still_gets_its_retries(self, tmp_path):
        calls, result, _ = _halting_board(tmp_path, halt=False)
        assert len(calls) == 3
        assert result.retries_used == 2
        assert result.outcome == "escalated"

    def test_the_log_says_why_it_did_not_retry(self, tmp_path):
        _calls, _result, path = _halting_board(tmp_path, halt=True)
        text = path.read_text(encoding="utf-8")
        assert "NOT re-dispatching" in text
        assert "consequence of the halt" in text
        assert "Re-dispatching sre-eng with this feedback" not in text

    def test_the_halt_survives_the_escalation_that_follows(self, tmp_path):
        _calls, _result, path = _halting_board(tmp_path, halt=True)
        assert gd._frontmatter_field(path.read_text(encoding="utf-8"), "status") == "blocked"
