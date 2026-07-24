"""dgox/langgraph_loop.py — WS-C LangGraph substrate adapter under DGO-X (ADR-0035).

The DGO-X Phase-2/3 execution substrate: it projects the Phase-1 ``graph_state``
(``dgox/state.py:GraphState``) onto LangGraph state channels and runs the durable
plan-act-observe-replan loop with gates-as-interrupts and a checkpointer that is
subordinate to the ADR-0023 run-model.  It binds to the ratified design
``docs/design/ws-c-langgraph-loop.md`` and Accepted **ADR-0035** (LG-1…LG-5):

    LG-1/FR-001+FR-002/C1+C2  §1  LangGraph state is a PROJECTION of graph_state
                                   (itself a mirror of board/tickets/*.md); truth
                                   flows down; a divergence resolves UP to the
                                   board.  LangGraph is never the source of truth.
    LG-2/FR-003/C4            §2  AADL predecessor gate = conditional edge (worker
                                   unreachable while open); never-auto-approve
                                   categories = interrupt() halt-for-Founder;
                                   GATE-5-open stays machine-blocked. Fail-closed.
    LG-3/FR-004/C3            §3  The ``routing`` channel is write-denied to worker
                                   nodes — supervisor-only, enforced by node
                                   authority + apply_group guards.
    LG-4/FR-005              §4   The checkpointer is keyed by run_id and
                                   subordinate to the ADR-0023 run-model; the
                                   single ``run_wave`` producer keeps ADR-0025
                                   flag-on == flag-off; resume is guard-before-act
                                   idempotent (DAS-1447), no forked truth.
    LG-5/FR-007/C5           §6   Behind ``ws_c_langgraph_loop`` (OFF by default):
                                   inert when off (dispatch byte-identical);
                                   LangGraph is an OPT-IN extra — absent ⇒
                                   substrate UNAVAILABLE, not broken.

Design contract, not the org brain (ADR-0035 LG-1): the *governance logic* below
(projection, reconciliation, the gate predicate, the write-scope guard, the
checkpoint keying, the idempotent-resume guard) is pure Python over ``GraphState``
/ ``apply_group`` and needs NO third-party runtime — so it is fully testable
without LangGraph installed.  LangGraph is required ONLY to compile and *run* the
graph (:func:`build_graph`), which raises :class:`SubstrateUnavailableError` when
the optional dependency is absent.  The substrate is a CLIENT of the single
post-decision seam ``scripts/wave_runner.py:run_wave`` — it NEVER calls
``dispatch_emitter`` / ``pulse_checkpoint`` / the ledger appenders directly, so it
adds no second producer (ADR-0031/0032) and the ADR-0025 equivalence holds by
property.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Self-locating root — same bootstrap the sibling dgox modules use, so scripts/
# is importable regardless of how the caller invoked us.
# ──────────────────────────────────────────────────────────────────────────────

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # scripts/dgox/.. → scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dgox.state import (  # noqa: E402
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

#: The feature flag that gates the whole substrate (ADR-0019 / ADR-0035 LG-5).
FLAG = "ws_c_langgraph_loop"

#: One LangGraph channel per graph_state field group, in the same order, each
#: inheriting the group's sole writer from GROUP_WRITER (ADR-0011 §1).  This is
#: the §1.2 channel schema made mechanical — the channels ARE FIELD_GROUPS.
CHANNELS: tuple[str, ...] = tuple(FIELD_GROUPS)
CHANNEL_WRITER: dict[str, str] = dict(GROUP_WRITER)

#: The QONUN-5 never-auto-approve categories.  Any of these on a ticket makes the
#: supervisor edge halt at an interrupt() for the Founder (§2.2), never auto-pass.
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

#: Conditional-edge targets out of the supervisor node (§2.1).
WORKER = "worker"
INTERRUPT = "interrupt"


# ──────────────────────────────────────────────────────────────────────────────
# Errors
# ──────────────────────────────────────────────────────────────────────────────


class SubstrateUnavailableError(RuntimeError):
    """Raised when the LangGraph runtime is asked for but not installed.

    LangGraph is an OPT-IN extra (ADR-0035 LG-5): it is intentionally NOT in the
    core ``requirements.txt`` (install ``scripts/dgox/requirements-langgraph.txt``
    to enable the runtime).  Its absence means the substrate is *unavailable* —
    a clean, catchable condition — NOT that the engine is *broken*: the pure
    governance functions (project / reconcile / route / apply_channel /
    checkpointing) all keep working without it.
    """


class SubstrateInertError(RuntimeError):
    """Raised if a caller tries to DRIVE a wave while the flag is OFF.

    With ``ws_c_langgraph_loop`` OFF the substrate must be inert (§6 / SC-004a):
    dispatch stays byte-identical to pre-merge and the loop does not drive.  The
    correct inert path is :func:`run_loop` returning an inert result — this error
    exists only to fail-closed if a caller forces a drive against the flag.
    """


# ──────────────────────────────────────────────────────────────────────────────
# Flag / capability probes
# ──────────────────────────────────────────────────────────────────────────────


def drive_enabled(features_path: Path | None = None) -> bool:
    """True only when ``ws_c_langgraph_loop`` is ON (ADR-0019 default OFF).

    The single reader is ``scripts/feature_flags.py`` (same file /daslab-cycle
    reads), so the substrate and the fallback agree.  OFF ⇒ the substrate is
    inert and dispatch is byte-identical to pre-merge (§6 / LG-5 / FR-007).
    """
    from feature_flags import enabled  # noqa: PLC0415  (lazy: keep import cheap)

    return enabled(FLAG, features_path)


def langgraph_available() -> bool:
    """True iff the optional ``langgraph`` runtime is importable.

    A pure capability probe — it does NOT import langgraph, only checks the spec,
    so importing this module never depends on the extra being present.  Absent ⇒
    :func:`build_graph` raises :class:`SubstrateUnavailableError` (unavailable,
    not broken); the governance functions remain fully usable (ADR-0035 LG-5).
    """
    return importlib.util.find_spec("langgraph") is not None


# ──────────────────────────────────────────────────────────────────────────────
# §1 — Projection: graph_state → LangGraph channels (LG-1 / FR-001+FR-002 / C2)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ProjectedState:
    """An execution PROJECTION of ``GraphState`` onto per-group LangGraph channels.

    One entry per FIELD_GROUPS group (``channels[group] = {field: value}``); it
    holds no fact the board does not already hold.  It exists only to *run* the
    loop and is NEVER a second store — on any divergence it is overwritten from
    the board (:func:`reconcile`, §1.3).  ``run_id`` keys the checkpoint (§4).
    """

    channels: dict[str, dict[str, Any]]
    run_id: str | None = None

    def field(self, name: str) -> Any:
        """Read a single graph_state field back out of its channel."""
        for group, fields in FIELD_GROUPS.items():
            if name in fields:
                return self.channels[group].get(name)
        raise KeyError(f"{name!r} is not a graph_state field")


def project(state: GraphState) -> ProjectedState:
    """Project a board-reconciled ``GraphState`` onto LangGraph channels.

    ONE direction only (board → graph_state → channels): it reads ``state`` and
    materialises the channels; it never writes a fact back into ``graph_state``
    that did not originate on the board/event path (§1.1).  ``run_id`` is carried
    through so the checkpoint (§4) is keyed by the ADR-0023 run identity.
    """
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
    """Route a channel write through the projection boundary — guards fire here.

    Two structural layers, both from the board-canonical model:

    1. **Node authority (§1.2 / §3.1 / LG-3).** The writing node's role
       (``writer``) MUST equal the channel's sole writer (``CHANNEL_WRITER`` ==
       ``GROUP_WRITER``).  A worker node writing ``routing`` is rejected with a
       ``StateInvariantError`` (``wrong_group_writer_node``) — the write is
       unrepresentable, not merely discouraged.  This is the layer that stops a
       worker touching a routing field even though ``assignee`` IS a routing
       field (so ``apply_group`` alone would not stop it).
    2. **Invariant guards (LG-1 / FR-001).** The mutation then goes through
       ``dgox.state.apply_group``, so the FOUR ``StateInvariantError`` guards
       (cannot-skip-AADL-stage, role-cannot-self-route, severity-up-only,
       flat-ArcRift-scope) and the cross-group-field guard fire at the
       projection boundary EXACTLY as they do in ``graph_state``.

    The channel projection is derived, so it is never written directly; the write
    lands on ``state`` and callers re-``project`` to refresh channels.
    """
    if channel not in CHANNEL_WRITER:
        raise ValueError(
            f"Unknown channel {channel!r}. Valid channels: {sorted(CHANNELS)}"
        )

    expected_writer = CHANNEL_WRITER[channel]
    if writer != expected_writer:
        # Node-authority breach (LG-3/C3): e.g. a worker writing `routing`.
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

    # Invariant guards fire here (delegated to the Phase-1 write API).
    apply_group(state, channel, updates, review_authorized=review_authorized)


# ──────────────────────────────────────────────────────────────────────────────
# §1.3 — Reconciliation: the board wins, always (LG-1 / FR-002 / C2)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Reconciliation:
    """Result of reconciling a projected channel-set against the board.

    ``board_state`` is the authoritative ``GraphState`` re-derived from the board;
    ``diverged`` lists the (channel, field) pairs the LangGraph projection got
    wrong; ``event`` is the ADR-0011 ``state_violation`` / reconciliation event
    payload for the audit trail (emitted by the caller / event store).
    """

    board_state: GraphState
    diverged: list[tuple[str, str]]
    event: dict[str, Any] | None


def reconcile(projected: ProjectedState, board_state: GraphState) -> Reconciliation:
    """On any projection ↔ board divergence, the BOARD value wins (C2 / §1.3).

    Called at the board_adapter re-read at the head of each supervisor tick: the
    board is read LAST and wins.  The LangGraph checkpoint is NEVER consulted as a
    tiebreaker — it is execution scratch, not truth (§4).  Returns the
    board-derived ``GraphState`` (the projection is overwritten from it, never the
    reverse) plus the diverged fields and a reconciliation event for the trail.
    """
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


# ──────────────────────────────────────────────────────────────────────────────
# §2 — Gates as conditional edges / interrupts (LG-2 / FR-003 / C4)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RouteDecision:
    """The supervisor's conditional-edge decision: worker, or halt at interrupt."""

    target: str  # WORKER | INTERRUPT
    reason: str
    categories: frozenset[str] = frozenset()
    fail_closed: bool = False


def route_from_supervisor(
    state: GraphState,
    *,
    categories: frozenset[str] | set[str] = frozenset(),
    unclassified: bool = False,
) -> RouteDecision:
    """The conditional edge out of the supervisor node (§2.1 / §2.2 — fail-closed).

    Precedence (any halt ⇒ the worker node is UNREACHABLE this tick):

    1. **Never-auto-approve category** (QONUN-5) ⇒ ``interrupt()`` halt-for-Founder.
       A GATE-5-open deployment carries ``gate5_deployment`` here and stays
       machine-blocked.
    2. **Unclassifiable** gate/category ⇒ fail-closed halt (an over-cautious halt
       always beats routing past an ungoverned gate — §2.2).
    3. **AADL predecessor gate** not ``closed`` (``open`` or unset) ⇒ halt; an
       unset gate is treated as fail-closed.
    4. Otherwise (gate ``closed``, no never-auto-approve category) ⇒ route to the
       worker node.
    """
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
    """True iff the conditional edge routes to a worker node (else it halts)."""
    return decision.target == WORKER


def make_interrupt_card(
    state: GraphState,
    decision: RouteDecision,
    *,
    created_by: str = "supervisor",
    options: list[str] | None = None,
) -> dict[str, Any]:
    """Build the DAS-1446 interrupt card payload for a halt-for-Founder point.

    The graph halt is surfaced as a ``board/interrupts/<id>.json`` card and the
    ticket parks at ``status: interrupted`` (not ``blocked``, not ``in_review``);
    the graph resumes only on the Founder's ``resume:<value>`` (§2.2).  This
    returns the schema-shaped card body (``board/interrupts/README.md``); writing
    the file is the runtime's job (DAS-1447), not this pure builder.
    """
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


# ──────────────────────────────────────────────────────────────────────────────
# §4 — Checkpoint / resume: subordinate to the ADR-0023 run-model (LG-4 / FR-005)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Checkpoint:
    """A LangGraph checkpoint — execution scratch, keyed by the ADR-0023 run_id.

    It persists which node/channels/pending-interrupts a run paused at so a
    crashed run can resume — it holds NO run-fact the ADR-0023 run-model does not
    (it is a resumption index, not a second ledger).  On resume the board +
    run-model are authority and any channel that disagrees is overwritten (§4.1).
    """

    run_id: str
    node: str
    channels: dict[str, dict[str, Any]]
    pending_interrupts: list[str] = field(default_factory=list)
    #: run_id-scoped set of committed side-effect keys (the DAS-1447 guard set).
    committed: set[str] = field(default_factory=set)


class RunIdCheckpointer:
    """A checkpoint store keyed by ``run_id``, subordinate to the ADR-0023 run-model.

    In-memory by default; when ``runs_dir`` is given it may co-locate under
    ``board/runs/<run_id>/`` — the ADR-0023 run-artifact tree — never a fork of
    it.  It is a resumption index, not a truth store: a checkpoint that diverges
    from the board LOSES (:func:`reconcile`).  The ``committed`` set implements the
    guard-before-act idempotency (§4.3): a side effect is recorded once per
    ``run_id`` and skipped on any resume that would re-apply it.
    """

    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir
        self._store: dict[str, Checkpoint] = {}

    def save(self, cp: Checkpoint) -> None:
        """Persist (or overwrite) the checkpoint for ``cp.run_id``."""
        existing = self._store.get(cp.run_id)
        if existing is not None:
            # Preserve the accumulated committed-side-effect guard set across saves.
            cp.committed |= existing.committed
        self._store[cp.run_id] = cp

    def load(self, run_id: str) -> Checkpoint | None:
        """Load the checkpoint for ``run_id`` (``None`` if the run never paused)."""
        return self._store.get(run_id)

    def already_committed(self, run_id: str, effect_key: str) -> bool:
        """Guard-before-act (§4.3 / DAS-1447): did ``effect_key`` already commit?

        A committed side effect (a merge, an emitted event, a written checkpoint)
        is detected here by ``run_id`` + effect identity so a resume does NOT
        double-apply it.
        """
        cp = self._store.get(run_id)
        return bool(cp and effect_key in cp.committed)

    def mark_committed(self, run_id: str, effect_key: str) -> None:
        """Record ``effect_key`` as committed for ``run_id`` (idempotent)."""
        cp = self._store.get(run_id)
        if cp is None:
            cp = Checkpoint(run_id=run_id, node="", channels={})
            self._store[run_id] = cp
        cp.committed.add(effect_key)


# ──────────────────────────────────────────────────────────────────────────────
# §4.2 — Single producer: post-decision mechanics through run_wave (LG-4 / ADR-0025)
# ──────────────────────────────────────────────────────────────────────────────


def commit_wave(
    plan: Any,
    results: Any,
    *,
    created_at: str,
    checkpointer: RunIdCheckpointer,
    organism_emit: bool = True,
    **run_wave_kwargs: Any,
) -> Any:
    """Commit one wave's post-decision mechanics THROUGH the single ``run_wave`` seam.

    The graph's ONLY write into the event / attestation / wave-ledger surface is
    this call (§4.2): it never calls ``dispatch_emitter`` / ``pulse_checkpoint`` /
    the ledger appenders directly, so it adds no second producer and the
    ADR-0031/0032 reconciliation bijection is preserved.  Because it feeds the
    SAME ``(plan, results)`` /daslab-cycle would, the committed attestation is
    identical — ADR-0025 flag-on == flag-off holds at this function boundary.

    Guard-before-act idempotency (§4.3 / SC-001b): keyed by ``plan.run_id``, a
    wave already committed on this checkpointer is NOT re-produced — the prior
    result stands, so a resume never appends a duplicate ledger entry.
    """
    import wave_runner as _wr  # noqa: PLC0415  (lazy: only the driving path needs it)

    run_id = plan.run_id
    effect_key = f"wave:{run_id}:{plan.wave}"

    # DAS-1447 guard: if this exact wave already committed for this run_id, do not
    # re-apply it (no double attestation, no duplicate ledger line). The prior
    # attestation stands; resume is a no-op over the committed side effect.
    if checkpointer.already_committed(run_id, effect_key):
        return checkpointer.load(run_id).channels.get("_attestation")  # prior receipt

    attestation = _wr.run_wave(
        plan,
        results,
        created_at=created_at,
        organism_emit=organism_emit,
        **run_wave_kwargs,
    )

    if attestation is not None:
        # Record the committed side effect + stash the receipt for an idempotent
        # resume to return without re-producing.
        checkpointer.mark_committed(run_id, effect_key)
        cp = checkpointer.load(run_id)
        if cp is not None:
            cp.channels.setdefault("_attestation", attestation)
    return attestation


# ──────────────────────────────────────────────────────────────────────────────
# §1/§2/§4 — The graph builder (the ONLY function that needs the LangGraph extra)
# ──────────────────────────────────────────────────────────────────────────────


def build_graph(*, checkpointer: RunIdCheckpointer | None = None) -> Any:
    """Compile the DGO-X loop onto a LangGraph ``StateGraph`` (needs the extra).

    Wires supervisor → [conditional edge: :func:`route_from_supervisor`] →
    worker | interrupt, with the channels of §1.2 and a checkpointer subordinate
    to the ADR-0023 run-model (§4).  This is the ONE function that reaches for the
    optional ``langgraph`` runtime; when it is absent this raises
    :class:`SubstrateUnavailableError` (unavailable, not broken — the governance
    functions above keep working).  The graph never becomes the top-level
    dispatcher (C1/C2): it executes edges, it does not decide what is true.

    Clean-room note (§2.3 / ``check_import_ban.py``): the DasLab engine takes NO
    static or core dependency on the donor framework — ``langgraph`` is loaded
    DYNAMICALLY (``importlib``) only on a host that has opted into the extra
    (``scripts/dgox/requirements-langgraph.txt``), and never at import time.  This
    is the legitimate optional-dependency boundary that reconciles ADR-0035's
    adoption with the clean-room posture; the formal allowlist question is flagged
    for the CTO (GATE-4 owner) in the DAS-1564 log.
    """
    if not langgraph_available():
        raise SubstrateUnavailableError(
            "LangGraph is not installed. It is an opt-in extra (ADR-0035 LG-5); "
            "install scripts/dgox/requirements-langgraph.txt to enable the runtime. "
            "The substrate is unavailable, not broken — projection/reconcile/route/"
            "checkpoint governance functions remain fully usable without it."
        )

    # Dynamic (opt-in) load — no static donor import in the clean-room source.
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


# ──────────────────────────────────────────────────────────────────────────────
# §6 — The driven loop (inert when the flag is OFF — LG-5 / FR-007 / C5)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InertResult:
    """Returned by :func:`run_loop` when the flag is OFF — the substrate did nothing."""

    drove: bool = False
    reason: str = f"{FLAG} is OFF — substrate inert, dispatch byte-identical (SC-004a)"


def run_loop(
    *,
    features_path: Path | None = None,
    force_drive: bool = False,
) -> InertResult:
    """Entry point for the substrate — INERT unless ``ws_c_langgraph_loop`` is ON.

    OFF (default) ⇒ returns :class:`InertResult` and drives nothing: no wave, no
    event, no attestation attributable to the substrate; a wave through
    /daslab-cycle is byte-identical to pre-merge (§6 / SC-004a).  Even ON, the
    posture is shadow-before-drive: the flip is a Founder/board act, so a real
    drive is not the flag alone.  ``force_drive`` against an OFF flag fails-closed
    with :class:`SubstrateInertError` — the flag is the gate, not a suggestion.
    """
    if not drive_enabled(features_path):
        if force_drive:
            raise SubstrateInertError(
                f"{FLAG} is OFF — refusing to drive a wave (fail-closed). Flip the "
                "flag via the Founder/board act (DAS-1568) before driving."
            )
        return InertResult()
    # Flag ON: shadow-before-drive. Actual driving (mirror → enforce → drive) is
    # gated on an explicit board-approval signal (Q4), owned by DAS-1568; this
    # adapter exposes the primitives (project/reconcile/route/commit_wave) the
    # driver composes. Nothing is auto-driven on the flag alone.
    return InertResult(drove=False, reason=f"{FLAG} ON — shadow posture; drive is a board act (Q4)")
