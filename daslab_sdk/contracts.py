
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

    DISPATCHED = "dispatched"
    INERT_FLAG_OFF = "inert_flag_off"
    UNAVAILABLE_NO_SDK = "unavailable_no_sdk"
    UNAVAILABLE_NO_SEAM = "unavailable_no_seam"
    REFUSED_NO_MODEL = "refused_no_model"
    REFUSED_NO_ADMITTER = "refused_no_admitter"
    ADMISSION_HOLD = "admission_hold"


class AdmissionOutcome(StrEnum):

    ADMIT = "admit"
    HOLD = "hold"


@dataclass(frozen=True)
class AdmissionDecision:

    outcome: AdmissionOutcome
    ticket_id: str
    model: str
    reason: str = ""

    @property
    def admitted(self) -> bool:
        return self.outcome is AdmissionOutcome.ADMIT


@runtime_checkable
class Admitter(Protocol):

    def __call__(self, *, ticket_id: str, role: str, model: str) -> AdmissionDecision: ...


@dataclass(frozen=True)
class TicketDispatchResult:

    ticket_id: str
    status: RunnerStatus
    role: str = ""
    model: str = ""
    reason: str = ""
    output: str = ""
    dispatched: bool = False

    @property
    def is_noop(self) -> bool:
        return self.status in {
            RunnerStatus.INERT_FLAG_OFF,
            RunnerStatus.UNAVAILABLE_NO_SDK,
        }


@dataclass(frozen=True)
class WaveDispatchResult:

    status: RunnerStatus
    attestation: object = None
    reason: str = ""
