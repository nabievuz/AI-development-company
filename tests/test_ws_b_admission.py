"""WS-B admission-gateway tests (ADR-0009 / ADR-0034 SR-2 / DAS-1556).

Covers scripts/ws_b_admission.py: explicit-model fail-closed admission
(LAW 3), mustaqil budget-breach and monthly-credit-exhaustion handling
(idle+alert / sanctioned pause, FR-007/FR-008), the Claude-subscription
auth env isolation (API-key drop, §4.1), and the shared feature-flag
inertness (SR-5).

  T1  missing/empty explicit model -> REJECTED before any model call
  T2  frontmatter model hint is never a fallback source (claude-code#44385)
  T3  mustaqil per_run/per_day budget breach -> idle_and_alert, zero dispatch
  T4  monthly subscription credit exhaustion -> sanctioned_pause
  T5  idle_and_alert / sanctioned_pause are distinct from ADMIT and from a crash
  T6  constructed env has NO ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN (not even
      empty), even when the base env explicitly sets one
  T7  flag OFF -> gated_admit is inert (UNAVAILABLE), admit() logic unreached
  T8  metered_overflow stays OFF: exhaustion never resolves to ADMIT regardless
  T9  real config/budgets.yaml mustaqil: block loads and is well-formed
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ws_b_admission as gw  # noqa: E402

# ---------------------------------------------------------------------------
# T1 / T2 — explicit-model fail-closed admission (LAW 3 / SR-2 / FR-002)
# ---------------------------------------------------------------------------


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
    """A ticket whose frontmatter carries a `model:` hint but whose dispatch
    call omits the explicit resolved argument must still be rejected — the
    gateway has no code path that reads ticket text at all."""
    ticket_frontmatter_hint = "sonnet"  # what a lazy caller might be tempted to fall back to
    decision = gw.admit(ticket_id="DAS-9999", role="backend-eng-1", model=None)
    assert decision.outcome is gw.AdmissionOutcome.REJECTED
    # sanity: admit() takes no ticket-text parameter, so the hint above is
    # inert by construction — this assertion documents that structural fact.
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


# ---------------------------------------------------------------------------
# T3 — mustaqil budget breach -> idle + alert (ADR-0027 SI-5 / FR-007)
# ---------------------------------------------------------------------------


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
        estimate=gw.UsageEstimate(run_cost_usd=6.00),  # breaches max_cost_usd=5.00
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
        estimate=gw.UsageEstimate(run_input_tokens=2_500_000),  # breaches 2M cap
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.IDLE_AND_ALERT
    assert decision.alert["dimension"] == "per_run"


def test_per_day_cost_breach_is_idle_and_alert():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=1.0, day_cost_usd=16.00),  # breaches 15.00
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


# ---------------------------------------------------------------------------
# T4 / T8 — monthly credit exhaustion -> sanctioned pause (Q9 / FR-008)
# ---------------------------------------------------------------------------


def test_monthly_credit_exhaustion_is_sanctioned_pause():
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=0.01),  # under the per_run cap
        credit_state=gw.CreditState(plan="pro", used_usd=20.0),  # >= pro ceiling of 20
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.SANCTIONED_PAUSE
    assert not decision.admitted
    assert decision.alert["on_exhaustion"] == "sanctioned_pause"


def test_credit_exhaustion_never_falls_back_to_admit_metered_overflow():
    """metered_overflow stays OFF: exhaustion must never resolve to ADMIT no
    matter how much "room" is estimated in the wave — there is no overflow
    parameter on admit() at all (structural, not just configured)."""
    decision = gw.admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",
        estimate=gw.UsageEstimate(run_cost_usd=0.0),  # trivially cheap
        credit_state=gw.CreditState(plan="pro", used_usd=999.0),
        budgets=_mustaqil(),
    )
    assert decision.outcome is gw.AdmissionOutcome.SANCTIONED_PAUSE
    assert not hasattr(gw.admit, "metered_overflow")


def test_credit_refresh_resumes_normally_idempotent():
    """After a 'refresh' (used_usd reset), an identical re-entry admits
    normally — no double-apply, safe to re-run (DAS-1447 guard-before-act)."""
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


# ---------------------------------------------------------------------------
# T5 — breach/exhaustion distinct from ADMIT and from a crash
# ---------------------------------------------------------------------------


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
    except Exception as exc:  # pragma: no cover - the assertion IS "never raises"
        pytest.fail(f"admit() must never raise for a sanctioned non-dispatch, got {exc!r}")
    assert decision.outcome in {
        gw.AdmissionOutcome.IDLE_AND_ALERT,
        gw.AdmissionOutcome.SANCTIONED_PAUSE,
    }
    assert decision.outcome is not gw.AdmissionOutcome.ADMIT


# ---------------------------------------------------------------------------
# T6 — Claude-subscription auth: ANTHROPIC_API_KEY dropped entirely (§4.1)
# ---------------------------------------------------------------------------


def test_build_subscription_env_has_no_api_key_var_absent_base():
    env = gw.build_subscription_env(base_env={"PATH": "/usr/bin", "HOME": "/var/empty"})
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["PATH"] == "/usr/bin"


def test_build_subscription_env_drops_even_an_empty_api_key():
    """The gotcha: ANTHROPIC_API_KEY="" still wins its precedence slot ahead
    of the OAuth profile, so it must be ABSENT from the mapping, not blanked."""
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


# ---------------------------------------------------------------------------
# T7 — feature flag OFF -> gated_admit is inert (SR-5)
# ---------------------------------------------------------------------------


def test_gated_admit_inert_when_flag_off():
    decision = gw.gated_admit(
        ticket_id="DAS-9999",
        role="backend-eng-1",
        model="claude-sonnet-4-6",  # a perfectly valid model — still inert
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


def test_gated_admit_defaults_to_repo_feature_flags_file():
    """With no explicit flag_enabled, gated_admit reads config/features.yaml,
    where ws_b_agent_sdk_runner defaults to false — so today's real repo
    state is inert."""
    decision = gw.gated_admit(ticket_id="DAS-9999", role="backend-eng-1", model="claude-sonnet-4-6")
    assert decision.outcome is gw.AdmissionOutcome.UNAVAILABLE


# ---------------------------------------------------------------------------
# T9 — real config/budgets.yaml mustaqil: block loads and is well-formed
# ---------------------------------------------------------------------------


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
    # inert config never fabricates a breach
    decision = gw.admit(
        ticket_id="DAS-9999", role="backend-eng-1", model="claude-sonnet-4-6", budgets=mustaqil
    )
    assert decision.outcome is gw.AdmissionOutcome.ADMIT
