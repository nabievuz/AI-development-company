"""daslab_sdk.contracts — the typed seam of the WS-B headless runner (DAS-1555).

Pure data + protocols, zero runtime dependency on the Claude Agent SDK or on
``scripts/``.  Importing this module never imports the SDK, never reads the
board, and never touches the network — so the runner's public shapes are usable
(and testable) with the flag OFF and the SDK absent.

The admission types (``AdmissionOutcome`` / ``AdmissionDecision`` / ``Admitter``)
are the *interface* the DAS-1556 admission gateway fills.  The core runner
(``daslab_sdk.runner``) depends on this seam by injection — it never re-implements
the model/budget/auth decision the gateway owns (ADR-0034 SR-2/SR-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

__all__ = [
    "AdmissionDecision",
    "AdmissionOutcome",
    "Admitter",
    "RunnerStatus",
    "TicketDispatchResult",
    "WaveDispatchResult",
]


class RunnerStatus(StrEnum):
    """The terminal status of a headless dispatch attempt.

    Only ``DISPATCHED`` means a model call was actually made.  Every other value
    is a *non-dispatch* — an inert no-op, a clean unavailability, or a
    fail-closed refusal — that never reaches ``query()``.
    """

    DISPATCHED = "dispatched"           # query() invoked from inside an ADMIT
    INERT_FLAG_OFF = "inert_flag_off"   # SR-5: ws_b_agent_sdk_runner OFF ⇒ no-op
    UNAVAILABLE_NO_SDK = "unavailable_no_sdk"    # SR-5: Agent SDK not installed
    UNAVAILABLE_NO_SEAM = "unavailable_no_seam"  # wave_runner seam unimportable
    REFUSED_NO_MODEL = "refused_no_model"        # FR-002: explicit model missing
    REFUSED_NO_ADMITTER = "refused_no_admitter"  # SR-2/SR-3: no admission wired
    ADMISSION_HOLD = "admission_hold"            # SR-2: gateway returned HOLD


class AdmissionOutcome(StrEnum):
    """The verdict the DAS-1556 admission gateway returns for one dispatch."""

    ADMIT = "admit"
    HOLD = "hold"


@dataclass(frozen=True)
class AdmissionDecision:
    """A yes/hold on an already-made routing decision (never a decision-maker).

    The gateway governs *whether* an already-chosen ``(role, model)`` dispatches
    — under the per-dispatch budget and the subscription-auth path — but it makes
    no routing/selection/re-tier choice of its own (ADR-0034 §2.2).
    """

    outcome: AdmissionOutcome
    ticket_id: str
    model: str
    reason: str = ""

    @property
    def admitted(self) -> bool:
        return self.outcome is AdmissionOutcome.ADMIT


@runtime_checkable
class Admitter(Protocol):
    """The admission-gateway call shape the core runner depends on by injection.

    DAS-1556 provides the concrete implementation (model + SI-5 budget + swappable
    Claude-account auth).  The runner calls it, never re-implements it.
    """

    def __call__(self, *, ticket_id: str, role: str, model: str) -> AdmissionDecision: ...


@dataclass(frozen=True)
class TicketDispatchResult:
    """The outcome the runner OBSERVED for a single headless ticket dispatch.

    Carries no routing or merge field (SR-4): a headless dispatch advances a
    ticket toward its reviewer, it never records a self-merge.  ``dispatched`` is
    ``True`` iff ``query()`` was actually invoked.
    """

    ticket_id: str
    status: RunnerStatus
    role: str = ""
    model: str = ""
    reason: str = ""
    output: str = ""
    dispatched: bool = False

    @property
    def is_noop(self) -> bool:
        """True for the two SR-5 non-dispatch outcomes (flag-off / absent SDK)."""
        return self.status in {
            RunnerStatus.INERT_FLAG_OFF,
            RunnerStatus.UNAVAILABLE_NO_SDK,
        }


@dataclass(frozen=True)
class WaveDispatchResult:
    """The outcome of forwarding one wave to the ``run_wave`` seam (SR-3).

    ``attestation`` is the ``wave_runner.WaveAttestation`` that seam returned (or
    ``None`` when the runner was inert / the seam produced nothing).
    """

    status: RunnerStatus
    attestation: object = None
    reason: str = ""
