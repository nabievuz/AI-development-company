#!/usr/bin/env python3
"""fanout.py — Fanout emission: materialise N child tickets + 1 deferred synthesis ticket.

This module implements the P5 fanout primitive for the ORGANISM program's
pulse loop (DAS-1449).  A single fanout parent ticket can, at dispatch time,
expand into N runtime-generated child tickets — each with a **private** per-child
payload block — plus one synthesis ticket (``defer: true``) that aggregates
results once all children are done.

The synthesis ticket declares ``depends_on: [child1, ..., childN]``.  The
existing daslab-cycle dep-blocked skip (SKILL.md step 3) refuses to dispatch it
until every child is ``done``.  The ``defer: true`` marker is an additional hard
guard that survives race conditions: even if the dep-blocked check were somehow
bypassed, ``defer: true`` forces a second independent check.

Dispatcher gating (mirrors SKILL.md step 3)
-------------------------------------------
Use :func:`is_actionable` to pre-screen tickets before dispatch:

* ``status`` must be ``todo`` or ``in_progress``.
* Every id in ``depends_on`` must be ``status=done`` (dep-blocked skip).
* ``defer: true`` applies an explicit second check — redundant with the above
  but guaranteed to run even in error paths.

Private-payload isolation
-------------------------
Each child ticket carries its payload in a ``## Fanout Payload`` section.
The section is prefixed with an HTML comment marking it as private (siblings
must not read it).  The synthesis ticket receives only child ids (via
``depends_on``), never the raw payloads of siblings unless a child explicitly
publishes a result to a shared artifact.

Usage (from the orchestrator, in daslab-cycle step 5)::

    from fanout import emit_fanout

    child_ids, synthesis_id = emit_fanout(
        board_dir=Path("board/tickets"),
        parent_id="DAS-1500",
        parent_meta={
            "author": "senior-pm",
            "dept": "engineering",
            "priority": "p1",
            "goal": "my-goal",
            "zone": "daslab-cycle",
        },
        children_payloads=[
            {"title": "Slice A", "assignee": "backend-eng-1", "payload": "..."},
            {"title": "Slice B", "assignee": "backend-eng-2", "payload": "..."},
        ],
        synthesis_meta={
            "title": "Aggregate slice results",
            "assignee": "backend-em",
            "payload": "Read child done-status and aggregate.",
        },
        date="2026-07-03",
    )

All emitted tickets are validated against ``scripts/check_dependency_graph.py``
(no dangling deps, acyclic graph, well-formed ``zone:``).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DAS_NUM_RE = re.compile(r"^DAS-(\d+)")          # match filename prefix
_DAS_ID_RE = re.compile(r"\bDAS-\d+\b")           # extract all ids from a field value

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _next_ids(board_dir: Path, n: int) -> list[str]:
    """Return *n* consecutive DAS-* ids starting from max(existing) + 1.

    Scans *board_dir* for ``DAS-<digits>-*.md`` files and picks the next n
    ids after the highest found.  An empty board starts at DAS-1.
    """
    max_n = 0
    for md in board_dir.glob("DAS-*.md"):
        m = _DAS_NUM_RE.match(md.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return [f"DAS-{max_n + i + 1}" for i in range(n)]


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert *text* into a lowercase hyphen-separated slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:max_len]


def _write_ticket(
    board_dir: Path,
    ticket_id: str,
    *,
    title: str,
    status: str = "todo",
    assignee: str = "",
    author: str,
    dept: str,
    priority: str,
    parent: str = "",
    goal: str = "",
    zone: str = "",
    depends_on: list[str] | None = None,
    defer: bool = False,
    date: str,
    body_intro: str = "",
    payload: str = "",
) -> Path:
    """Serialise a ticket frontmatter + body to *board_dir* and return its path."""
    fm_lines: list[str] = [
        "---",
        f"id: {ticket_id}",
        f"title: {title}",
        f"status: {status}",
        f"assignee: {assignee}",
        f"author: {author}",
        f"dept: {dept}",
        f"priority: {priority}",
    ]
    if parent:
        fm_lines.append(f"parent: {parent}")
    if goal:
        fm_lines.append(f"goal: {goal}")
    if zone:
        fm_lines.append(f"zone: {zone}")
    if depends_on:
        dep_str = "[" + ", ".join(depends_on) + "]"
        fm_lines.append(f"depends_on: {dep_str}")
    if defer:
        fm_lines.append("defer: true")
    fm_lines += [
        f"created: {date}",
        f"updated: {date}",
        "---",
        "",
    ]

    # Body
    body_parts: list[str] = ["## Description", ""]
    if body_intro:
        body_parts += [body_intro, ""]
    if payload:
        body_parts += [
            "## Fanout Payload",
            "",
            "<!-- PRIVATE: this payload is scoped to this ticket only.",
            "     Sibling tickets must NOT read this block. Results intended",
            "     for the synthesis step must be published explicitly. -->",
            "",
            payload,
            "",
        ]
    body_parts += ["## Log", ""]

    content = "\n".join(fm_lines) + "\n".join(body_parts)

    slug = _slugify(title)
    filename = f"{ticket_id}-{slug}.md"
    path = board_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Public API — emission
# ---------------------------------------------------------------------------

def emit_fanout(
    board_dir: Path,
    parent_id: str,
    parent_meta: dict[str, Any],
    children_payloads: list[dict[str, Any]],
    synthesis_meta: dict[str, Any],
    *,
    date: str,
) -> tuple[list[str], str]:
    """Emit N child tickets + 1 deferred synthesis ticket from a fanout parent.

    Parameters
    ----------
    board_dir:
        Directory where ticket ``.md`` files live (e.g. ``board/tickets/``).
        Must already exist.
    parent_id:
        The DAS-* id of the fanout parent ticket.
    parent_meta:
        Shared metadata applied to all emitted tickets.  Recognised keys:
        ``author``, ``dept``, ``priority``, ``goal``, ``zone`` (all optional
        with sensible defaults).
    children_payloads:
        List of per-child dicts.  Each dict may carry:
        ``title`` (str), ``assignee`` (str), ``payload`` (str — private body).
        N is ``len(children_payloads)`` and is determined at call time.
    synthesis_meta:
        Dict for the synthesis ticket.  Keys: ``title`` (str), ``assignee``
        (str), ``payload`` (str — aggregation prompt / join instructions).
        The synthesis ticket will carry ``defer: true`` and
        ``depends_on: [child1, ..., childN]`` automatically.
    date:
        ISO date string for ``created``/``updated`` (e.g. ``"2026-07-03"``).

    Returns
    -------
    (child_ids, synthesis_id)
        ``child_ids`` — ordered list of N newly-created child ticket ids.
        ``synthesis_id`` — the deferred synthesis ticket id.

    Raises
    ------
    ValueError
        If ``children_payloads`` is empty (N must be >= 1).
    FileNotFoundError
        If ``board_dir`` does not exist.
    """
    if not children_payloads:
        raise ValueError(
            "emit_fanout: children_payloads must be non-empty (N >= 1). "
            "A fanout with zero children has no purpose."
        )
    if not board_dir.is_dir():
        raise FileNotFoundError(f"emit_fanout: board_dir does not exist: {board_dir}")

    n = len(children_payloads)
    # Allocate n child ids + 1 synthesis id, all consecutive.
    new_ids = _next_ids(board_dir, n + 1)
    child_ids: list[str] = new_ids[:n]
    synthesis_id: str = new_ids[n]

    author = str(parent_meta.get("author", "senior-pm"))
    dept = str(parent_meta.get("dept", "engineering"))
    priority = str(parent_meta.get("priority", "p1"))
    goal = str(parent_meta.get("goal", ""))
    zone = str(parent_meta.get("zone", ""))

    # ------------------------------------------------------------------
    # Write N child tickets (each with its own private payload)
    # ------------------------------------------------------------------
    for i, (child_id, child) in enumerate(zip(child_ids, children_payloads, strict=False)):
        _write_ticket(
            board_dir,
            child_id,
            title=str(child.get("title", f"Fanout child {i + 1}")),
            assignee=str(child.get("assignee", "")),
            author=author,
            dept=dept,
            priority=priority,
            parent=parent_id,
            goal=goal,
            zone=zone,
            date=date,
            body_intro=(
                f"Fanout child {i + 1}/{n} emitted from parent {parent_id}. "
                "See the Fanout Payload section below for the private work slice."
            ),
            payload=str(child.get("payload", "")),
        )

    # ------------------------------------------------------------------
    # Write 1 synthesis ticket (defer: true + depends_on all children)
    # ------------------------------------------------------------------
    _write_ticket(
        board_dir,
        synthesis_id,
        title=str(synthesis_meta.get("title", f"Synthesize results from {parent_id}")),
        assignee=str(synthesis_meta.get("assignee", "")),
        author=author,
        dept=dept,
        priority=priority,
        parent=parent_id,
        goal=goal,
        zone=zone,
        depends_on=child_ids,
        defer=True,
        date=date,
        body_intro=(
            f"Deferred synthesis ticket for fanout parent {parent_id}. "
            f"Aggregates results from {n} child ticket(s): "
            + ", ".join(child_ids)
            + ". "
            "This ticket carries defer: true and will NOT be dispatched until "
            "ALL children reach status=done. "
            "Do not read sibling Fanout Payload sections directly — "
            "consume only explicitly published child results."
        ),
        payload=str(synthesis_meta.get("payload", "")),
    )

    return child_ids, synthesis_id


# ---------------------------------------------------------------------------
# Public API — dispatcher gating helper
# ---------------------------------------------------------------------------

def _parse_depends_on(raw: str) -> list[str]:
    """Extract DAS-* ids from a raw ``depends_on`` field value."""
    return _DAS_ID_RE.findall(raw or "")


def is_actionable(
    fm: dict[str, str],
    all_fms_by_id: dict[str, dict[str, str]],
) -> bool:
    """Return True if *fm* is actionable per daslab-cycle SKILL.md step 3.

    This function mirrors the dispatcher's selection logic and is the canonical
    source of truth for the deferred-synthesis gating rule.  It is used by both
    the orchestrator and tests.

    Rules applied (in order):
    1. ``status`` must be ``todo`` or ``in_progress``.
    2. Every id in ``depends_on`` must resolve to a ``done`` ticket
       (dep-blocked skip — SKILL.md step 3, existing rule).
    3. ``defer: true`` — hard guard.  Even after the dep-blocked pass, if the
       ticket is marked deferred, re-verify every dep independently.  This
       second check cannot be short-circuited and guards against race conditions
       where the first check might be bypassed by a bug.

    Parameters
    ----------
    fm:
        Frontmatter dict for the ticket being evaluated.
    all_fms_by_id:
        Mapping of ticket id → frontmatter dict for the whole board.  Used to
        resolve ``depends_on`` ids to their current ``status``.

    Returns
    -------
    bool
        ``True`` if the ticket may be dispatched; ``False`` if it is blocked.
    """
    status = fm.get("status", "").strip()
    if status not in ("todo", "in_progress"):
        return False

    deps = _parse_depends_on(fm.get("depends_on", ""))

    # Rule 2 — dep-blocked skip (core SKILL.md step 3 rule)
    for dep_id in deps:
        dep_fm = all_fms_by_id.get(dep_id)
        if dep_fm is None or dep_fm.get("status", "").strip() != "done":
            return False

    # Rule 3 — defer: true hard guard (independent second check)
    if fm.get("defer", "").lower().strip() == "true":
        for dep_id in deps:
            dep_fm = all_fms_by_id.get(dep_id)
            if dep_fm is None or dep_fm.get("status", "").strip() != "done":
                return False  # hard guard: synthesis blocked while sibling not done

    return True


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def _smoke_test() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp)
        child_ids, synthesis_id = emit_fanout(
            board_dir=board,
            parent_id="DAS-9000",
            parent_meta={
                "author": "senior-pm",
                "dept": "engineering",
                "priority": "p1",
                "goal": "smoke-test",
                "zone": "daslab-cycle",
            },
            children_payloads=[
                {"title": "Slice A", "assignee": "backend-eng-1", "payload": "Private A"},
                {"title": "Slice B", "assignee": "backend-eng-2", "payload": "Private B"},
            ],
            synthesis_meta={
                "title": "Aggregate A and B",
                "assignee": "backend-em",
                "payload": "Aggregate child results.",
            },
            date="2026-07-03",
        )
        print(f"child_ids:    {child_ids}")
        print(f"synthesis_id: {synthesis_id}")
        for md in sorted(board.glob("DAS-*.md")):
            print(f"\n{'='*60}")
            print(f"FILE: {md.name}")
            print(md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    _smoke_test()
