"""DGO-X Phase-1 graph_state — typed mirror of a ticket's runtime state.

graph_state is a DERIVED mirror, reconstructable by re-reading the board
(board/tickets/*.md) plus replaying the event store.  It is NEVER primary
truth — on any divergence the board wins (ADR 0011 §1, ADR 0010 C2).

Field groups and sole writers (ADR 0011 §1 table):

    Identity   — Board adapter    (ticket_id, goal, parent, project, dept)
    Lifecycle  — Gate engine      (aadl_stage, gate_status, predecessor_gate)
    Routing    — Supervisor only  (assignee, reviewer, routing_reason, confidence)
    Execution  — Dispatch runner  (run_id, workspace_id, branch, pr_url)
    Risk       — Gate / Security  (severity, security_class, approval_required)
    Artifacts  — Worker / CI      (files_changed, docs_changed, test_results, trace_ids)
    Memory     — ArcRift adapter  (recall_id, store_id, memory_scope)

Four invariants are ENFORCED AT WRITE (StateInvariantError raised on breach):

    1. Cannot skip AADL stage   — aadl_stage advances only to its immediate
                                   successor; the predecessor gate must be closed.
    2. Role cannot self-route   — reviewer must differ from author/assignee;
                                   a worker/role agent may never write Routing.
    3. Severity is up-only      — severity may increase autonomously but may only
                                   be lowered by an explicit security/gate review.
    4. Flat ArcRift scope       — memory_scope ∈ {daslab, daslab-<project>}, no slash.

This module is DEPENDENCY-FREE of events.py (built in parallel as DAS-1377).
It raises StateInvariantError carrying a machine-readable ``violation`` field so
a higher layer can convert it to a ``state_violation`` event without creating a
circular import.

Usage (Phase 1, shadow mode — state is computed but does not affect dispatch):

    from dgox.state import GraphState, apply_group, StateInvariantError
    state = GraphState(ticket_id="DAS-1234")
    try:
        apply_group(state, "lifecycle", {"aadl_stage": "design"})
    except StateInvariantError as exc:
        # Hand exc.violation to the event store as a state_violation event.
        ...
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Self-locating root (ADR 0003 / scripts/_paths.py).
# Inserted into sys.path only once, so dgox can import _paths without the
# caller having added scripts/ to sys.path already.
# ──────────────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # scripts/dgox/.. → scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import repo_root  # noqa: E402  (import after sys.path fixup)

#: Repository root resolved at import time (never hardcoded).
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

# ──────────────────────────────────────────────────────────────────────────────
# AADL stage ordering (ADR 0010 §3 / ADR 0011 §1 Lifecycle invariant)
# ──────────────────────────────────────────────────────────────────────────────


class AadlStage(StrEnum):
    """Six-stage AADL lifecycle (AI Agent Lifecycle, governance/policies/ai-agent-lifecycle.md)."""

    planning = "planning"
    design = "design"
    development = "development"
    testing = "testing"
    deployment = "deployment"
    maintenance = "maintenance"


#: Ordered list of stages — used by the cannot-skip invariant.
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
    """Whether the predecessor gate is open or closed."""

    open = "open"
    closed = "closed"


class Severity(StrEnum):
    """Risk severity levels — ordered lowest to highest."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


_SEVERITY_INDEX: dict[Severity, int] = {s: i for i, s in enumerate(Severity)}

# ──────────────────────────────────────────────────────────────────────────────
# Field-group metadata
# ──────────────────────────────────────────────────────────────────────────────

#: Maps group name → tuple of field names that belong to it.
FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("ticket_id", "goal", "parent", "project", "dept"),
    "lifecycle": ("aadl_stage", "gate_status", "predecessor_gate"),
    "routing": ("assignee", "reviewer", "routing_reason", "confidence"),
    "execution": ("run_id", "workspace_id", "branch", "pr_url"),
    "risk": ("severity", "security_class", "approval_required"),
    "artifacts": ("files_changed", "docs_changed", "test_results", "trace_ids"),
    "memory": ("recall_id", "store_id", "memory_scope"),
}

#: Maps group name → its declared sole writer (ADR 0011 §1 table).
GROUP_WRITER: dict[str, str] = {
    "identity": "board_adapter",
    "lifecycle": "gate_engine",
    "routing": "supervisor",
    "execution": "dispatch_runner",
    "risk": "gate_engine_or_security",
    "artifacts": "worker_or_ci",
    "memory": "arcrift_adapter",
}

# Reverse map: field name → group name (computed once)
_FIELD_TO_GROUP: dict[str, str] = {
    fname: gname
    for gname, fnames in FIELD_GROUPS.items()
    for fname in fnames
}

# ──────────────────────────────────────────────────────────────────────────────
# Invariant violation error
# ──────────────────────────────────────────────────────────────────────────────


class StateInvariantError(ValueError):
    """Raised when a write to graph_state would violate an invariant.

    Attributes
    ----------
    violation:
        Machine-readable dict describing the breach.  A higher layer converts
        this to a ``state_violation`` event (without importing events.py here).

        Keys always present:
            ``rule``    — string identifier of the broken invariant
                          (one of: "cannot_skip_aadl_stage", "role_cannot_self_route",
                          "severity_up_only", "flat_arcrift_scope")
            ``field``   — the field whose new value triggered the breach
            ``current`` — the current value (may be None if field was unset)
            ``proposed``— the value that was rejected

        Optional keys (when applicable):
            ``reason``  — human-readable explanation
    """

    def __init__(self, violation: dict[str, Any]) -> None:
        self.violation: dict[str, Any] = violation
        super().__init__(str(violation))


# ──────────────────────────────────────────────────────────────────────────────
# GraphState dataclass
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class GraphState:
    """Typed mirror of a single ticket's lifecycle/routing/execution/risk/artifact/memory state.

    This is a DERIVED record, reconstructable from board + event replay.
    It is NEVER primary truth.  The board (board/tickets/*.md) is canonical.

    All mutation goes through :func:`apply_group`, which enforces the four
    invariants at write time and raises :class:`StateInvariantError` on breach.

    Sole-writer contract (ADR 0011 §1):
        Each field group is owned by exactly one component (see ``GROUP_WRITER``).
        A component that does not own a group must not pass those fields to
        ``apply_group``.  In Phase-1 shadow mode this is advisory; the invariant
        checker records the violation rather than blocking dispatch.

    Parameters
    ----------
    ticket_id:
        The DAS-NNNN ticket identifier.  Required; must be non-empty.

    All other fields default to ``None`` / empty collections and are populated
    progressively as the board adapter, gate engine, supervisor, etc. write
    their respective groups.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    # SOLE WRITER: board_adapter
    # Populated from ticket frontmatter; never invented by the adapter.
    ticket_id: str = ""
    goal: str | None = None
    parent: str | None = None
    project: str | None = None
    dept: str | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    # SOLE WRITER: gate_engine
    # Invariant: aadl_stage advances only to its immediate successor;
    #            predecessor_gate must be "closed" before advancing.
    aadl_stage: AadlStage | None = None
    gate_status: GateStatus | None = None
    predecessor_gate: GateStatus | None = None

    # ── Routing ───────────────────────────────────────────────────────────────
    # SOLE WRITER: supervisor
    # Invariant: reviewer ≠ author/assignee (never self-review; ADR 0011 §1).
    # A worker/role agent may never write this group (ADR 0010 C3).
    assignee: str | None = None
    reviewer: str | None = None
    routing_reason: str | None = None
    confidence: float | None = None

    # ── Execution ─────────────────────────────────────────────────────────────
    # SOLE WRITER: dispatch_runner / PR bot
    # run_id correlates this run across events, CI, and the ticket log.
    run_id: str | None = None
    workspace_id: str | None = None
    branch: str | None = None
    pr_url: str | None = None

    # ── Risk ──────────────────────────────────────────────────────────────────
    # SOLE WRITER: gate_engine / security
    # Invariant: severity is up-only without an explicit review event.
    severity: Severity | None = None
    security_class: str | None = None
    approval_required: bool = False

    # ── Artifacts ─────────────────────────────────────────────────────────────
    # SOLE WRITER: worker / CI adapters
    # files_changed and docs_changed are co-updated when a code change requires
    # a documentation change; trace_ids link artifact fields to events.
    files_changed: list[str] = field(default_factory=list)
    docs_changed: list[str] = field(default_factory=list)
    test_results: dict[str, Any] = field(default_factory=dict)
    trace_ids: list[str] = field(default_factory=list)

    # ── Memory ────────────────────────────────────────────────────────────────
    # SOLE WRITER: arcrift_adapter
    # Invariant: memory_scope ∈ {daslab, daslab-<project>}, NO slash (ADR 0008 / LAW 4).
    recall_id: str | None = None
    store_id: str | None = None
    memory_scope: str | None = None

    # ── Internal ─────────────────────────────────────────────────────────────
    # The author field is not a standard graph_state group field but is stored
    # here for the self-route invariant check (reviewer ≠ author).
    _author: str | None = field(default=None, repr=False, compare=False)

    def set_author(self, author: str) -> None:
        """Record the ticket author for self-route invariant checking."""
        self._author = author


# ──────────────────────────────────────────────────────────────────────────────
# Invariant checkers (pure functions — no side effects)
# ──────────────────────────────────────────────────────────────────────────────


def _check_aadl_stage(
    state: GraphState,
    proposed_stage: Any,
    proposed_predecessor_gate: Any,
) -> None:
    """Invariant 1: cannot skip an AADL stage.

    The proposed stage must be:
      - the same as the current stage (no-op update), OR
      - exactly one step ahead of the current stage, AND
        the current predecessor_gate must be ``closed``.

    If the current stage is None (unset), any stage is a valid first write.
    """
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
        # First write — any valid stage is accepted.
        return

    if proposed == current:
        # No-op — stage unchanged, always allowed.
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

    # Advancing to the next stage requires the predecessor gate to be closed.
    # Resolve the effective predecessor_gate: the proposed value (if supplied)
    # takes precedence over the current state value.
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
    """Invariant 2: reviewer must differ from author and assignee.

    ADR 0011 §1 Routing: ``reviewer ≠ author``; ADR 0010 C3 forbids a worker/
    role agent from writing the Routing group.  Here we enforce the structural
    check: the proposed reviewer must not equal the ticket's author or assignee.
    """
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
    """Invariant 3: severity is up-only without an explicit review event.

    ``severity`` may increase autonomously.  It may only be *lowered* by an
    explicit security/gate review event.  In Phase-1 shadow mode the gate does
    not block, but this check raises StateInvariantError so the caller can
    record a ``state_violation`` event.

    To lower severity, the caller must pass ``review_authorized=True`` to
    :func:`apply_group`.
    """
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
        return  # First write — any level accepted.

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
    """Invariant 4: memory_scope must be flat — no slash (ADR 0008 / LAW 4).

    Valid values: ``"daslab"`` or ``"daslab-<project>"`` where ``<project>``
    contains no slash.  An empty string or None is accepted (field not set).
    """
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


# ──────────────────────────────────────────────────────────────────────────────
# Public write API
# ──────────────────────────────────────────────────────────────────────────────


def apply_group(
    state: GraphState,
    group: str,
    updates: dict[str, Any],
    *,
    review_authorized: bool = False,
) -> None:
    """Apply a dict of field updates to *state*, enforcing all invariants at write.

    Parameters
    ----------
    state:
        The :class:`GraphState` to mutate.
    group:
        The field group being written (must be a key in ``FIELD_GROUPS``).
        Only fields belonging to this group may be present in *updates*.
    updates:
        Mapping of field name → new value.  Fields not in *updates* are
        unchanged.
    review_authorized:
        If ``True``, the severity-up-only invariant is relaxed for this write,
        permitting a downgrade.  Set only when an explicit security/gate review
        event has been recorded.  (Default: ``False``.)

    Raises
    ------
    ValueError
        If ``group`` is not a recognised field group.
    StateInvariantError
        If any invariant is violated.  The ``violation`` attribute carries a
        machine-readable dict for conversion to a ``state_violation`` event.
    """
    if group not in FIELD_GROUPS:
        raise ValueError(
            f"Unknown field group {group!r}. Valid groups: {sorted(FIELD_GROUPS)}"
        )

    allowed_fields = FIELD_GROUPS[group]

    # ── Invariant checks (before any mutation) ───────────────────────────────

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

    # ── Apply updates (all invariants passed) ────────────────────────────────
    for fname, value in updates.items():
        if fname not in allowed_fields:
            # Field is not in the declared group — reject per ADR 0011 §1
            # (the state_violation event is the caller's responsibility).
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

        # Coerce enum fields to their enum type when a plain string is supplied.
        if value is not None:
            if fname == "aadl_stage":
                value = AadlStage(value)
            elif fname in ("gate_status", "predecessor_gate"):
                value = GateStatus(value)
            elif fname == "severity":
                value = Severity(value)

        setattr(state, fname, value)
