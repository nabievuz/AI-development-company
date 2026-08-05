
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import wave_runner as wr
import ws_b_admission as gw

from daslab_sdk import runner as rn
from daslab_sdk.contracts import AdmissionDecision as RunnerAdmissionDecision
from daslab_sdk.contracts import AdmissionOutcome as RunnerAdmissionOutcome
from daslab_sdk.contracts import RunnerStatus


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


def _clear_budgets() -> dict:
    return {
        "caps": {
            "per_run": {"max_input_tokens": 2_000_000, "max_output_tokens": 400_000, "max_cost_usd": 5.00},
            "per_day": {"max_input_tokens": 20_000_000, "max_output_tokens": 4_000_000, "max_cost_usd": 15.00},
        },
        "on_breach": "idle_and_alert",
        "monthly_credit_ceiling": {
            "plan_credit_usd": {"pro": 20, "max_5x": 100, "max_20x": 200},
            "on_exhaustion": "sanctioned_pause",
            "metered_overflow": False,
        },
    }


def ws_b_admission_adapter(
    *,
    estimate: gw.UsageEstimate | None = None,
    credit_state: gw.CreditState | None = None,
    budgets: dict | None = None,
    admit_fn=gw.admit,
    call_log: list | None = None,
):

    def _admitter(*, ticket_id: str, role: str, model: str) -> RunnerAdmissionDecision:
        if call_log is not None:
            call_log.append((ticket_id, role, model))
        decision = admit_fn(
            ticket_id=ticket_id,
            role=role,
            model=model,
            estimate=estimate,
            credit_state=credit_state,
            budgets=budgets,
        )
        outcome = (
            RunnerAdmissionOutcome.ADMIT
            if decision.outcome is gw.AdmissionOutcome.ADMIT
            else RunnerAdmissionOutcome.HOLD
        )
        return RunnerAdmissionDecision(
            outcome=outcome,
            ticket_id=decision.ticket_id,
            model=decision.model or model,
            reason=decision.reason,
        )

    return _admitter


def _naive_passthrough_admitter(*, ticket_id: str, role: str, model: str):
    return gw.admit(
        ticket_id=ticket_id, role=role, model=model, budgets=_clear_budgets()
    )


def test_naive_direct_injection_scores_every_real_admit_as_hold(tmp_path):
    real_decision = gw.admit(
        ticket_id="DAS-9100", role="backend-eng-1", model="claude-sonnet-4-6",
        budgets=_clear_budgets(),
    )
    assert real_decision.outcome is gw.AdmissionOutcome.ADMIT

    spy = _QuerySpy()
    res = rn.dispatch_ticket(
        ticket_id="DAS-9100",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        prompt="do the thing",
        admit=_naive_passthrough_admitter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )

    assert res.status is RunnerStatus.ADMISSION_HOLD
    assert spy.calls == []


def test_adapter_fixes_the_enum_identity_trap(tmp_path):
    spy = _QuerySpy(output="done")
    adapter = ws_b_admission_adapter(budgets=_clear_budgets())
    res = rn.dispatch_ticket(
        ticket_id="DAS-9100",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        prompt="do the thing",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.DISPATCHED
    assert res.dispatched is True
    assert len(spy.calls) == 1


def test_real_admit_flows_adapter_dispatch_ticket_query_fn(tmp_path):
    spy = _QuerySpy(output="ran")
    adapter = ws_b_admission_adapter(budgets=_clear_budgets())
    res = rn.dispatch_ticket(
        ticket_id="DAS-9101",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        prompt="envelope",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.DISPATCHED
    assert res.dispatched is True
    assert res.output == "ran"
    assert len(spy.calls) == 1


@pytest.mark.parametrize(
    "case,estimate,credit_state",
    [
        ("budget_breach", gw.UsageEstimate(run_cost_usd=6.00), gw.CreditState()),
        ("credit_exhaustion", gw.UsageEstimate(), gw.CreditState(plan="pro", used_usd=20.0)),
    ],
)
def test_real_non_admit_outcomes_hold_and_never_reach_query_fn(
    tmp_path, case, estimate, credit_state
):
    spy = _QuerySpy()
    adapter = ws_b_admission_adapter(
        estimate=estimate, credit_state=credit_state, budgets=_clear_budgets()
    )
    res = rn.dispatch_ticket(
        ticket_id="DAS-9102",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        prompt="envelope",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.ADMISSION_HOLD, case
    assert res.dispatched is False
    assert spy.calls == []
    assert res.status is not RunnerStatus.DISPATCHED


def test_missing_model_rejected_before_adapter_is_ever_called(tmp_path):
    spy = _QuerySpy()
    call_log: list = []
    adapter = ws_b_admission_adapter(budgets=_clear_budgets(), call_log=call_log)
    res = rn.dispatch_ticket(
        ticket_id="DAS-9103",
        role="backend-eng-1",
        model="",
        prompt="envelope",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.REFUSED_NO_MODEL
    assert spy.calls == []
    assert call_log == []


def test_flag_off_adapter_never_reached(tmp_path):
    spy = _QuerySpy()
    call_log: list = []
    adapter = ws_b_admission_adapter(budgets=_clear_budgets(), call_log=call_log)
    res = rn.dispatch_ticket(
        ticket_id="DAS-9104",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        prompt="envelope",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=False),
    )
    assert res.status is RunnerStatus.INERT_FLAG_OFF
    assert spy.calls == []
    assert call_log == []


def _fixed_wave():
    plan = wr.WavePlan(
        run_id="RUNEQUIV01",
        wave=1,
        goal="mustaqil-ws-b-runner",
        engine_version="2.0.0",
        tickets=[
            wr.TicketPlan(
                ticket_id="DAS-9110", role="backend-eng-1", model="claude-sonnet-4-6",
                from_status="todo", to_status="in_review",
            )
        ],
    )
    results = wr.WaveResults(
        tickets=[
            wr.TicketResult(
                ticket_id="DAS-9110", outcome="in_review", merged_pr=None, ci_status="PENDING",
                t7_pass=False, t7_score=0.0, start="2026-07-24T00:00:00Z",
                end="2026-07-24T00:00:01Z", final_status="in_review", output="",
            )
        ],
    )
    return plan, results


def _hermetic_kwargs(base: Path) -> dict:
    (base / "tickets").mkdir(parents=True, exist_ok=True)
    return {
        "store_path": base / "events.jsonl",
        "runs_dir": base / "runs",
        "attest_dir": base / "attestations",
        "ledger_path": base / "wave-ledger.jsonl",
        "evidence_dir": base / "evidence",
        "tickets_dir": base / "tickets",
        "board_dir": base / "tickets",
        "run_guardrails": False,
    }


def test_sc001_dispatch_equivalence_flag_on_vs_interactive_equivalent(tmp_path):
    plan, results = _fixed_wave()
    created_at = "2026-07-24T00:00:00Z"

    interactive_dir = tmp_path / "interactive"
    headless_dir = tmp_path / "headless"
    interactive_kw = _hermetic_kwargs(interactive_dir)
    headless_kw = _hermetic_kwargs(headless_dir)

    interactive_att = wr.run_wave(plan, wr.replay_executor(results.tickets), created_at=created_at, **interactive_kw)

    headless_res = rn.dispatch_wave(
        plan, wr.replay_executor(results.tickets), created_at=created_at,
        flag_path=_flag_file(tmp_path, on=True), **headless_kw,
    )

    assert headless_res.status is RunnerStatus.DISPATCHED
    headless_att = headless_res.attestation
    assert interactive_att is not None and headless_att is not None


    assert interactive_att.payload == headless_att.payload
    assert interactive_att.payload["event_digest"] == headless_att.payload["event_digest"]
    assert interactive_att.payload["ledger_digest"] == headless_att.payload["ledger_digest"]
    assert interactive_att.payload["counts"] == headless_att.payload["counts"]
    assert interactive_att.self_hash == headless_att.self_hash


    assert wr.verify_wave_ledger(interactive_kw["ledger_path"], attest_dir=interactive_kw["attest_dir"]) == []
    assert wr.verify_wave_ledger(headless_kw["ledger_path"], attest_dir=headless_kw["attest_dir"]) == []


def test_sc001_flag_off_produces_zero_headless_writes_interactive_unaffected(tmp_path):
    plan, results = _fixed_wave()
    created_at = "2026-07-24T00:00:00Z"

    interactive_dir = tmp_path / "interactive"
    headless_dir = tmp_path / "headless"
    interactive_kw = _hermetic_kwargs(interactive_dir)
    headless_kw = _hermetic_kwargs(headless_dir)

    interactive_att = wr.run_wave(plan, wr.replay_executor(results.tickets), created_at=created_at, **interactive_kw)
    assert interactive_att is not None

    headless_res = rn.dispatch_wave(
        plan, wr.replay_executor(results.tickets), created_at=created_at,
        flag_path=_flag_file(tmp_path, on=False), **headless_kw,
    )
    assert headless_res.status is RunnerStatus.INERT_FLAG_OFF
    assert headless_res.attestation is None
    assert not headless_kw["ledger_path"].exists()
    assert not headless_kw["attest_dir"].exists() or list(Path(headless_kw["attest_dir"]).iterdir()) == []
