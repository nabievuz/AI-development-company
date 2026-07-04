#!/usr/bin/env python3
"""board_metrics.py — throughput & effectiveness KPIs for the DasLab board.

Reads every ``DAS-*.md`` under ``board/tickets/`` and (optionally) the archive,
and reports the org's operating metrics:

- **Status distribution** — how many tickets in each state.
- **Throughput** — count of ``done`` tickets.
- **Cycle time** — mean/median days between ``created`` and ``updated`` for done
  tickets (a proxy for lead time).
- **Gate pass-rate** — share of epics (no ``parent``) that are ``done``.
- **Blocked / rework** — count of ``blocked`` tickets (work the org could not
  self-serve, e.g. external dependencies).

It measures the engine, not a product, so it works for any project on the board.

    python3 scripts/board_metrics.py            # table over board/tickets/ + archive
    python3 scripts/board_metrics.py --json      # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

from _paths import ROOT

_STATUSES = ("backlog", "todo", "in_progress", "blocked", "in_review", "done")
_FM_RE = re.compile(r"^---\n(.*?)\n---", re.S)


def _frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.search(text)
    fm: dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
    return fm


def _ticket_dirs(root: Path, include_archive: bool) -> list[Path]:
    dirs = [root / "board" / "tickets"]
    archive = root / "board" / "archive"
    if include_archive and archive.is_dir():
        dirs.append(archive)
    return [d for d in dirs if d.is_dir()]


def collect(root: Path, include_archive: bool = True) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for d in _ticket_dirs(root, include_archive):
        for f in d.rglob("DAS-*.md"):
            out.append(_frontmatter(f.read_text(encoding="utf-8", errors="ignore")))
    return out


def _parse_date(s: str) -> date | None:
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def metrics(tickets: list[dict[str, str]]) -> dict[str, object]:
    by_status = dict.fromkeys(_STATUSES, 0)
    for t in tickets:
        st = t.get("status", "")
        if st in by_status:
            by_status[st] += 1

    cycle_days: list[int] = []
    for t in tickets:
        if t.get("status") == "done":
            c, u = _parse_date(t.get("created", "")), _parse_date(t.get("updated", ""))
            if c and u and u >= c:
                cycle_days.append((u - c).days)

    epics = [t for t in tickets if not t.get("parent")]
    epics_done = [t for t in epics if t.get("status") == "done"]

    return {
        "total": len(tickets),
        "by_status": by_status,
        "throughput_done": by_status["done"],
        "cycle_time_days": {
            "mean": round(statistics.mean(cycle_days), 1) if cycle_days else None,
            "median": statistics.median(cycle_days) if cycle_days else None,
            "n": len(cycle_days),
        },
        "gate_pass_rate": round(len(epics_done) / len(epics), 3) if epics else None,
        "epics": {"total": len(epics), "done": len(epics_done)},
        "blocked": by_status["blocked"],
    }


def _print_table(m: dict[str, object]) -> None:
    print(f"DasLab board metrics — {m['total']} tickets")
    print("  status:")
    for s, n in m["by_status"].items():  # type: ignore[union-attr]
        print(f"    {s:<12} {n}")
    ct = m["cycle_time_days"]  # type: ignore[index]
    print(f"  throughput (done): {m['throughput_done']}")
    print(f"  cycle time (days): mean={ct['mean']} median={ct['median']} n={ct['n']}")
    print(f"  gate pass-rate:    {m['gate_pass_rate']} ({m['epics']['done']}/{m['epics']['total']} epics)")
    print(f"  blocked:           {m['blocked']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--no-archive", action="store_true", help="exclude board/archive/")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()

    tickets = collect(root, include_archive=not args.no_archive)
    m = metrics(tickets)
    if args.json:
        json.dump(m, sys.stdout, indent=2)
        print()
    else:
        _print_table(m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
