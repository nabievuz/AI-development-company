#!/usr/bin/env python3


from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feature_flags
from _paths import ROOT

try:
    from alerting import budget_governor as _budget_governor
except ImportError:
    _budget_governor = None

BUDGETS_PATH = ROOT / "config" / "budgets.yaml"


FEATURE_FLAG = "ws_b_agent_sdk_runner"


API_KEY_ENV_VARS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class AdmissionOutcome(StrEnum):

    ADMIT = "admit"
    REJECTED = "rejected"
    IDLE_AND_ALERT = "idle_and_alert"
    SANCTIONED_PAUSE = "sanctioned_pause"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class UsageEstimate:

    run_input_tokens: int = 0
    run_output_tokens: int = 0
    run_cost_usd: float = 0.0
    day_input_tokens: int = 0
    day_output_tokens: int = 0
    day_cost_usd: float = 0.0


@dataclass(frozen=True)
class CreditState:

    plan: str = "max_20x"
    used_usd: float = 0.0


@dataclass(frozen=True)
class AdmissionDecision:

    outcome: AdmissionOutcome
    ticket_id: str
    role: str
    model: str | None
    reason: str
    alert: dict[str, Any] | None = field(default=None)

    @property
    def admitted(self) -> bool:
        return self.outcome is AdmissionOutcome.ADMIT


def load_mustaqil_budgets(path: Path | None = None) -> dict[str, Any]:
    p = path or BUDGETS_PATH
    if yaml is None or not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    mustaqil = data.get("mustaqil")
    return mustaqil if isinstance(mustaqil, dict) else {}


def _token_cap_breach(estimate: UsageEstimate, caps: dict[str, Any]) -> dict[str, Any] | None:
    dims = (
        ("per_run", "run_input_tokens", "max_input_tokens"),
        ("per_run", "run_output_tokens", "max_output_tokens"),
        ("per_day", "day_input_tokens", "max_input_tokens"),
        ("per_day", "day_output_tokens", "max_output_tokens"),
    )
    for dim, est_attr, cap_key in dims:
        cap_block = caps.get(dim) or {}
        limit = cap_block.get(cap_key)
        if limit is None:
            continue
        value = getattr(estimate, est_attr)
        if value >= limit:
            return {
                "dimension": dim,
                "field": est_attr,
                "value": value,
                "limit": limit,
                "over_by": value - limit,
            }
    return None


def check_budget(estimate: UsageEstimate, mustaqil: dict[str, Any]) -> dict[str, Any] | None:
    caps = mustaqil.get("caps") or {}
    if not caps:
        return None

    token_breach = _token_cap_breach(estimate, caps)
    if token_breach is not None:
        return token_breach

    if _budget_governor is not None:
        totals = {
            "per_run_cost_usd": estimate.run_cost_usd,
            "per_day_cost_usd": estimate.day_cost_usd,
        }
        verdict = _budget_governor(totals, {"caps": caps})
        if verdict["status"] == "breach":
            return verdict["details"][0] if verdict["details"] else {"dimension": "cost"}
    return None


def check_credit_exhaustion(
    credit_state: CreditState, mustaqil: dict[str, Any]
) -> dict[str, Any] | None:
    ceiling_cfg = mustaqil.get("monthly_credit_ceiling") or {}
    plan_credits = ceiling_cfg.get("plan_credit_usd") or {}
    limit = plan_credits.get(credit_state.plan)
    if limit is None:
        return None
    if credit_state.used_usd >= limit:
        return {
            "plan": credit_state.plan,
            "used_usd": credit_state.used_usd,
            "limit_usd": limit,
            "on_exhaustion": ceiling_cfg.get("on_exhaustion", "sanctioned_pause"),
        }
    return None


def build_subscription_env(
    base_env: dict[str, str] | None = None,
    *,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    source = dict(base_env) if base_env is not None else {}
    env = {k: v for k, v in source.items() if k not in API_KEY_ENV_VARS}
    if extra:
        env.update({k: v for k, v in extra.items() if k not in API_KEY_ENV_VARS})
    for var in API_KEY_ENV_VARS:
        env.pop(var, None)
    return env


def admit(
    *,
    ticket_id: str,
    role: str,
    model: str | None,
    estimate: UsageEstimate | None = None,
    credit_state: CreditState | None = None,
    budgets: dict[str, Any] | None = None,
) -> AdmissionDecision:
    if not isinstance(model, str) or not model.strip():
        return AdmissionDecision(
            outcome=AdmissionOutcome.REJECTED,
            ticket_id=ticket_id,
            role=role,
            model=model,
            reason=(
                "explicit `model` is absent/empty — LAW 3 fail-closed precondition; "
                "rejected before any model call is reached (frontmatter is never "
                "consulted as a fallback source, claude-code#44385)"
            ),
        )

    mustaqil = budgets if budgets is not None else load_mustaqil_budgets()
    estimate = estimate or UsageEstimate()
    credit_state = credit_state or CreditState()

    budget_breach = check_budget(estimate, mustaqil)
    if budget_breach is not None:
        return AdmissionDecision(
            outcome=AdmissionOutcome.IDLE_AND_ALERT,
            ticket_id=ticket_id,
            role=role,
            model=model,
            reason=(
                f"mustaqil {budget_breach.get('dimension', 'budget')} cap would be "
                "breached by the estimated usage — idle + alert, zero dispatch "
                "(ADR-0027 SI-5, config/budgets.yaml mustaqil.on_breach)"
            ),
            alert=budget_breach,
        )

    credit_exhausted = check_credit_exhaustion(credit_state, mustaqil)
    if credit_exhausted is not None:
        return AdmissionDecision(
            outcome=AdmissionOutcome.SANCTIONED_PAUSE,
            ticket_id=ticket_id,
            role=role,
            model=model,
            reason=(
                "monthly subscription credit exhausted — sanctioned pause, resumes "
                "on credit refresh (Q9, config/budgets.yaml mustaqil.on_exhaustion); "
                "metered_overflow stays OFF, never spilled into to keep dispatching"
            ),
            alert=credit_exhausted,
        )

    return AdmissionDecision(
        outcome=AdmissionOutcome.ADMIT,
        ticket_id=ticket_id,
        role=role,
        model=model,
        reason="admitted: explicit model, within mustaqil budget, credit available",
    )


def gated_admit(
    *,
    ticket_id: str,
    role: str,
    model: str | None,
    estimate: UsageEstimate | None = None,
    credit_state: CreditState | None = None,
    budgets: dict[str, Any] | None = None,
    flag_enabled: bool | None = None,
) -> AdmissionDecision:
    enabled = feature_flags.enabled(FEATURE_FLAG) if flag_enabled is None else flag_enabled
    if not enabled:
        return AdmissionDecision(
            outcome=AdmissionOutcome.UNAVAILABLE,
            ticket_id=ticket_id,
            role=role,
            model=model,
            reason=f"`{FEATURE_FLAG}` flag is OFF (default) — runner inert, no admission logic runs",
        )
    return admit(
        ticket_id=ticket_id,
        role=role,
        model=model,
        estimate=estimate,
        credit_state=credit_state,
        budgets=budgets,
    )


def dispatch_through_gate(
    *,
    ticket_id: str,
    role: str,
    model: str | None,
    call: Any,
    estimate: UsageEstimate | None = None,
    credit_state: CreditState | None = None,
    budgets: dict[str, Any] | None = None,
) -> tuple[AdmissionDecision, Any]:
    decision = admit(
        ticket_id=ticket_id,
        role=role,
        model=model,
        estimate=estimate,
        credit_state=credit_state,
        budgets=budgets,
    )
    if not decision.admitted:
        return decision, None
    return decision, call()


def main(argv: list[str] | None = None) -> int:
    mustaqil = load_mustaqil_budgets()
    print(f"ws_b_agent_sdk_runner flag: {feature_flags.enabled(FEATURE_FLAG)}")
    print(f"mustaqil budgets loaded: {bool(mustaqil)}")
    if mustaqil:
        print(f"  caps: {mustaqil.get('caps')}")
        print(f"  monthly_credit_ceiling: {mustaqil.get('monthly_credit_ceiling')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
