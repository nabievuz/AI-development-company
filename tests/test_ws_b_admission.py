
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ws_b_admission as gw


def test_missing_model_rejected_before_model_call():
    calls = {"n": 0}

    def fake_model_call():
        calls["n"] += 1
        return "should-never-run"

    decision, result = gw.dispatch_through_gate(
        ticket_id="DAS-9999", role="backend-eng-1", model=None, call=fake_model_call
    )

    assert decision.outcome is gw.AdmissionOutcome.REJECTED
    assert not decision.admitted
    assert result is None
    assert calls["n"] == 0, "the model call must not be reached on a missing model"


def test_empty_string_model_rejected():
    decision = gw.admit(ticket_id="DAS-9999", role="backend-eng-1", model="")
    assert decision.outcome is gw.AdmissionOutcome.REJECTED

    decision_ws = gw.admit(ticket_id="DAS-9999", role="backend-eng-1", model="   ")
    assert decision_ws.outcome is gw.AdmissionOutcome.REJECTED


def test_non_string_model_rejected():
    decision = gw.admit(ticket_id="DAS-9999", role="backend-eng-1", model=None)
    assert decision.outcome is gw.AdmissionOutcome.REJECTED
    assert "LAW 3" in decision.reason or "fail-closed" in decision.reason


def test_frontmatter_model_hint_is_never_a_fallback():
    ticket_frontmatter_hint = "sonnet"
    decision = gw.admit(ticket_id="DAS-9999", role="backend-eng-1", model=None)
    assert decision.outcome is gw.AdmissionOutcome.REJECTED


    assert ticket_frontmatter_hint not in decision.reason


def test_valid_explicit_model_is_admitted_when_budget_and_credit_clear():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=0.01),
        credit_state=gw.CreditState(plan="max_20x", used_usd=0.0),
        budgets={
            "caps": {"per_run": {"max_cost_usd": 5.0}, "per_day": {"max_cost_usd": 15.0}},
            "monthly_credit_ceiling": {"plan_credit_usd": {"max_20x": 200}},
        },
    )
    assert decision.outcome is gw.AdmissionOutcome.ADMIT
    assert decision.admitted


def _mustaqil(**overrides):
    base = {
        "caps": {
            "per_run": {
                "max_input_tokens": 2_000_000,
                "max_output_tokens": 400_000,
                "max_cost_usd": 5.00,
            },
            "per_day": {
                "max_input_tokens": 20_000_000,
                "max_output_tokens": 4_000_000,
                "max_cost_usd": 15.00,
            },
        },
        "on_breach": "idle_and_alert",
        "monthly_credit_ceiling": {
            "plan_credit_usd": {"pro": 20, "max_5x": 100, "max_20x": 200},
            "on_exhaustion": "sanctioned_pause",
            "metered_overflow": False,
        },
    }
    base.update(overrides)
    return base


def test_per_run_cost_breach_is_idle_and_alert():
    calls = {"n": 0}
    decision, result = gw.dispatch_through_gate(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        call=lambda: calls.__setitem__("n", calls["n"] + 1),
        estimate=gw.UsageEstimate(run_cost_usd=6.00),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.IDLE_AND_ALERT
    assert not decision.admitted
    assert decision.alert is not None
    assert calls["n"] == 0, "a budget breach must dispatch nothing"


def test_per_run_token_cap_breach_is_idle_and_alert():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_input_tokens=2_500_000),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.IDLE_AND_ALERT
    assert decision.alert["dimension"] == "per_run"


def test_per_day_cost_breach_is_idle_and_alert():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=1.0, day_cost_usd=16.00),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.IDLE_AND_ALERT


def test_under_budget_is_not_a_breach():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=1.00, run_input_tokens=1000),
        credit_state=gw.CreditState(plan="max_20x", used_usd=0.0),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.ADMIT


def test_monthly_credit_exhaustion_is_sanctioned_pause():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=0.01),
        credit_state=gw.CreditState(plan="pro", used_usd=20.0),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.SANCTIONED_PAUSE
    assert not decision.admitted
    assert decision.alert["on_exhaustion"] == "sanctioned_pause"


def test_credit_exhaustion_never_falls_back_to_admit_metered_overflow():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=0.0),
        credit_state=gw.CreditState(plan="pro", used_usd=999.0),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.SANCTIONED_PAUSE
    assert not hasattr(gw.admit, "metered_overflow")


def test_credit_refresh_resumes_normally_idempotent():
    budgets = _mustaqil()
    exhausted = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        credit_state=gw.CreditState(plan="pro", used_usd=25.0),
        budgets=budgets,
    )
    assert exhausted.outcome is gw.AdmissionOutcome.SANCTIONED_PAUSE

    refreshed = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        credit_state=gw.CreditState(plan="pro", used_usd=0.0),
        budgets=budgets,
    )
    assert refreshed.outcome is gw.AdmissionOutcome.ADMIT


@pytest.mark.parametrize(
    "estimate,credit_state",
    [
        (gw.UsageEstimate(run_cost_usd=100.0), gw.CreditState()),
        (gw.UsageEstimate(), gw.CreditState(plan="pro", used_usd=1000.0)),
    ],
)
def test_non_admit_outcomes_never_raise(estimate, credit_state):
    try:
        decision = gw.admit(
            ticket_id="DAS-9999",
            role="backend-eng-1",
            model="claude-sonnet-4-6",
            estimate=estimate,
            credit_state=credit_state,
            budgets=_mustaqil(),
        )
    except Exception as exc:
        pytest.fail(f"admit() must never raise for a sanctioned non-dispatch, got {exc!r}")
    assert decision.outcome in {
        gw.AdmissionOutcome.IDLE_AND_ALERT,
        gw.AdmissionOutcome.SANCTIONED_PAUSE,
    }
    assert decision.outcome is not gw.AdmissionOutcome.ADMIT


def test_build_subscription_env_has_no_api_key_var_absent_base():
    env = gw.build_subscription_env(base_env={"PATH": "/usr/bin", "HOME": "/var/empty"})
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["PATH"] == "/usr/bin"


def test_build_subscription_env_drops_even_an_empty_api_key():
    base = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "", "OTHER": "keep-me"}
    env = gw.build_subscription_env(base_env=base)
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["OTHER"] == "keep-me"
    assert "ANTHROPIC_API_KEY" not in env


def test_build_subscription_env_drops_a_real_looking_key():
    base = {"ANTHROPIC_API_KEY": "sk-ant-real-looking-value"}
    env = gw.build_subscription_env(base_env=base)
    assert "ANTHROPIC_API_KEY" not in env


def test_build_subscription_env_extra_cannot_reintroduce_key():
    env = gw.build_subscription_env(
        base_env={"HOME": "/var/empty"}, extra={"ANTHROPIC_API_KEY": "sneaky", "FOO": "bar"}
    )
    assert "ANTHROPIC_API_KEY" not in env
    assert env["FOO"] == "bar"


def test_build_subscription_env_no_base_env_defaults_empty():
    env = gw.build_subscription_env()
    assert env == {}
    assert "ANTHROPIC_API_KEY" not in env


def test_gated_admit_inert_when_flag_off():
    decision = gw.gated_admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        flag_enabled=False,
    )
    assert decision.outcome is gw.AdmissionOutcome.UNAVAILABLE
    assert not decision.admitted


def test_gated_admit_reaches_admit_logic_when_flag_on():
    decision = gw.gated_admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        flag_enabled=True,
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.ADMIT


def test_gated_admit_inert_when_flag_disabled():
    decision = gw.gated_admit(
        ticket_id="DAS-9999", role="backend-eng-1", model="claude-sonnet-4-6", flag_enabled=False
    )
    assert decision.outcome is gw.AdmissionOutcome.UNAVAILABLE


def test_gated_admit_no_longer_unavailable_when_flag_on():
    decision = gw.gated_admit(ticket_id="DAS-9999", role="backend-eng-1", model="claude-sonnet-4-6")
    assert decision.outcome is not gw.AdmissionOutcome.UNAVAILABLE


def test_load_mustaqil_budgets_from_real_config():
    mustaqil = gw.load_mustaqil_budgets()
    assert mustaqil, "config/budgets.yaml must carry a non-empty mustaqil: block"
    assert mustaqil["caps"]["per_run"]["max_cost_usd"] == 5.00
    assert mustaqil["caps"]["per_day"]["max_cost_usd"] == 15.00
    assert mustaqil["on_breach"] == "idle_and_alert"
    assert mustaqil["monthly_credit_ceiling"]["on_exhaustion"] == "sanctioned_pause"
    assert mustaqil["monthly_credit_ceiling"]["metered_overflow"] is False
    assert mustaqil["monthly_credit_ceiling"]["plan_credit_usd"]["max_20x"] == 200


def test_load_mustaqil_budgets_missing_file_is_inert():
    mustaqil = gw.load_mustaqil_budgets(path=ROOT / "config" / "does-not-exist.yaml")
    assert mustaqil == {}

    decision = gw.admit(
        ticket_id="DAS-9999", role="backend-eng-1", model="claude-sonnet-4-6", budgets=mustaqil
    )
    assert decision.outcome is gw.AdmissionOutcome.ADMIT
