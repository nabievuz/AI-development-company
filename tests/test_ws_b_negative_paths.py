"""WS-B negative-path suite + integration-seam adapter (DAS-1557, GATE-4).

Design: docs/design/ws-b-agent-sdk-runner.md §7 (SC-001..SC-004). Prerequisite:
the INTEGRATION-SEAM ADAPTER bound by the CTO at GATE-3 closure (ticket body) —
built here, first, BEFORE the SC-001 dispatch-equivalence work.

Unit-level coverage of the runner (``daslab_sdk``) and of the admission gateway
(``scripts/ws_b_admission.py``) already lives in ``tests/test_ws_b_daslab_sdk_
runner.py`` and ``tests/test_ws_b_admission.py`` respectively — this module does
NOT re-assert those unit facts. What lives here is what neither unit suite can
prove alone: the two units COMPOSED through a translating adapter, end to end.

  ADAPTER        ws_b_admission's 5-outcome AdmissionOutcome -> the runner's
                 2-outcome Admitter protocol (ADMIT -> ADMIT; every other
                 sanctioned outcome -> HOLD), plus the dataclass-shape
                 translation (ticket_id/model/outcome/reason).
  ENUM TRAP      a naive direct injection (no translation) silently scores
                 EVERY real ADMIT as HOLD, because the two AdmissionOutcome
                 enums are distinct classes with distinct identity -- proven
                 here, then shown fixed by the adapter.
  SC-001         dispatch-equivalence: the SAME (plan, results) produces an
                 equal attestation whether driven directly through run_wave
                 (the interactive-equivalent call) or through the headless
                 daslab_sdk.dispatch_wave (one producer, not two).
  SC-002         explicit-model rejection happens BEFORE the admission adapter
                 is ever invoked (frontmatter is not a fallback source).
  SC-003         flag OFF -> inert; the adapter/admission gateway is never
                 reached at all (byte-identical to a runner-absent world).
  SC-004         a real budget-breach and a real credit-exhaustion decision,
                 produced by the REAL ws_b_admission.admit and carried through
                 the adapter into dispatch_ticket, both HOLD -- the query_fn
                 spy is never invoked -- and neither is scored as a crash or a
                 false-green DISPATCHED.

This test-scoped adapter is NOT the production wiring: DAS-1558 binds the live
adapter used at flip time. Nothing here imports the live Agent SDK; the SDK
boundary is always the injected ``query_fn`` spy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import wave_runner as wr  # noqa: E402
import ws_b_admission as gw  # noqa: E402

from daslab_sdk import runner as rn  # noqa: E402
from daslab_sdk.contracts import AdmissionDecision as RunnerAdmissionDecision  # noqa: E402
from daslab_sdk.contracts import AdmissionOutcome as RunnerAdmissionOutcome  # noqa: E402
from daslab_sdk.contracts import RunnerStatus  # noqa: E402

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


def _clear_budgets() -> dict:
    """A mustaqil budget block wide open -- nothing breaches, credit is fresh."""
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


# --------------------------------------------------------------------------- #
# THE INTEGRATION-SEAM ADAPTER (test-scoped; production adapter is DAS-1558)
# --------------------------------------------------------------------------- #


def ws_b_admission_adapter(
    *,
    estimate: gw.UsageEstimate | None = None,
    credit_state: gw.CreditState | None = None,
    budgets: dict | None = None,
    admit_fn=gw.admit,
    call_log: list | None = None,
):
    """Build an ``Admitter`` (runner's 2-outcome protocol) backed by the REAL
    ``ws_b_admission.admit`` (5-outcome gateway).

    The translation this closes over:

      * ``ws_b_admission.AdmissionOutcome.ADMIT``       -> ``contracts.AdmissionOutcome.ADMIT``
      * every other outcome (``REJECTED`` / ``IDLE_AND_ALERT`` /
        ``SANCTIONED_PAUSE`` / ``UNAVAILABLE``)          -> ``contracts.AdmissionOutcome.HOLD``

    and the dataclass-shape translation: ``ws_b_admission.AdmissionDecision``
    (``outcome, ticket_id, role, model, reason, alert``) ->
    ``daslab_sdk.contracts.AdmissionDecision`` (``outcome, ticket_id, model,
    reason``), preserving ``reason`` verbatim so a HOLD is still diagnosable.
    """

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
    """The bug the CTO flagged: NO translation at all. Returns the raw
    ``ws_b_admission.AdmissionDecision`` as if it satisfied the runner's
    ``Admitter`` protocol. Used ONLY to demonstrate the enum-identity trap
    below -- never a real code path."""
    return gw.admit(
        ticket_id=ticket_id, role=role, model=model, budgets=_clear_budgets()
    )


# =========================================================================== #
# THE ENUM-IDENTITY TRAP -- and the adapter that fixes it
# =========================================================================== #


def test_naive_direct_injection_scores_every_real_admit_as_hold(tmp_path):
    """Without the adapter, a real ADMIT is silently scored ADMISSION_HOLD.

    ``rn.dispatch_ticket`` compares ``decision.outcome is not AdmissionOutcome.
    ADMIT`` using the RUNNER's own ``contracts.AdmissionOutcome`` enum. A raw
    ``ws_b_admission.AdmissionDecision`` carries ``ws_b_admission.
    AdmissionOutcome.ADMIT`` -- a DIFFERENT enum class -- so the identity check
    is never true, even for a real admit. This is the silent bug the adapter
    exists to close.
    """
    real_decision = gw.admit(
        ticket_id="DAS-9100", role="backend-eng-1", model="claude-sonnet-4-6",
        budgets=_clear_budgets(),
    )
    assert real_decision.outcome is gw.AdmissionOutcome.ADMIT  # ws_b_admission agrees: real ADMIT

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
    # The bug, demonstrated: a real ADMIT is silently scored as a HOLD.
    assert res.status is RunnerStatus.ADMISSION_HOLD
    assert spy.calls == []


def test_adapter_fixes_the_enum_identity_trap(tmp_path):
    """The SAME real decision, through the adapter, dispatches for real."""
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
    assert len(spy.calls) == 1  # the seam actually dispatches


# =========================================================================== #
# INTEGRATION -- real ADMIT reaches query_fn; every non-ADMIT HOLDs (Task 1)
# =========================================================================== #


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
    """SC-004 through the adapter: budget-breach and credit-exhaustion, each
    produced by the REAL ws_b_admission.admit, both HOLD at the runner and the
    query_fn spy is NEVER invoked -- no false-green dispatch."""
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
    assert spy.calls == []  # SC-004: no dispatch on breach/exhaustion
    assert res.status is not RunnerStatus.DISPATCHED  # not a false-green
    # not a crash / false-red: dispatch_ticket returned a clean result, no raise


def test_missing_model_rejected_before_adapter_is_ever_called(tmp_path):
    """SC-002: the runner's own explicit-model precondition fires BEFORE the
    admission adapter (and therefore before ws_b_admission.admit) is reached
    at all -- frontmatter is never consulted as a fallback (claude-code#44385)."""
    spy = _QuerySpy()
    call_log: list = []
    adapter = ws_b_admission_adapter(budgets=_clear_budgets(), call_log=call_log)
    res = rn.dispatch_ticket(
        ticket_id="DAS-9103",
        role="backend-eng-1",
        model="",  # absent explicit model, even though a frontmatter hint might exist
        prompt="envelope",
        admit=adapter,
        query_fn=spy,
        flag_path=_flag_file(tmp_path, on=True),
    )
    assert res.status is RunnerStatus.REFUSED_NO_MODEL
    assert spy.calls == []
    assert call_log == []  # the adapter (and ws_b_admission.admit) was never invoked


def test_flag_off_adapter_never_reached(tmp_path):
    """SC-003a via the real adapter: with the flag OFF the runner is inert
    before the admission gateway is ever consulted -- byte-identical to a
    world where the adapter/admission module doesn't exist."""
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


# =========================================================================== #
# SC-001 -- dispatch-equivalence: interactive-equivalent vs. headless (SR-3)
# =========================================================================== #


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
    """The SAME (plan, results, created_at) produces an EQUAL attestation
    whether driven directly through ``run_wave`` (the interactive-equivalent
    caller, i.e. what ``/daslab-cycle`` would produce) or through the headless
    ``daslab_sdk.dispatch_wave`` -- one producer, not two (SC-001a/b)."""
    plan, results = _fixed_wave()
    created_at = "2026-07-24T00:00:00Z"

    interactive_dir = tmp_path / "interactive"
    headless_dir = tmp_path / "headless"
    interactive_kw = _hermetic_kwargs(interactive_dir)
    headless_kw = _hermetic_kwargs(headless_dir)

    interactive_att = wr.run_wave(plan, results, created_at=created_at, **interactive_kw)

    headless_res = rn.dispatch_wave(
        plan, results, created_at=created_at,
        flag_path=_flag_file(tmp_path, on=True), **headless_kw,
    )

    assert headless_res.status is RunnerStatus.DISPATCHED
    headless_att = headless_res.attestation
    assert interactive_att is not None and headless_att is not None

    # Same decision data in, same committed payload out -- both dirs are fresh
    # (genesis attest_chain.prev in each), so the FULL payload is comparable,
    # including the self-excluded preimage hash.
    assert interactive_att.payload == headless_att.payload
    assert interactive_att.payload["event_digest"] == headless_att.payload["event_digest"]
    assert interactive_att.payload["ledger_digest"] == headless_att.payload["ledger_digest"]
    assert interactive_att.payload["counts"] == headless_att.payload["counts"]
    assert interactive_att.self_hash == headless_att.self_hash

    # Both ledgers independently reconcile -- no orphan attestation, no chain
    # gap, in EITHER world (one producer per world, not two).
    assert wr.verify_wave_ledger(interactive_kw["ledger_path"], attest_dir=interactive_kw["attest_dir"]) == []
    assert wr.verify_wave_ledger(headless_kw["ledger_path"], attest_dir=headless_kw["attest_dir"]) == []


def test_sc001_flag_off_produces_zero_headless_writes_interactive_unaffected(tmp_path):
    """flag-off == interactive path unaffected: the headless side writes
    NOTHING while the interactive-equivalent call still produces its normal
    attestation (SC-003a's complement to SC-001's equivalence claim)."""
    plan, results = _fixed_wave()
    created_at = "2026-07-24T00:00:00Z"

    interactive_dir = tmp_path / "interactive"
    headless_dir = tmp_path / "headless"
    interactive_kw = _hermetic_kwargs(interactive_dir)
    headless_kw = _hermetic_kwargs(headless_dir)

    interactive_att = wr.run_wave(plan, results, created_at=created_at, **interactive_kw)
    assert interactive_att is not None

    headless_res = rn.dispatch_wave(
        plan, results, created_at=created_at,
        flag_path=_flag_file(tmp_path, on=False), **headless_kw,
    )
    assert headless_res.status is RunnerStatus.INERT_FLAG_OFF
    assert headless_res.attestation is None
    assert not headless_kw["ledger_path"].exists()
    assert not headless_kw["attest_dir"].exists() or list(Path(headless_kw["attest_dir"]).iterdir()) == []
