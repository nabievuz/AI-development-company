"""WS-B core runner tests (ADR-0034 SR-1/3/4/5 · DAS-1555).

Unit coverage for the ``daslab_sdk`` core headless runner — the part-1 surface
built by DAS-1555 (the admission gateway's budget/auth internals are DAS-1556;
the full SC-001…SC-004 negative suite is DAS-1557).  What is proven here:

  flag-off no-op       the runner is inert with ws_b_agent_sdk_runner OFF —
                       no SDK import, no admission, no model call (SR-5 / SC-003a)
  absent SDK           SDK not installed ⇒ a clean "unavailable" result,
                       not a crash (SR-5 / SC-003b)
  run_wave seam        dispatch_wave is a NEW CALLER of scripts/wave_runner.py:
                       run_wave with well-formed (plan, results); the wave-ledger
                       reconciles ⇒ ONE producer, not two (SR-3 / SC-001)
  load-shape (SR-1)    cwd=repo root + setting_sources=["project"]; no ported-
                       agent constructor path exists
  explicit model       absent/empty model rejected before any model call (FR-002)
  admission seam       no admitter wired ⇒ fail-closed refuse; a HOLD ⇒ no
                       dispatch — the runner never self-admits (SR-2/SR-3)
  board/Git law        no self-merge / routing-write path; assembled results
                       carry no merged_pr and never a merge-`done` (SR-4)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import daslab_sdk  # noqa: E402
from daslab_sdk import runner as rn  # noqa: E402
from daslab_sdk.contracts import (  # noqa: E402
    AdmissionDecision,
    AdmissionOutcome,
    RunnerStatus,
)

RUNNER_SRC = (ROOT / "daslab_sdk" / "runner.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _flag_file(tmp_path: Path, *, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_b_agent_sdk_runner: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


class _QuerySpy:
    """Records calls to the injected SDK boundary; a live call is never made."""

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


# --------------------------------------------------------------------------- #
# SR-5 — flag-off no-op / inert
# --------------------------------------------------------------------------- #


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
    assert spy.calls == []  # no model call reached


def test_dispatch_ticket_flag_off_by_default(tmp_path):
    # No flag_path ⇒ reads the repo config, where ws_b_agent_sdk_runner is OFF.
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9001",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=_admit_yes,
        query_fn=spy,
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert spy.calls == []


def test_dispatch_wave_flag_off_never_calls_run_wave(tmp_path):
    ledger = tmp_path / "wave-ledger.jsonl"
    res = rn.dispatch_wave(
        plan=object(),  # never inspected on the inert path
        results=object(),
        created_at="2026-07-24T00:00:00Z",
        ledger_path=ledger,
        flag_path=_flag_file(tmp_path, on=False),
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert res.attestation is None
    assert not ledger.exists()  # run_wave was never reached ⇒ no post-decision write


# --------------------------------------------------------------------------- #
# SR-5 — absent SDK ⇒ clean unavailable, not a crash
# --------------------------------------------------------------------------- #


def test_absent_sdk_is_unavailable_not_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(rn, "sdk_available", lambda: False)
    res = rn.dispatch_ticket(
        ticket_id="DAS-9002",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=_admit_yes,
        query_fn=None,  # force the real SDK path so availability is consulted
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.UNAVAILABLE_NO_SDK
    assert res.is_noop and res.dispatched is False


def test_sdk_available_never_imports(monkeypatch):
    # find_spec-based probe returns a bool and never raises, SDK present or not.
    assert isinstance(rn.sdk_available(), bool)


# --------------------------------------------------------------------------- #
# FR-002 — explicit model required, rejected before the model call
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_model", ["", "   ", None])
def test_missing_model_rejected_before_query(tmp_path, bad_model):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9003",
        role="backend-eng-1",
        model=bad_model,  # type: ignore[arg-type]
        prompt="p",
        admit=_admit_yes,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.REFUSED_NO_MODEL
    assert spy.calls == []  # fail-closed before any model call


def test_build_agent_options_rejects_empty_model():
    with pytest.raises(ValueError, match="explicit"):
        rn.build_agent_options(model="")


# --------------------------------------------------------------------------- #
# SR-2/SR-3 — admission seam: no self-admit; HOLD ⇒ no dispatch
# --------------------------------------------------------------------------- #


def test_no_admitter_wired_is_fail_closed(tmp_path):
    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9004",
        role="backend-eng-1",
        model="claude-x",
        prompt="p",
        admit=None,  # DAS-1556 not wired in ⇒ fail-closed
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
    assert spy.calls == []  # a HOLD never reaches query()


# --------------------------------------------------------------------------- #
# SR-1 — load-shape: cwd + setting_sources=["project"], no ported-agent path
# --------------------------------------------------------------------------- #


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
    assert options["cwd"] == str(rn.REPO_ROOT)          # SR-1: repo root
    assert options["setting_sources"] == ["project"]    # SR-1: repo's own agents
    assert options["model"] == "claude-opus-x"          # explicit, threaded through
    # SR-5 §4.1/§6.2: metered key dropped, no os.environ passthrough.
    assert "ANTHROPIC_API_KEY" not in options["env"]
    assert options["env"] == {"REPO_SCOPED": "1"}


def test_no_ported_agent_constructor_path_exists():
    # SR-1 structural invariant: the runner has no create_agent / ported-role path.
    assert "create_agent" not in RUNNER_SRC
    # and it DOES pin the repo's own project settings.
    assert '["project"]' in RUNNER_SRC
    assert rn.SETTING_SOURCES == ["project"]


def test_isolate_env_is_constructed_not_passthrough():
    assert rn.isolate_env({"ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y", "FOO": "bar"}) == {
        "FOO": "bar"
    }
    assert rn.isolate_env(None) == {}  # floor is empty, never the host environment


# --------------------------------------------------------------------------- #
# SR-4 — board / Git law: no self-merge, no routing writes
# --------------------------------------------------------------------------- #


def test_runner_has_no_self_merge_or_push_path():
    for forbidden in ("gh pr merge", "gh pr create", "--admin", "git push", "git commit"):
        assert forbidden not in RUNNER_SRC, f"runner must not contain {forbidden!r} (SR-4)"


def test_assembled_results_never_self_merge():
    import wave_runner as wr  # scripts/ seam

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
    assert ticket.merged_pr is None          # runner never records a merge
    assert ticket.ci_status == ""
    assert ticket.final_status == "in_review"  # routing target, never merge-`done`
    assert ticket.outcome == "dispatched"


# --------------------------------------------------------------------------- #
# SR-3 — the run_wave seam: new caller, ONE producer (SC-001)
# --------------------------------------------------------------------------- #


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

    # SC-001b — ONE producer: the wave-ledger reconciles against its attestation
    # (no orphan, no chain gap) — proving the runner wrote ONLY through run_wave.
    problems = wr.verify_wave_ledger(kw["ledger_path"], attest_dir=kw["attest_dir"])
    assert problems == []


def test_dispatch_wave_inherits_organism_gate_no_second_toggle(tmp_path):
    # organism_emit=False ⇒ run_wave is a no-op returning None; the runner inherits
    # that gate (no second producer/toggle) and writes zero post-decision artifacts.
    wr, plan, results, kw = _hermetic_wave(tmp_path)
    res = rn.dispatch_wave(
        plan, results, created_at="2026-07-24T00:00:00Z",
        flag_path=_flag_file(tmp_path, on=True), organism_emit=False, **kw,
    )
    assert res.status is RunnerStatus.DISPATCHED
    assert res.attestation is None
    assert not kw["ledger_path"].exists()  # zero post-decision writes
