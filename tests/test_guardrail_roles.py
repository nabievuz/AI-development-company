from __future__ import annotations

import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "governance"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from guardrails import (
    GuardrailContext,
    default_input_guardrail,
    default_output_guardrail,
    ok_result,
    runner,
    trip,
)

GUARDRAILS_DIR = _REPO_ROOT / "governance" / "guardrails"


def test_ok_and_trip_helpers():
    assert ok_result() == (True, "")
    ok, fb = trip("something wrong")
    assert ok is False and fb == "something wrong"


def test_trip_requires_feedback():
    import pytest

    with pytest.raises(ValueError):
        trip("   ")


def _eng_ctx(**kw) -> GuardrailContext:
    base = {
        "role": "backend-eng-1",
        "role_dept": "engineering",
        "ticket_id": "DAS-9001",
        "ticket_dept": "engineering",
    }
    base.update(kw)
    return GuardrailContext(**base)


def test_input_wrong_department_trips():
    ctx = _eng_ctx(ticket_dept="marketing")
    ok, fb = default_input_guardrail(ctx)
    assert ok is False
    assert "wrong-department" in fb


def test_input_missing_consumes_field_trips():
    ctx = _eng_ctx(consumes=["design_spec"], frontmatter={})
    ok, fb = default_input_guardrail(ctx)
    assert ok is False
    assert "missing consumes" in fb and "design_spec" in fb


def test_input_missing_consumes_dep_trips():
    ctx = _eng_ctx(consumes=["DAS-1000"], deps_status={"DAS-1000": "in_progress"})
    ok, fb = default_input_guardrail(ctx)
    assert ok is False
    assert "DAS-1000" in fb


def test_input_consumes_satisfied_passes():
    ctx = _eng_ctx(
        consumes=["DAS-1000", "design_spec"],
        deps_status={"DAS-1000": "done"},
        frontmatter={"design_spec": "docs/spec.md"},
    )
    assert default_input_guardrail(ctx) == (True, "")


def test_input_gate_open_unfinished_dep_trips():
    ctx = _eng_ctx(depends_on=["DAS-1000"], deps_status={"DAS-1000": "in_progress"})
    ok, fb = default_input_guardrail(ctx)
    assert ok is False and "gate-open" in fb


def test_input_gate_open_aadl_flag_trips():
    ctx = _eng_ctx(gate_open=True)
    ok, fb = default_input_guardrail(ctx)
    assert ok is False and "gate-open" in fb


def test_input_clean_passes():
    ctx = _eng_ctx(depends_on=["DAS-1000"], deps_status={"DAS-1000": "done"})
    assert default_input_guardrail(ctx) == (True, "")


def test_output_empty_trips():
    ok, fb = default_output_guardrail(_eng_ctx(output="   "))
    assert ok is False and "empty output" in fb


def test_output_unresolved_marker_trips():
    ok, fb = default_output_guardrail(_eng_ctx(output="did the thing, TODO wire it"))
    assert ok is False and "unresolved" in fb.lower()


def test_output_clean_passes():
    assert default_output_guardrail(_eng_ctx(output="all done and shipped")) == (True, "")


def _sec_ctx(**kw) -> GuardrailContext:
    base = {
        "role": "security-lead",
        "role_dept": "engineering",
        "ticket_id": "DAS-9002",
        "ticket_dept": "engineering",
        "frontmatter": {"title": "Security review of auth flow"},
        "body": "Review the auth token handling for vulnerabilities.",
    }
    base.update(kw)
    return GuardrailContext(**base)


def test_security_lead_input_offscope_trips():
    ctx = _sec_ctx(frontmatter={"title": "Refactor CSS grid"}, body="tidy the layout")
    ok, fb = runner.run_input("security-lead", ctx, GUARDRAILS_DIR)
    assert ok is False and "off-scope" in fb


def test_security_lead_input_onscope_passes():
    ok, _ = runner.run_input("security-lead", _sec_ctx(), GUARDRAILS_DIR)
    assert ok is True


def test_security_lead_output_no_signoff_trips():
    ctx = _sec_ctx(output="I looked at the code and it seems fine.")
    ok, fb = runner.run_output("security-lead", ctx, GUARDRAILS_DIR)
    assert ok is False and "sign-off" in fb


def test_security_lead_output_leaked_secret_trips():


    ctx = _sec_ctx(output="Signed-off. Note api_key=notarealkey1234 in config.")
    ok, fb = runner.run_output("security-lead", ctx, GUARDRAILS_DIR)
    assert ok is False and "secret" in fb.lower()


def test_security_lead_output_signoff_passes():
    ctx = _sec_ctx(output="Reviewed OWASP top-10; no findings. Security sign-off granted.")
    assert runner.run_output("security-lead", ctx, GUARDRAILS_DIR)[0] is True


def _be_ctx(**kw) -> GuardrailContext:
    base = {
        "role": "backend-eng-1",
        "role_dept": "engineering",
        "ticket_id": "DAS-9003",
        "ticket_dept": "engineering",
    }
    base.update(kw)
    return GuardrailContext(**base)


def test_backend_output_no_tests_trips():
    ok, fb = runner.run_output(
        "backend-eng-1", _be_ctx(output="Implemented the endpoint."), GUARDRAILS_DIR
    )
    assert ok is False and "test evidence" in fb


def test_backend_output_red_build_trips():
    ok, fb = runner.run_output(
        "backend-eng-1",
        _be_ctx(output="Added tests but the suite failed with a traceback."),
        GUARDRAILS_DIR,
    )
    assert ok is False and "red build" in fb


def test_backend_output_green_passes():
    ok, _ = runner.run_output(
        "backend-eng-1",
        _be_ctx(output="Implemented endpoint; added pytest cases, all 12 passed (green)."),
        GUARDRAILS_DIR,
    )
    assert ok is True


def test_load_hyphenated_module_by_path():
    mod = runner.load_guardrail_module("security-lead", GUARDRAILS_DIR)
    assert mod is not None and mod.ROLE == "security-lead"


def test_unknown_role_falls_back_to_default():


    ctx = _eng_ctx(role="nonexistent-role", output="TODO finish")
    assert runner.load_guardrail_module("nonexistent-role", GUARDRAILS_DIR) is None
    ok, fb = runner.run_output("nonexistent-role", ctx, GUARDRAILS_DIR)
    assert ok is False and "unresolved" in fb.lower()


_ROUTING_FIXTURE = textwrap.dedent(
    """\
    # Role routing

    | Role key | Display name | Dept | Reports to (reviewer) |
    |---|---|---|---|
    | `security-lead` | Security Lead | engineering | CTO |
    | `cto` | CTO | engineering | CEO |
    | `backend-eng-1` | Backend Engineer 1 | engineering | Backend EM |
    """
)


def _write(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_build_context_reads_ticket_and_deps(tmp_path):
    routing = _write(tmp_path / "ROUTING.md", _ROUTING_FIXTURE)
    board = tmp_path / "tickets"
    board.mkdir()
    _write(
        board / "DAS-1000-dep.md",
        """\
        ---
        id: DAS-1000
        status: done
        ---
        dep body
        """,
    )
    ticket = _write(
        board / "DAS-2000-work.md",
        """\
        ---
        id: DAS-2000
        title: Guard the thing
        status: todo
        assignee: security-lead
        author: ceo
        dept: engineering
        depends_on: [DAS-1000]
        consumes: [DAS-1000]
        ---
        body text
        """,
    )
    ctx = runner.build_context(ticket, routing_path=routing, board_dir=board)
    assert ctx.role == "security-lead"
    assert ctx.role_dept == "engineering"
    assert ctx.ticket_dept == "engineering"
    assert ctx.depends_on == ["DAS-1000"]
    assert ctx.deps_status == {"DAS-1000": "done"}
    assert ctx.frontmatter["author"] == "ceo"
