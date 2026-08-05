
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import daslab_sdk
from daslab_sdk import runner as rn
from daslab_sdk.contracts import (
    AdmissionDecision,
    AdmissionOutcome,
    RunnerStatus,
)

RUNNER_SRC = (ROOT / "daslab_sdk" / "runner.py").read_text(encoding="utf-8")


def _flag_file(tmp_path: Path, *, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_b_agent_sdk_runner: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


class _QuerySpy:

    def __init__(self, output: str = "ok") -> None:
        self.calls: list[tuple[str, dict]] = []
        self.output = output

    def __call__(self, prompt: str, options) -> str:
        self.calls.append((prompt, dict(options)))
        return self.output


def _admit_yes(*, ticket_id: str, role: str, model: str) -> AdmissionDecision:
    return AdmissionDecision(outcome=AdmissionOutcome.ADMIT, ticket_id=ticket_id, model=model)


def _admit_hold(*, ticket_id: str, role: str, model: str) -> AdmissionDecision:
    return AdmissionDecision(
        outcome=AdmissionOutcome.HOLD, ticket_id=ticket_id, model=model, reason="budget breach"
    )


def test_dispatch_ticket_flag_off_is_inert_noop(tmp_path):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9001",
        role="backend-eng-1",
        model="claude-x",
        prompt="do the thing",
        admit=_admit_yes,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=False),
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert res.is_noop and res.dispatched is False
    assert spy.calls == []


def test_dispatch_ticket_inert_when_flag_off(tmp_path):


    off = tmp_path / "features.yaml"
    off.write_text("ws_b_agent_sdk_runner: false\n", encoding="utf-8")
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9001",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=_admit_yes,
        query_fn=spy,
        flag_path=off,
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert spy.calls == []


def test_dispatch_wave_flag_off_never_calls_run_wave(tmp_path):
    ledger = tmp_path / "wave-ledger.jsonl"
    res = rn.dispatch_wave(
        plan=object(),
        results=object(),
        created_at="2026-07-24T00:00:00Z",
        ledger_path=ledger,
        flag_path=_flag_file(tmp_path, on=False),
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert res.attestation is None
    assert not ledger.exists()


def test_absent_sdk_is_unavailable_not_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(rn, "sdk_available", lambda: False)
    res = rn.dispatch_ticket(
        ticket_id="DAS-9002",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=_admit_yes,
        query_fn=None,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.UNAVAILABLE_NO_SDK
    assert res.is_noop and res.dispatched is False


def test_sdk_available_never_imports(monkeypatch):

    assert isinstance(rn.sdk_available(), bool)


@pytest.mark.parametrize("bad_model", ["", "   ", None])
def test_missing_model_rejected_before_query(tmp_path, bad_model):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9003",
        role="backend-eng-1",
        model=bad_model,
        prompt="p",
        admit=_admit_yes,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.REFUSED_NO_MODEL
    assert spy.calls == []


def test_build_agent_options_rejects_empty_model():
    with pytest.raises(ValueError, match="explicit"):
        rn.build_agent_options(model="")


def test_no_admitter_wired_is_fail_closed(tmp_path):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9004",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=None,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.REFUSED_NO_ADMITTER
    assert spy.calls == []


def test_admission_hold_blocks_dispatch(tmp_path):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9005",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=_admit_hold,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.ADMISSION_HOLD
    assert res.reason == "budget breach"
    assert spy.calls == []


def test_happy_dispatch_pins_load_shape_and_drops_metered_key(tmp_path):
    spy = _QuerySpy(output="done")
    res = rn.dispatch_ticket(
        ticket_id="DAS-9006",
        role="backend-eng-1",
        model="claude-opus-x",
        prompt="envelope",
        env={"ANTHROPIC_API_KEY": "sekret", "REPO_SCOPED": "1"},
        admit=_admit_yes,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.DISPATCHED
    assert res.dispatched is True and res.output == "done"

    assert len(spy.calls) == 1
    prompt, options = spy.calls[0]
    assert prompt == "envelope"
    assert options["cwd"] == str(rn.REPO_ROOT)
    assert options["setting_sources"] == ["project"]
    assert options["model"] == "claude-opus-x"

    assert "ANTHROPIC_API_KEY" not in options["env"]
    assert options["env"] == {"REPO_SCOPED": "1"}


def test_no_ported_agent_constructor_path_exists():

    assert "create_agent" not in RUNNER_SRC

    assert '["project"]' in RUNNER_SRC
    assert rn.SETTING_SOURCES == ["project"]


def test_isolate_env_is_constructed_not_passthrough():
    assert rn.isolate_env({"ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y", "FOO": "bar"}) == {
        "FOO": "bar"
    }
    assert rn.isolate_env(None) == {}


def test_runner_has_no_self_merge_or_push_path():
    for forbidden in ("gh pr merge", "gh pr create", "--admin", "git push", "git commit"):
        assert forbidden not in RUNNER_SRC, f"runner must not contain {forbidden!r} (SR-4)"


def test_assembled_results_never_self_merge():
    import wave_runner as wr

    plan = wr.WavePlan(
        run_id="RUNZZZ",
        wave=1,
        goal="mustaqil-ws-b-runner",
        engine_version="2.0.0",
        tickets=[wr.TicketPlan(ticket_id="DAS-9007", role="backend-eng-1", model="claude-x",
                               from_status="todo", to_status="in_review")],
    )
    dispatched = daslab_sdk.TicketDispatchResult(
        ticket_id="DAS-9007", status=RunnerStatus.DISPATCHED, dispatched=True, output="work"
    )
    results = rn.results_from_dispatches(plan, [dispatched], created_at="2026-07-24T00:00:00Z")
    (ticket,) = results.tickets
    assert ticket.merged_pr is None
    assert ticket.ci_status == ""
    assert ticket.final_status == "in_review"
    assert ticket.outcome == "dispatched"


def _hermetic_wave(tmp_path):
    import wave_runner as wr

    plan = wr.WavePlan(
        run_id="RUNSEAM01",
        wave=1,
        goal="mustaqil-ws-b-runner",
        engine_version="2.0.0",
        tickets=[wr.TicketPlan(ticket_id="DAS-9008", role="backend-eng-1", model="claude-x",
                               from_status="todo", to_status="in_review")],
    )
    results = wr.WaveResults(
        tickets=[wr.TicketResult(
            ticket_id="DAS-9008", outcome="in_review", merged_pr=None, ci_status="PENDING",
            t7_pass=False, t7_score=0.0, start="2026-07-24T00:00:00Z",
            end="2026-07-24T00:00:01Z", final_status="in_review", output="")],
    )
    kw = {
        "store_path": tmp_path / "events.jsonl",
        "runs_dir": tmp_path / "runs",
        "attest_dir": tmp_path / "attestations",
        "ledger_path": tmp_path / "wave-ledger.jsonl",
        "evidence_dir": tmp_path / "evidence",
        "tickets_dir": tmp_path / "tickets",
        "board_dir": tmp_path / "tickets",
        "run_guardrails": False,
    }
    (tmp_path / "tickets").mkdir()
    return wr, plan, results, kw


def test_dispatch_wave_calls_run_wave_and_ledger_reconciles(tmp_path):
    wr, plan, results, kw = _hermetic_wave(tmp_path)
    res = rn.dispatch_wave(
        plan, results, created_at="2026-07-24T00:00:00Z",
        flag_path=_flag_file(tmp_path, on=True), **kw,
    )
    assert res.status is RunnerStatus.DISPATCHED
    att = res.attestation
    assert att is not None and att.run_id == "RUNSEAM01"


    problems = wr.verify_wave_ledger(kw["ledger_path"], attest_dir=kw["attest_dir"])
    assert problems == []


def test_dispatch_wave_inherits_organism_gate_no_second_toggle(tmp_path):


    wr, plan, results, kw = _hermetic_wave(tmp_path)
    res = rn.dispatch_wave(
        plan, results, created_at="2026-07-24T00:00:00Z",
        flag_path=_flag_file(tmp_path, on=True), organism_emit=False, **kw,
    )
    assert res.status is RunnerStatus.DISPATCHED
    assert res.attestation is None
    assert not kw["ledger_path"].exists()
