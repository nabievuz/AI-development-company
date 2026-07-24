#!/usr/bin/env python3
"""ws_b_admission.py — WS-B admission gateway: explicit-model, budget/credit,
Claude-subscription auth env isolation (DAS-1556 / ADR-0009 / ADR-0034 SR-2).

Design: docs/design/ws-b-agent-sdk-runner.md §2 (admission), §4 (auth/budget/
credit). Ratified: ADR-0034 (Accepted 2026-07-24, SR-2); honors ADR-0009's
LAW 8 admission-layer restatement rather than reopening it. Spec:
docs/specs/003-mustaqil-ws-b-runner/SPEC.md FR-002/006/007/008.

This module is a **library only** — it is not wired into any live dispatch
path yet (that is DAS-1555's `daslab_sdk` entrypoint, a distinct repo zone).
It ships behind the shared `ws_b_agent_sdk_runner` feature flag (default OFF,
`config/features.yaml`); importing/calling it does not change any interactive
`/daslab-cycle` wave.

## What `admit()` governs (and does NOT)

Per the design, `admit()` is a fail-closed **yes/hold on an already-made
decision** — it makes NO routing/selection/re-tier decision:

- **explicit-model admission (LAW 3 / SR-2 / FR-002)** — a dispatch with an
  absent/empty/whitespace `model` is REJECTED before any model call is made.
  The ticket frontmatter's own `model:` hint is never consulted here — the
  caller must pass the already-resolved value from
  `governance/policies/model-allocation.md` (claude-code#44385: frontmatter
  alone is never trusted).
- **budget ceiling (ADR-0027 SI-5 / FR-007)** — the `mustaqil:` per-run/
  per-day caps in `config/budgets.yaml` are the SSOT. A dispatch whose
  estimated usage would breach either cap evaluates to `idle_and_alert` —
  zero dispatch, an alert emitted (`scripts/alerting.py` seam) — never a
  partial wave, never a false-green.
- **monthly credit ceiling (Q9 / FR-007 / FR-008)** — the subscription's
  monthly credit is the OUTER ceiling. Exhaustion evaluates to
  `sanctioned_pause`: an expected, resumable halt — never a crash, a silent
  stop, or a failed run. `metered_overflow` stays OFF (hard invariant; no
  parameter on this module can turn it on — flipping it is a Founder-only
  budget decision made in `config/budgets.yaml`, never here).
- **auth (Q9 / FR-006)** — `build_subscription_env()` constructs the isolated
  child env for the headless dispatch and DROPS `ANTHROPIC_API_KEY` /
  `ANTHROPIC_AUTH_TOKEN` entirely (not merely blanked) so the SDK falls
  through its precedence chain to the Claude-account OAuth profile. An empty
  string still wins its precedence slot — the non-obvious gotcha this
  function exists to close (design §4.1).

## Flip-time precondition (bound on DAS-1558)

`config/budgets.yaml` carries a `[NEEDS VERIFICATION at WS-B go-live]` marker:
the live plan's Agent-SDK terms/monthly credit must be re-verified before
`ws_b_agent_sdk_runner` is ever flipped ON. That is a Deployment-time
precondition on DAS-1558, not a build-time blocker here (Q9 already fixes the
model stance) — see design §4.4.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a repo dependency
    yaml = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feature_flags  # noqa: E402
from _paths import ROOT  # noqa: E402

try:
    from alerting import budget_governor as _budget_governor
except ImportError:  # pragma: no cover - alerting.py always ships alongside this module
    _budget_governor = None

BUDGETS_PATH = ROOT / "config" / "budgets.yaml"

# Feature key shared with DAS-1555 (config/features.yaml, ADR-0034).
FEATURE_FLAG = "ws_b_agent_sdk_runner"

# The credential vars the SDK's resolution chain checks BEFORE the OAuth
# profile (design §4.1): ANTHROPIC_API_KEY -> ANTHROPIC_AUTH_TOKEN -> OAuth.
# Both are dropped entirely from the constructed child env — an empty string
# still wins its precedence slot, so "blank it" is not sufficient; the key
# must be ABSENT from the mapping.
API_KEY_ENV_VARS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


# ---------------------------------------------------------------------------
# Outcome vocabulary — distinct from ADMIT and from an unhandled crash
# ---------------------------------------------------------------------------


class AdmissionOutcome(StrEnum):
    """The gateway's return vocabulary (design §2.2, §4.3).

    ADMIT is the only outcome that permits a model call. Every other outcome
    is a sanctioned non-dispatch, never an exception:
      - REJECTED         — fail-closed precondition failure (missing model).
      - IDLE_AND_ALERT    — mustaqil per_run/per_day cap would be breached.
      - SANCTIONED_PAUSE  — monthly subscription credit is exhausted.
      - UNAVAILABLE       — the shared feature flag is OFF; runner inert.
    """

    ADMIT = "admit"
    REJECTED = "rejected"
    IDLE_AND_ALERT = "idle_and_alert"
    SANCTIONED_PAUSE = "sanctioned_pause"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class UsageEstimate:
    """Pre-dispatch estimated usage for one wave/dispatch (design §4.2).

    Estimated (token-estimate + post-hoc accounting), not an inline per-call
    meter — the ADR-0009 harness-era granularity. A dimension left at its
    zero default is simply never a source of breach.
    """

    run_input_tokens: int = 0
    run_output_tokens: int = 0
    run_cost_usd: float = 0.0
    day_input_tokens: int = 0
    day_output_tokens: int = 0
    day_cost_usd: float = 0.0


@dataclass(frozen=True)
class CreditState:
    """The subscription's monthly-credit state (design §4.3, Q9).

    ``plan`` keys into ``mustaqil.monthly_credit_ceiling.plan_credit_usd``
    (``pro`` / ``max_5x`` / ``max_20x``); ``used_usd`` is the credit consumed
    so far this billing cycle.
    """

    plan: str = "max_20x"
    used_usd: float = 0.0


@dataclass(frozen=True)
class AdmissionDecision:
    """The gateway's verdict — never raises for a sanctioned non-dispatch."""

    outcome: AdmissionOutcome
    ticket_id: str
    role: str
    model: str | None
    reason: str
    alert: dict[str, Any] | None = field(default=None)

    @property
    def admitted(self) -> bool:
        return self.outcome is AdmissionOutcome.ADMIT


# ---------------------------------------------------------------------------
# config/budgets.yaml mustaqil: loader
# ---------------------------------------------------------------------------


def load_mustaqil_budgets(path: Path | None = None) -> dict[str, Any]:
    """Read the ``mustaqil:`` block from ``config/budgets.yaml`` (the SSOT).

    Returns ``{}`` (every dimension inert, nothing breaches) if the file or
    yaml module is unavailable — a missing config never fabricates a breach,
    mirroring ``feature_flags.load``'s fail-safe-to-default posture.
    """
    p = path or BUDGETS_PATH
    if yaml is None or not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    mustaqil = data.get("mustaqil")
    return mustaqil if isinstance(mustaqil, dict) else {}


# ---------------------------------------------------------------------------
# Cap checks (§4.2) — cost via the existing alerting.budget_governor seam,
# tokens via a small local check (same shape, no re-implementation of cost).
# ---------------------------------------------------------------------------


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
    """Return a breach dict (`{dimension, ...}`) if `estimate` breaches the
    mustaqil per_run/per_day caps, else None. Checks cost (reusing
    ``alerting.budget_governor`` — REUSE, never re-implement) and tokens."""
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
    """Return an exhaustion dict if the monthly subscription credit is
    depleted for ``credit_state.plan``, else None (§4.3, Q9). Never treats an
    unknown plan as exhausted (fail-safe-inert, mirrors ``check_budget``)."""
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


# ---------------------------------------------------------------------------
# Claude-subscription auth — the isolated, API-key-dropping env (§4.1, §6.2)
# ---------------------------------------------------------------------------


def build_subscription_env(
    base_env: dict[str, str] | None = None,
    *,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the isolated child env for a headless dispatch (design §4.1/§6.2).

    Constructs (never inherits via ``os.environ`` passthrough) a new mapping
    that DROPS ``ANTHROPIC_API_KEY``/``ANTHROPIC_AUTH_TOKEN`` entirely — even
    an ``ANTHROPIC_API_KEY=""`` in ``base_env`` is removed, not blanked, because
    a present-but-empty var still wins its precedence slot ahead of the OAuth
    profile. ``extra`` is applied after the drop and is itself re-filtered, so
    a caller cannot accidentally reintroduce a key var through it.
    """
    source = dict(base_env) if base_env is not None else {}
    env = {k: v for k, v in source.items() if k not in API_KEY_ENV_VARS}
    if extra:
        env.update({k: v for k, v in extra.items() if k not in API_KEY_ENV_VARS})
    for var in API_KEY_ENV_VARS:
        env.pop(var, None)
    return env


# ---------------------------------------------------------------------------
# admit() — the single fail-closed gateway (design §2.2)
# ---------------------------------------------------------------------------


def admit(
    *,
    ticket_id: str,
    role: str,
    model: str | None,
    estimate: UsageEstimate | None = None,
    credit_state: CreditState | None = None,
    budgets: dict[str, Any] | None = None,
) -> AdmissionDecision:
    """The ADR-0009 admission gateway, made real under the SDK (ADR-0034 SR-2).

    Fail-closed precondition order (validated before ANY side effect, mirroring
    ``run_wave``'s own "validate inputs up front" discipline):

    1. explicit ``model`` present and non-blank (LAW 3) — else REJECTED.
    2. mustaqil per_run/per_day cap not breached (SI-5) — else IDLE_AND_ALERT.
    3. monthly subscription credit not exhausted (Q9) — else SANCTIONED_PAUSE.
    4. otherwise ADMIT.

    Makes NO routing/selection/re-tier decision — those stay the orchestrator's
    (SR-3 / `run_wave`-adjacent, out of this gateway's surface entirely).
    """
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
    """``admit()`` wrapped behind the shared ``ws_b_agent_sdk_runner`` flag
    (design §6.1, SR-5). With the flag OFF (default) this is a documented
    no-op: UNAVAILABLE is returned and ``admit()``'s own logic is never
    reached — the same "absent SDK / flag OFF => unavailable, not broken"
    posture the design specifies for the runner as a whole (SC-003).
    """
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
    """Reference caller shape: ``call`` (the model call, e.g. ``query()``) is
    invoked ONLY when ``admit()`` returns ADMIT. Demonstrates, and lets tests
    assert, that a non-ADMIT decision never reaches the model call (SC-002a).
    """
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


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - manual/debug entrypoint
    mustaqil = load_mustaqil_budgets()
    print(f"ws_b_agent_sdk_runner flag: {feature_flags.enabled(FEATURE_FLAG)}")
    print(f"mustaqil budgets loaded: {bool(mustaqil)}")
    if mustaqil:
        print(f"  caps: {mustaqil.get('caps')}")
        print(f"  monthly_credit_ceiling: {mustaqil.get('monthly_credit_ceiling')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
