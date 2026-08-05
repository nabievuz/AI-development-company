
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.state import (
    FIELD_GROUPS,
    GROUP_WRITER,
    GateStatus,
    GraphState,
    StateInvariantError,
    apply_group,
)

__all__ = [
    "FLAG",
    "CHANNELS",
    "CHANNEL_WRITER",
    "NEVER_AUTO_APPROVE",
    "WORKER",
    "INTERRUPT",
    "ProjectedState",
    "RouteDecision",
    "Reconciliation",
    "Checkpoint",
    "RunIdCheckpointer",
    "SubstrateUnavailableError",
    "SubstrateInertError",
    "langgraph_available",
    "drive_enabled",
    "project",
    "apply_channel",
    "reconcile",
    "route_from_supervisor",
    "worker_reachable",
    "make_interrupt_card",
    "commit_wave",
    "build_graph",
    "run_loop",
]


FLAG = "ws_c_langgraph_loop"


CHANNELS: tuple[str, ...] = tuple(FIELD_GROUPS)
CHANNEL_WRITER: dict[str, str] = dict(GROUP_WRITER)


NEVER_AUTO_APPROVE: frozenset[str] = frozenset(
    {
        "new_goal",
        "security_sensitive",
        "schema_migration",
        "gate5_deployment",
        "governance_or_policy",
        "permission_change",
        "secret_change",
    }
)


WORKER = "worker"
INTERRUPT = "interrupt"


class SubstrateUnavailableError(RuntimeError):
    pass


class SubstrateInertError(RuntimeError):
    pass


def drive_enabled(features_path: Path | None = None) -> bool:
    from feature_flags import enabled

    return enabled(FLAG, features_path)


def langgraph_available() -> bool:
    return importlib.util.find_spec("langgraph") is not None


@dataclass
class ProjectedState:

    channels: dict[str, dict[str, Any]]
    run_id: str | None = None

    def field(self, name: str) -> Any:
        for group, fields in FIELD_GROUPS.items():
            if name in fields:
                return self.channels[group].get(name)
        raise KeyError(f"{name!r} is not a graph_state field")


def project(state: GraphState) -> ProjectedState:
    channels: dict[str, dict[str, Any]] = {
        group: {fname: getattr(state, fname) for fname in fields}
        for group, fields in FIELD_GROUPS.items()
    }
    return ProjectedState(channels=channels, run_id=state.run_id)


def apply_channel(
    state: GraphState,
    channel: str,
    updates: dict[str, Any],
    *,
    writer: str,
    review_authorized: bool = False,
) -> None:
    if channel not in CHANNEL_WRITER:
        raise ValueError(
            f"Unknown channel {channel!r}. Valid channels: {sorted(CHANNELS)}"
        )

    expected_writer = CHANNEL_WRITER[channel]
    if writer != expected_writer:

        raise StateInvariantError(
            {
                "rule": "wrong_group_writer_node",
                "field": channel,
                "current": expected_writer,
                "proposed": writer,
                "reason": (
                    f"Node role {writer!r} may not write the {channel!r} channel — "
                    f"its sole writer is {expected_writer!r} (ADR-0011 §1 / ADR-0035 "
                    "LG-3). Routing stays supervisor-only; a worker node has no "
                    "routing-channel write handle."
                ),
            }
        )


    apply_group(state, channel, updates, review_authorized=review_authorized)


@dataclass(frozen=True)
class Reconciliation:

    board_state: GraphState
    diverged: list[tuple[str, str]]
    event: dict[str, Any] | None


def reconcile(projected: ProjectedState, board_state: GraphState) -> Reconciliation:
    diverged: list[tuple[str, str]] = []
    for group, fields in FIELD_GROUPS.items():
        proj_channel = projected.channels.get(group, {})
        for fname in fields:
            board_value = getattr(board_state, fname)
            if proj_channel.get(fname) != board_value:
                diverged.append((group, fname))

    event: dict[str, Any] | None = None
    if diverged:
        event = {
            "event_type": "state_violation",
            "ticket_id": board_state.ticket_id,
            "rule": "board_wins_reconciliation",
            "diverged": [f"{g}.{f}" for g, f in diverged],
            "reason": (
                "LangGraph projection diverged from the board; the projection was "
                "overwritten from the board-derived graph_state (board wins, C2). "
                "The LangGraph checkpoint was NOT used as a tiebreaker."
            ),
        }
    return Reconciliation(board_state=board_state, diverged=diverged, event=event)


@dataclass(frozen=True)
class RouteDecision:

    target: str
    reason: str
    categories: frozenset[str] = frozenset()
    fail_closed: bool = False


def route_from_supervisor(
    state: GraphState,
    *,
    categories: frozenset[str] | set[str] = frozenset(),
    unclassified: bool = False,
) -> RouteDecision:
    naa = frozenset(categories) & NEVER_AUTO_APPROVE
    if naa:
        return RouteDecision(
            target=INTERRUPT,
            reason=f"never-auto-approve categories require the Founder: {sorted(naa)}",
            categories=naa,
            fail_closed=False,
        )
    if unclassified:
        return RouteDecision(
            target=INTERRUPT,
            reason="unclassifiable gate/category — fail-closed halt (§2.2)",
            fail_closed=True,
        )
    if state.predecessor_gate != GateStatus.closed:
        return RouteDecision(
            target=INTERRUPT,
            reason=(
                f"predecessor gate is {state.predecessor_gate!r} (not 'closed') — "
                "no worker node is reachable past an open gate (§2.1)"
            ),
            fail_closed=state.predecessor_gate is None,
        )
    return RouteDecision(
        target=WORKER,
        reason="predecessor gate closed and no never-auto-approve category — gate clear",
    )


def worker_reachable(decision: RouteDecision) -> bool:
    return decision.target == WORKER


def make_interrupt_card(
    state: GraphState,
    decision: RouteDecision,
    *,
    created_by: str = "supervisor",
    options: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "question": (
            f"{state.ticket_id}: {decision.reason}. Approve to proceed, or halt?"
        ),
        "options": options or ["resume", "halt"],
        "ticket": state.ticket_id,
        "payload": {
            "reason": decision.reason,
            "categories": sorted(decision.categories),
            "fail_closed": decision.fail_closed,
            "aadl_stage": state.aadl_stage.value if state.aadl_stage else None,
            "predecessor_gate": (
                state.predecessor_gate.value if state.predecessor_gate else None
            ),
        },
        "created_by": created_by,
    }


@dataclass
class Checkpoint:

    run_id: str
    node: str
    channels: dict[str, dict[str, Any]]
    pending_interrupts: list[str] = field(default_factory=list)

    committed: set[str] = field(default_factory=set)


class RunIdCheckpointer:

    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir
        self._store: dict[str, Checkpoint] = {}

    def save(self, cp: Checkpoint) -> None:
        existing = self._store.get(cp.run_id)
        if existing is not None:

            cp.committed |= existing.committed
        self._store[cp.run_id] = cp

    def load(self, run_id: str) -> Checkpoint | None:
        return self._store.get(run_id)

    def already_committed(self, run_id: str, effect_key: str) -> bool:
        cp = self._store.get(run_id)
        return bool(cp and effect_key in cp.committed)

    def mark_committed(self, run_id: str, effect_key: str) -> None:
        cp = self._store.get(run_id)
        if cp is None:
            cp = Checkpoint(run_id=run_id, node="", channels={})
            self._store[run_id] = cp
        cp.committed.add(effect_key)


def commit_wave(
    plan: Any,
    execute_wave: Any,
    *,
    created_at: str,
    checkpointer: RunIdCheckpointer,
    organism_emit: bool = True,
    **run_wave_kwargs: Any,
) -> Any:
    import wave_runner as _wr

    run_id = plan.run_id
    effect_key = f"wave:{run_id}:{plan.wave}"


    if checkpointer.already_committed(run_id, effect_key):
        return checkpointer.load(run_id).channels.get("_attestation")

    attestation = _wr.run_wave(
        plan,
        execute_wave,
        created_at=created_at,
        organism_emit=organism_emit,
        **run_wave_kwargs,
    )

    if attestation is not None:


        checkpointer.mark_committed(run_id, effect_key)
        cp = checkpointer.load(run_id)
        if cp is not None:
            cp.channels.setdefault("_attestation", attestation)
    return attestation


def build_graph(*, checkpointer: RunIdCheckpointer | None = None) -> Any:
    if not langgraph_available():
        raise SubstrateUnavailableError(
            "LangGraph is not installed. It is an opt-in extra (ADR-0035 LG-5); "
            "install scripts/dgox/requirements-langgraph.txt to enable the runtime. "
            "The substrate is unavailable, not broken — projection/reconcile/route/"
            "checkpoint governance functions remain fully usable without it."
        )


    _lg_graph = importlib.import_module("langgraph.graph")
    StateGraph = _lg_graph.StateGraph
    END = _lg_graph.END

    graph = StateGraph(dict)

    def _supervisor(state: dict[str, Any]) -> dict[str, Any]:
        return state

    def _worker(state: dict[str, Any]) -> dict[str, Any]:
        return state

    def _interrupt(state: dict[str, Any]) -> dict[str, Any]:
        return state

    graph.add_node("supervisor", _supervisor)
    graph.add_node(WORKER, _worker)
    graph.add_node(INTERRUPT, _interrupt)
    graph.set_entry_point("supervisor")

    def _edge(state: dict[str, Any]) -> str:
        gs: GraphState = state["graph_state"]
        decision = route_from_supervisor(
            gs,
            categories=state.get("categories", frozenset()),
            unclassified=state.get("unclassified", False),
        )
        return decision.target

    graph.add_conditional_edges(
        "supervisor", _edge, {WORKER: WORKER, INTERRUPT: INTERRUPT}
    )
    graph.add_edge(WORKER, END)
    graph.add_edge(INTERRUPT, END)
    return graph.compile(checkpointer=checkpointer)


@dataclass(frozen=True)
class InertResult:

    drove: bool = False
    reason: str = f"{FLAG} is OFF — substrate inert, dispatch byte-identical (SC-004a)"


def run_loop(
    *,
    features_path: Path | None = None,
    force_drive: bool = False,
) -> InertResult:
    if not drive_enabled(features_path):
        if force_drive:
            raise SubstrateInertError(
                f"{FLAG} is OFF — refusing to drive a wave (fail-closed). Flip the "
                "flag via the Founder/board act (DAS-1568) before driving."
            )
        return InertResult()


    return InertResult(drove=False, reason=f"{FLAG} ON — shadow posture; drive is a board act (Q4)")
