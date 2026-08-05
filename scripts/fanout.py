#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_DAS_NUM_RE = re.compile(r"^DAS-(\d+)")
_DAS_ID_RE = re.compile(r"\bDAS-\d+\b")

REPO_ROOT = Path(__file__).resolve().parent.parent


def _next_ids(board_dir: Path, n: int) -> list[str]:
    max_n = 0
    for md in board_dir.glob("DAS-*.md"):
        m = _DAS_NUM_RE.match(md.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return [f"DAS-{max_n + i + 1}" for i in range(n)]


def _slugify(text: str, max_len: int = 40) -> str:
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


def emit_fanout(
    board_dir: Path,
    parent_id: str,
    parent_meta: dict[str, Any],
    children_payloads: list[dict[str, Any]],
    synthesis_meta: dict[str, Any],
    *,
    date: str,
) -> tuple[list[str], str]:
    if not children_payloads:
        raise ValueError(
            "emit_fanout: children_payloads must be non-empty (N >= 1). "
            "A fanout with zero children has no purpose."
        )
    if not board_dir.is_dir():
        raise FileNotFoundError(f"emit_fanout: board_dir does not exist: {board_dir}")

    n = len(children_payloads)

    new_ids = _next_ids(board_dir, n + 1)
    child_ids: list[str] = new_ids[:n]
    synthesis_id: str = new_ids[n]

    author = str(parent_meta.get("author", "senior-pm"))
    dept = str(parent_meta.get("dept", "engineering"))
    priority = str(parent_meta.get("priority", "p1"))
    goal = str(parent_meta.get("goal", ""))
    zone = str(parent_meta.get("zone", ""))


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


def _parse_depends_on(raw: str) -> list[str]:
    return _DAS_ID_RE.findall(raw or "")


def is_actionable(
    fm: dict[str, str],
    all_fms_by_id: dict[str, dict[str, str]],
) -> bool:
    status = fm.get("status", "").strip()
    if status not in ("todo", "in_progress"):
        return False

    deps = _parse_depends_on(fm.get("depends_on", ""))


    for dep_id in deps:
        dep_fm = all_fms_by_id.get(dep_id)
        if dep_fm is None or dep_fm.get("status", "").strip() != "done":
            return False


    if fm.get("defer", "").lower().strip() == "true":
        for dep_id in deps:
            dep_fm = all_fms_by_id.get(dep_id)
            if dep_fm is None or dep_fm.get("status", "").strip() != "done":
                return False

    return True


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
