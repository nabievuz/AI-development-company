"""dgox/board_adapter.py — DGO-X Phase-1 board adapter.

Reads ``board/tickets/*.md``, parses YAML frontmatter, and normalises each
ticket into a ``GraphState`` via ``state.apply_group``.

Design contract (ADR 0011 §3):
- ONE-WAY mirror: ``board/tickets/*.md`` stays canonical operator-facing truth.
  This adapter NEVER writes back to ticket files in Phase 1.
- The adapter writes ONLY the Identity group (ticket_id, goal, parent,
  project, dept) — sole-writer rule per ADR 0011 §1.
- On board ↔ mirror divergence: emits a ``mirror_divergence`` event via the
  EventStore and REBUILDS the mirror from the board.  Board wins, never the
  reverse.  The ``mirror_divergence`` event_type is already in events.py's
  ``_VALID_EVENT_TYPES`` (no change to events.py required).
- Normalisation is pure: same board + same event log ⇒ same mirror
  (deterministic, replayable).

Public API:
    ``parse_ticket(path)``        → ``dict[str, str | None]`` of frontmatter
    ``normalize_ticket(fm)``      → ``GraphState``  (Identity group only)
    ``build_mirror(board_dir)``   → ``dict[str, GraphState]`` {ticket_id: state}
    ``check_divergence(prior, current)`` → list of diverged ticket_ids

Shadow mode (ADR 0011 §4): this module is a STANDALONE LIBRARY wired into
nothing yet.  It does not touch /daslab-cycle, dispatch, or routing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating root — same pattern as state.py and events.py
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # scripts/dgox/../ = scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import repo_root  # noqa: E402

_ROOT = repo_root()

# ---------------------------------------------------------------------------
# Lazy imports of sibling modules (keep import-cycle-free)
# ---------------------------------------------------------------------------
# These imports live here (not at module top) so the module can be imported
# even when scripts/ hasn't been patched onto sys.path yet by a test setup
# script.  The actual import happens on first use inside each function.

def _get_apply_group_and_graph_state():  # noqa: ANN201
    """Return (apply_group, GraphState) — imported once."""
    from dgox.state import GraphState, apply_group  # noqa: PLC0415
    return apply_group, GraphState


def _get_event_store():  # noqa: ANN201
    """Return a live EventStore pointed at the canonical store path."""
    from dgox.events import EventStore, utcnow  # noqa: PLC0415
    return EventStore, utcnow


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

_FM_DELIM = re.compile(r"^---\s*$", re.MULTILINE)


def parse_ticket(path: Path | str) -> dict[str, str | None]:
    """Parse the YAML frontmatter of a ticket file.

    Returns a flat ``dict`` whose keys are the frontmatter field names and
    whose values are stripped strings (or ``None`` for blank values).  Fields
    outside frontmatter are ignored; only the first ``---``...``---`` block is
    parsed.

    The parser is intentionally minimal — it handles the simple ``key: value``
    format used in DasLab tickets and does NOT require PyYAML (pure stdlib).

    Raises
    ------
    ValueError
        If the file has no frontmatter block.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    parts = _FM_DELIM.split(text, maxsplit=2)
    # parts[0] = text before first ---, parts[1] = frontmatter body, parts[2] = rest
    if len(parts) < 3:
        raise ValueError(
            f"Ticket file {path!r} has no frontmatter block (expected ---...---)"
        )

    fm_body = parts[1]
    result: dict[str, str | None] = {}
    for line in fm_body.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw_val = line.partition(":")
        key = key.strip()
        val = raw_val.strip()
        # Strip surrounding quotes if present (e.g. title: "Foo bar")
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = val[1:-1].strip()
        result[key] = val if val else None
    return result


# ---------------------------------------------------------------------------
# Normalise frontmatter → GraphState (Identity group only)
# ---------------------------------------------------------------------------

def normalize_ticket(fm: dict[str, Any]) -> Any:
    """Project ticket frontmatter into a GraphState with the Identity group set.

    Parameters
    ----------
    fm:
        Frontmatter dict as returned by ``parse_ticket``.

    Returns
    -------
    GraphState
        A ``GraphState`` with its ``identity`` group populated from ``fm``.
        The ``_author`` internal field is set for self-route invariant checks.
        All other groups remain at their zero/default values.

    Raises
    ------
    ValueError
        If ``fm`` contains no ``id`` field (not a valid ticket frontmatter).
    StateInvariantError
        If the identity write violates an invariant (should never happen from
        well-formed frontmatter, but propagates for safety).
    """
    apply_group, GraphState = _get_apply_group_and_graph_state()

    ticket_id = fm.get("id") or ""
    if not ticket_id:
        raise ValueError(
            f"Frontmatter has no 'id' field — cannot construct GraphState: {fm!r}"
        )

    state: Any = GraphState(ticket_id=ticket_id)

    # Set author for self-route invariant checking (not an identity field,
    # stored internally via set_author).
    author = fm.get("author")
    if author:
        state.set_author(author)

    # Identity group fields (ADR 0011 §1 table — board adapter is sole writer).
    # Strip whitespace and coerce blank strings to None so normalize is pure.
    def _blank_to_none(v: Any) -> str | None:
        return v.strip() if isinstance(v, str) and v.strip() else None

    identity_updates: dict[str, Any] = {
        "ticket_id": ticket_id,
        "goal": _blank_to_none(fm.get("goal")),
        "parent": _blank_to_none(fm.get("parent")),
        "project": _blank_to_none(fm.get("project")),
        "dept": _blank_to_none(fm.get("dept")),
    }
    apply_group(state, "identity", identity_updates)

    return state


# ---------------------------------------------------------------------------
# Divergence check
# ---------------------------------------------------------------------------

def check_divergence(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    """Compare two mirrors and return ticket_ids that diverged.

    A divergence is defined as: a ticket present in *prior* whose Identity
    group differs from *current*, OR a ticket present in one but not the other.

    Parameters
    ----------
    prior:
        Previous mirror: ``{ticket_id: GraphState}``.
    current:
        Current mirror: ``{ticket_id: GraphState}``.

    Returns
    -------
    list[str]
        Sorted list of ticket_ids whose ``GraphState.identity`` fields differ
        between *prior* and *current*, or that are in one but not the other.
    """
    _, GraphState = _get_apply_group_and_graph_state()

    all_ids = set(prior) | set(current)
    diverged: list[str] = []

    for tid in all_ids:
        if tid not in prior or tid not in current:
            diverged.append(tid)
            continue
        p = prior[tid]
        c = current[tid]
        # Compare Identity fields only — that is all the adapter writes.
        if (
            p.ticket_id != c.ticket_id
            or p.goal != c.goal
            or p.parent != c.parent
            or p.project != c.project
            or p.dept != c.dept
        ):
            diverged.append(tid)

    return sorted(diverged)


# ---------------------------------------------------------------------------
# Mirror builder
# ---------------------------------------------------------------------------

#: Glob pattern that matches DasLab ticket files.
_TICKET_GLOB = "DAS-*.md"


def build_mirror(
    board_dir: Path | str | None = None,
    *,
    store_path: Path | str | None = None,
    prior_mirror: dict[str, Any] | None = None,
    emit_events: bool = True,
) -> dict[str, Any]:
    """Read all ``board/tickets/DAS-*.md`` files and return a complete mirror.

    For each ticket the file is parsed, normalised into a ``GraphState`` with
    the Identity group set, and stored in the returned dict keyed by ticket_id.

    Divergence handling (ADR 0011 §3):
        If *prior_mirror* is supplied, the new mirror is compared against it.
        Any diverged tickets cause a ``mirror_divergence`` event to be emitted
        (when *emit_events* is ``True``) and the mirror is REBUILT from the
        board — board wins, never the reverse.

    Parameters
    ----------
    board_dir:
        Directory containing ticket files.  Defaults to
        ``<repo_root>/board/tickets/``.
    store_path:
        Path to the JSONL event store.  ``None`` uses the default
        ``board/.events.jsonl`` path from ``EventStore``.
    prior_mirror:
        Previously computed mirror; if given, divergence checking is performed.
    emit_events:
        If ``False``, no events are emitted (useful for testing divergence
        detection without writing to the store).

    Returns
    -------
    dict[str, GraphState]
        ``{ticket_id: GraphState}`` for every ticket on the board.  Tickets
        that fail to parse are SKIPPED (a parse error cannot be a mirror
        truth) — this is the Phase-1 shadow policy (observe, don't block).

    Notes
    -----
    - NEVER writes to ticket files (ONE-WAY contract, ADR 0011 §3.3).
    - The adapter writes ONLY the Identity group per GraphState.
    - On divergence: emit event + rebuild (board wins).
    """
    tickets_dir = Path(board_dir) if board_dir is not None else _ROOT / "board" / "tickets"

    current_mirror: dict[str, Any] = {}

    for ticket_path in sorted(tickets_dir.glob(_TICKET_GLOB)):
        try:
            fm = parse_ticket(ticket_path)
            state = normalize_ticket(fm)
            current_mirror[state.ticket_id] = state
        except Exception:  # noqa: BLE001
            # Shadow mode: parse failures are skipped, not fatal.
            # In production this would emit a state_violation event;
            # Phase-1 policy is to observe and not block.
            continue

    # ── Divergence check ────────────────────────────────────────────────────
    if prior_mirror is not None:
        diverged_ids = check_divergence(prior_mirror, current_mirror)
        if diverged_ids and emit_events:
            _emit_mirror_divergence_events(diverged_ids, store_path=store_path)

    # Board always wins: return the freshly built mirror from the board.
    # (The rebuild IS the current_mirror — we build from the board on every
    # call, so there is no separate "rebuild" step needed.)
    return current_mirror


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

def _emit_mirror_divergence_events(
    diverged_ids: list[str],
    *,
    store_path: Path | str | None = None,
) -> None:
    """Emit one ``mirror_divergence`` event per diverged ticket.

    The ``mirror_divergence`` event_type is already in events.py's
    ``_VALID_EVENT_TYPES`` — no change to events.py is required.
    """
    EventStore, utcnow = _get_event_store()

    kwargs: dict[str, Any] = {}
    if store_path is not None:
        kwargs["path"] = store_path

    store = EventStore(**kwargs)
    ts = utcnow()

    for ticket_id in diverged_ids:
        event: dict[str, Any] = {
            "event_type": "mirror_divergence",
            "ticket_id": ticket_id,
            "created_at": ts,
            "reason": "board ↔ mirror divergence detected; mirror rebuilt from board (board wins)",
        }
        store.append(event)
