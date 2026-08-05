#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD = REPO_ROOT / "board" / "tickets"
DAS_RE = re.compile(r"\bDAS-\d+\b")


def _list_field(text: str, key: str) -> list[str]:
    raw = _fm_field(text, key)
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    names: list[str] = []
    for part in raw.split(","):
        cleaned = part.strip().strip('"').strip("'").strip()
        if cleaned:
            names.append(cleaned)
    return names


def _fm_field(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    if end is None:
        return None
    for line in lines[1:end]:
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def _load(
    board_dir: Path,
) -> tuple[
    dict[str, list[str]],
    dict[str, str | None],
    dict[str, str],
    dict[str, bool],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, str],
]:
    deps: dict[str, list[str]] = {}
    zones: dict[str, str | None] = {}
    files: dict[str, str] = {}
    defers: dict[str, bool] = {}
    produces_by_id: dict[str, list[str]] = {}
    consumes_by_id: dict[str, list[str]] = {}
    goal_by_id: dict[str, str] = {}
    for md in sorted(board_dir.glob("DAS-*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        tid = (_fm_field(text, "id") or md.name.split("-t.md")[0]).strip()
        dep_raw = _fm_field(text, "depends_on")
        deps[tid] = DAS_RE.findall(dep_raw) if dep_raw else []
        zone_raw = _fm_field(text, "zone")
        zones[tid] = None if zone_raw is None else zone_raw.strip().strip('"').strip("'")
        defer_raw = _fm_field(text, "defer")
        defers[tid] = (defer_raw or "").lower().strip() == "true"
        files[tid] = md.name
        produces_by_id[tid] = _list_field(text, "produces")
        consumes_by_id[tid] = _list_field(text, "consumes")
        goal_raw = _fm_field(text, "goal")
        goal_by_id[tid] = (goal_raw or "").strip()
    return deps, zones, files, defers, produces_by_id, consumes_by_id, goal_by_id


def _find_cycle(deps: dict[str, list[str]]) -> list[str] | None:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(deps, WHITE)

    def visit(node: str, path: list[str]) -> list[str] | None:
        colour[node] = GREY
        path.append(node)
        for nxt in deps.get(node, []):
            if nxt not in colour:
                continue
            if colour[nxt] == GREY:
                return path[path.index(nxt):] + [nxt]
            if colour[nxt] == WHITE:
                found = visit(nxt, path)
                if found:
                    return found
        colour[node] = BLACK
        path.pop()
        return None

    for n in deps:
        if colour[n] == WHITE:
            found = visit(n, [])
            if found:
                return found
    return None


def scan(board_dir: Path) -> list[tuple[str, str]]:
    deps, zones, files, defers, produces_by_id, consumes_by_id, goal_by_id = _load(board_dir)
    all_ids = set(deps)
    violations: list[tuple[str, str]] = []


    for tid, dep_list in deps.items():
        for d in dep_list:
            if d not in all_ids:
                violations.append((files[tid], f"depends_on {d} — no such ticket on the board"))

    for tid, zone in zones.items():
        if zone is not None and zone == "":
            violations.append((files[tid], "zone: is present but empty"))


    for tid, is_deferred in defers.items():
        if is_deferred and not deps.get(tid, []):
            violations.append(
                (files[tid], "defer: true but depends_on is empty — "
                 "deferred ticket can never become actionable")
            )

    cycle = _find_cycle(deps)
    if cycle:
        violations.append(("dependency-graph", "cycle: " + " → ".join(cycle)))


    all_produced: set[str] = set()
    for artifacts in produces_by_id.values():
        all_produced.update(artifacts)

    for tid, consumed in consumes_by_id.items():
        for artifact in consumed:
            if artifact not in all_produced:
                violations.append((
                    files[tid],
                    f"consumes '{artifact}' but no ticket on the board produces it "
                    f"— add a ticket with produces: {artifact}",
                ))


    goals_with_pc: set[str] = set()
    for tid, artifacts in produces_by_id.items():
        if artifacts:
            g = goal_by_id.get(tid, "")
            if g:
                goals_with_pc.add(g)
    for tid, artifacts in consumes_by_id.items():
        if artifacts:
            g = goal_by_id.get(tid, "")
            if g:
                goals_with_pc.add(g)

    if goals_with_pc:

        by_goal: dict[str, list[str]] = {}
        for tid, goal in goal_by_id.items():
            if goal in goals_with_pc:
                by_goal.setdefault(goal, []).append(tid)

        for goal, members in by_goal.items():
            if len(members) < 2:
                continue


            member_set = set(members)
            adj: dict[str, set[str]] = {tid: set() for tid in members}
            for tid in members:
                for dep in deps.get(tid, []):
                    if dep in member_set:
                        adj[tid].add(dep)
                        adj[dep].add(tid)


            unvisited = set(members)
            components: list[set[str]] = []
            while unvisited:
                start = next(iter(unvisited))
                component: set[str] = set()
                queue = [start]
                while queue:
                    node = queue.pop()
                    if node in component:
                        continue
                    component.add(node)
                    for neighbor in adj[node]:
                        if neighbor not in component:
                            queue.append(neighbor)
                components.append(component)
                unvisited -= component

            if len(components) <= 1:
                continue


            pc_tickets = {
                tid for tid in members
                if produces_by_id.get(tid) or consumes_by_id.get(tid)
            }
            pc_components = [c for c in components if c & pc_tickets]
            if len(pc_components) <= 1:
                continue

            sorted_comps = sorted(
                (sorted(c) for c in pc_components), key=lambda x: x[0]
            )
            main_comp = sorted_comps[0]
            orphans = sorted_comps[1:]
            orphan_strs = ["{" + ", ".join(c) + "}" for c in orphans]
            violations.append((
                "dependency-graph",
                f"goal '{goal}': dependency graph is disconnected among "
                f"produces/consumes tickets — orphaned component(s): "
                f"{', '.join(orphan_strs)} "
                f"(add depends_on edges to connect to {main_comp})",
            ))

    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=str(DEFAULT_BOARD))
    args = ap.parse_args(argv)

    board_dir = Path(args.board)
    if not board_dir.is_dir():
        sys.stderr.write(f"ERROR: board dir not found: {board_dir}\n")
        return 2

    violations = scan(board_dir)
    if violations:
        sys.stderr.write("FAIL: ticket dependency-graph violations (ADR-0016):\n")
        for who, reason in violations:
            sys.stderr.write(f"  - {who}: {reason}\n")
        sys.stderr.write(f"\n{len(violations)} violation(s).\n")
        return 1

    n_with_deps = sum(1 for d in _load(board_dir)[0].values() if d)
    print(f"OK: dependency graph acyclic, no dangling deps ({n_with_deps} ticket(s) declare depends_on).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
