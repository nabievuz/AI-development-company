
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import repo_root


ROOT = repo_root()

__all__ = [
    "AadlStage",
    "GateStatus",
    "Severity",
    "GraphState",
    "StateInvariantError",
    "apply_group",
    "AADL_ORDER",
    "FIELD_GROUPS",
    "GROUP_WRITER",
]


class AadlStage(StrEnum):

    planning = "planning"
    design = "design"
    development = "development"
    testing = "testing"
    deployment = "deployment"
    maintenance = "maintenance"


AADL_ORDER: list[AadlStage] = [
    AadlStage.planning,
    AadlStage.design,
    AadlStage.development,
    AadlStage.testing,
    AadlStage.deployment,
    AadlStage.maintenance,
]

_AADL_INDEX: dict[AadlStage, int] = {s: i for i, s in enumerate(AADL_ORDER)}


class GateStatus(StrEnum):

    open = "open"
    closed = "closed"


class Severity(StrEnum):

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


_SEVERITY_INDEX: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}


FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("ticket_id", "goal", "parent", "project", "dept"),
    "lifecycle": ("aadl_stage", "gate_status", "predecessor_gate"),
    "routing": ("assignee", "reviewer", "routing_reason", "confidence"),
    "execution": ("run_id", "workspace_id", "branch", "pr_url"),
    "risk": ("severity", "security_class", "approval_required"),
    "artifacts": ("files_changed", "docs_changed", "test_results", "trace_ids"),
    "memory": ("recall_id", "store_id", "memory_scope"),
}


GROUP_WRITER: dict[str, str] = {
    "identity": "board_adapter",
    "lifecycle": "gate_engine",
    "routing": "supervisor",
    "execution": "dispatch_runner",
    "risk": "gate_engine_or_security",
    "artifacts": "worker_or_ci",
    "memory": "arcrift_adapter",
}


_FIELD_TO_GROUP: dict[str, str] = {
    fname: gname
    for gname, fnames in FIELD_GROUPS.items()
    for fname in fnames
}


class StateInvariantError(ValueError):

    def __init__(self, violation: dict[str, Any]) -> None:
        self.violation: dict[str, Any] = violation
        super().__init__(str(violation))


@dataclass
class GraphState:


    ticket_id: str = ""
    goal: str | None = None
    parent: str | None = None
    project: str | None = None
    dept: str | None = None


    aadl_stage: AadlStage | None = None
    gate_status: GateStatus | None = None
    predecessor_gate: GateStatus | None = None


    assignee: str | None = None
    reviewer: str | None = None
    routing_reason: str | None = None
    confidence: float | None = None


    run_id: str | None = None
    workspace_id: str | None = None
    branch: str | None = None
    pr_url: str | None = None


    severity: Severity | None = None
    security_class: str | None = None
    approval_required: bool = False


    files_changed: list[str] = field(default_factory=list)
    docs_changed: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    trace_ids: list[str] = field(default_factory=list)


    recall_id: str | None = None
    store_id: str | None = None
    memory_scope: str | None = None


    _author: str | None = field(default=None, repr=False, compare=False)

    def set_author(self, author: str) -> None:
        self._author = author


def _check_aadl_stage(
    state: GraphState,
    proposed_stage: Any,
    proposed_predecessor_gate: Any,
) -> None:
    try:
        proposed = AadlStage(proposed_stage)
    except ValueError as err:
        raise StateInvariantError(
            {
                "rule": "cannot_skip_aadl_stage",
                "field": "aadl_stage",
                "current": state.aadl_stage.value if state.aadl_stage else None,
                "proposed": proposed_stage,
                "reason": f"Unknown AADL stage: {proposed_stage!r}. "
                f"Valid stages: {[s.value for s in AadlStage]}",
            }
        ) from err

    current = state.aadl_stage
    if current is None:

        return

    if proposed == current:

        return

    current_idx = _AADL_INDEX[current]
    proposed_idx = _AADL_INDEX[proposed]

    if proposed_idx != current_idx + 1:
        raise StateInvariantError(
            {
                "rule": "cannot_skip_aadl_stage",
                "field": "aadl_stage",
                "current": current.value,
                "proposed": proposed.value,
                "reason": (
                    f"Stage must advance exactly one step at a time "
                    f"({current.value!r} → next is "
                    f"{AADL_ORDER[current_idx + 1].value!r} if not at end, "
                    f"not {proposed.value!r})."
                ),
            }
        )


    effective_gate = proposed_predecessor_gate
    if effective_gate is None:
        effective_gate = state.predecessor_gate

    if effective_gate is None or GateStatus(effective_gate) != GateStatus.closed:
        raise StateInvariantError(
            {
                "rule": "cannot_skip_aadl_stage",
                "field": "predecessor_gate",
                "current": state.predecessor_gate.value if state.predecessor_gate else None,
                "proposed": proposed.value,
                "reason": (
                    f"Cannot advance from {current.value!r} to {proposed.value!r}: "
                    f"predecessor gate must be 'closed' (currently "
                    f"{effective_gate!r})."
                ),
            }
        )


def _check_self_route(
    state: GraphState,
    proposed_reviewer: Any,
) -> None:
    if proposed_reviewer is None:
        return

    reviewer = str(proposed_reviewer)
    author = state._author
    assignee = state.assignee

    if author and reviewer == author:
        raise StateInvariantError(
            {
                "rule": "role_cannot_self_route",
                "field": "reviewer",
                "current": state.reviewer,
                "proposed": reviewer,
                "reason": (
                    f"Reviewer {reviewer!r} equals the ticket author {author!r}. "
                    "Self-review is forbidden (ADR 0011 §1, board/ROUTING.md)."
                ),
            }
        )

    if assignee and reviewer == assignee:
        raise StateInvariantError(
            {
                "rule": "role_cannot_self_route",
                "field": "reviewer",
                "current": state.reviewer,
                "proposed": reviewer,
                "reason": (
                    f"Reviewer {reviewer!r} equals the current assignee {assignee!r}. "
                    "An assignee cannot review their own work (ADR 0011 §1)."
                ),
            }
        )


def _check_severity_up_only(
    state: GraphState,
    proposed_severity: Any,
) -> None:
    if proposed_severity is None:
        return

    try:
        proposed = Severity(proposed_severity)
    except ValueError as err:
        raise StateInvariantError(
            {
                "rule": "severity_up_only",
                "field": "severity",
                "current": state.severity.value if state.severity else None,
                "proposed": proposed_severity,
                "reason": f"Unknown severity level: {proposed_severity!r}. "
                f"Valid levels: {[s.value for s in Severity]}",
            }
        ) from err

    current = state.severity
    if current is None:
        return

    if _SEVERITY_INDEX[proposed] < _SEVERITY_INDEX[current]:
        raise StateInvariantError(
            {
                "rule": "severity_up_only",
                "field": "severity",
                "current": current.value,
                "proposed": proposed.value,
                "reason": (
                    f"Severity may not be lowered autonomously "
                    f"({current.value!r} → {proposed.value!r}). "
                    "An explicit security/gate review event is required."
                ),
            }
        )


def _check_flat_arcrift_scope(proposed_scope: Any) -> None:
    if proposed_scope is None or proposed_scope == "":
        return

    scope = str(proposed_scope)

    if "/" in scope:
        raise StateInvariantError(
            {
                "rule": "flat_arcrift_scope",
                "field": "memory_scope",
                "current": None,
                "proposed": scope,
                "reason": (
                    f"memory_scope must not contain a slash (ADR 0008 / LAW 4). "
                    f"Got: {scope!r}. Valid forms: 'daslab' or 'daslab-<project>'."
                ),
            }
        )

    if not re.match(r"^daslab(-[a-zA-Z0-9][a-zA-Z0-9_-]*)?$", scope):
        raise StateInvariantError(
            {
                "rule": "flat_arcrift_scope",
                "field": "memory_scope",
                "current": None,
                "proposed": scope,
                "reason": (
                    f"memory_scope must be 'daslab' or 'daslab-<project>' "
                    f"(letters, digits, hyphens, underscores only in the project part). "
                    f"Got: {scope!r}."
                ),
            }
        )


def apply_group(
    state: GraphState,
    group: str,
    updates: dict[str, Any],
    *,
    review_authorized: bool = False,
) -> None:
    if group not in FIELD_GROUPS:
        raise ValueError(
            f"Unknown field group {group!r}. Valid groups: {sorted(FIELD_GROUPS)}"
        )

    allowed_fields = FIELD_GROUPS[group]


    if group == "lifecycle" and "aadl_stage" in updates:
        proposed_stage = updates.get("aadl_stage", state.aadl_stage)
        proposed_gate = updates.get("predecessor_gate", state.predecessor_gate)
        _check_aadl_stage(state, proposed_stage, proposed_gate)

    if group == "routing" and "reviewer" in updates:
        _check_self_route(state, updates["reviewer"])

    if group == "risk" and "severity" in updates and not review_authorized:
        _check_severity_up_only(state, updates["severity"])

    if group == "memory" and "memory_scope" in updates:
        _check_flat_arcrift_scope(updates["memory_scope"])


    for fname, value in updates.items():
        if fname not in allowed_fields:


            raise StateInvariantError(
                {
                    "rule": "wrong_group_writer",
                    "field": fname,
                    "current": getattr(state, fname, None),
                    "proposed": value,
                    "reason": (
                        f"Field {fname!r} belongs to group "
                        f"{_FIELD_TO_GROUP.get(fname, '<unknown>')!r}, "
                        f"not {group!r}. Each group has a single declared writer "
                        "(ADR 0011 §1)."
                    ),
                }
            )


        if value is not None:
            if fname == "aadl_stage":
                value = AadlStage(value)
            elif fname in ("gate_status", "predecessor_gate"):
                value = GateStatus(value)
            elif fname == "severity":
                value = Severity(value)

        setattr(state, fname, value)
