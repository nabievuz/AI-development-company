
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import repo_root

_ROOT = repo_root()


def _get_apply_group_and_graph_state():
    from dgox.state import GraphState, apply_group
    return apply_group, GraphState


def _get_event_store():
    from dgox.events import EventStore, utcnow
    return EventStore, utcnow


_FM_DELIM = re.compile(r"^---\s*$", re.MULTILINE)


def parse_ticket(path: Path | str) -> dict[str, str | None]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    parts = _FM_DELIM.split(text, maxsplit=2)

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

        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = val[1:-1].strip()
        result[key] = val if val else None
    return result


def normalize_ticket(fm: dict[str, Any]) -> Any:
    apply_group, GraphState = _get_apply_group_and_graph_state()

    ticket_id = fm.get("id") or ""
    if not ticket_id:
        raise ValueError(
            f"Frontmatter has no 'id' field — cannot construct GraphState: {fm!r}"
        )

    state: Any = GraphState(ticket_id=ticket_id)


    author = fm.get("author")
    if author:
        state.set_author(author)


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


def check_divergence(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    _, GraphState = _get_apply_group_and_graph_state()

    all_ids = set(prior) | set(current)
    diverged: list[str] = []

    for tid in all_ids:
        if tid not in prior or tid not in current:
            diverged.append(tid)
            continue
        p = prior[tid]
        c = current[tid]

        if (
            p.ticket_id != c.ticket_id
            or p.goal != c.goal
            or p.parent != c.parent
            or p.project != c.project
            or p.dept != c.dept
        ):
            diverged.append(tid)

    return sorted(diverged)


_TICKET_GLOB = "DAS-*.md"


def build_mirror(
    board_dir: Path | str | None = None,
    *,
    store_path: Path | str | None = None,
    prior_mirror: dict[str, Any] | None = None,
    emit_events: bool = True,
) -> dict[str, Any]:
    tickets_dir = Path(board_dir) if board_dir is not None else _ROOT / "board" / "tickets"

    current_mirror: dict[str, Any] = {}

    for ticket_path in sorted(tickets_dir.glob(_TICKET_GLOB)):
        try:
            fm = parse_ticket(ticket_path)
            state = normalize_ticket(fm)
            current_mirror[state.ticket_id] = state
        except Exception:


            continue


    if prior_mirror is not None:
        diverged_ids = check_divergence(prior_mirror, current_mirror)
        if diverged_ids and emit_events:
            _emit_mirror_divergence_events(diverged_ids, store_path=store_path)


    return current_mirror


def _emit_mirror_divergence_events(
    diverged_ids: list[str],
    *,
    store_path: Path | str | None = None,
) -> None:
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
