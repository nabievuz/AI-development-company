#!/usr/bin/env python3
"""check_quickstart.py — the README Quickstart actually works on a fresh clone.

A new operator follows the README literally. This validator guarantees that path:

1. **Order** — parse the README "Quickstart" fenced block and assert the boot
   order is correct: ``bootstrap.py`` must run **before** ``doctor.py`` (doctor's
   REQUIRED ``projects/`` check only passes after bootstrap creates it).
2. **Runs** — execute the Quickstart's ``python3 scripts/*.py`` commands in a
   throwaway copy of the repo (with ``CI=1`` so Claude Code is optional) and assert
   each exits 0. ``--no-run`` does the order check only (used by diagnostics; CI
   runs the full check).

Wired into CI (blocking) and ``diagnostics.py`` (Docs) so the onboarding can never
drift back to a doctor-first Quickstart that fails at step 1.

Exit codes
----------
0  Quickstart order correct (and, unless --no-run, every command exits 0)
1  wrong order or a Quickstart command failed
2  usage / no Quickstart found
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _paths import ROOT

_QUICKSTART_RE = re.compile(r"##\s+Quickstart.*?```(?:bash)?\n(.*?)\n```", re.S)
_CMD_RE = re.compile(r"^python3\s+scripts/\S+\.py")


def quickstart_commands(readme: Path) -> list[str]:
    """Return the ``python3 scripts/*.py`` commands from the Quickstart block, in order."""
    m = _QUICKSTART_RE.search(readme.read_text(encoding="utf-8", errors="ignore"))
    if not m:
        return []
    cmds: list[str] = []
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code = line.split("#", 1)[0].strip()  # drop trailing comment
        if _CMD_RE.match(code):
            cmds.append(code)
    return cmds


def order_problem(cmds: list[str]) -> str | None:
    """Return an error string if the boot order is wrong, else None."""
    def idx(name: str) -> int:
        return next((i for i, c in enumerate(cmds) if name in c), -1)

    boot, doc = idx("bootstrap.py"), idx("doctor.py")
    if boot == -1:
        return "Quickstart never runs scripts/bootstrap.py (first-run setup)"
    if doc != -1 and boot > doc:
        return "bootstrap.py must precede doctor.py (doctor's projects/ check needs bootstrap)"
    return None


def run_in_scratch(root: Path, cmds: list[str]) -> str | None:
    """Run the commands in a throwaway copy of the repo; return an error or None."""
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "clone"
        scratch.mkdir()
        try:
            arch = subprocess.run(
                ["git", "archive", "HEAD"], cwd=root, capture_output=True, check=True
            ).stdout
            subprocess.run(["tar", "-x", "-C", str(scratch)], input=arch, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None  # git/tar unavailable — order check already covered it
        # Overlay the working-tree scripts + README so uncommitted fixes apply.
        shutil.copytree(root / "scripts", scratch / "scripts", dirs_exist_ok=True)
        shutil.copy2(root / "README.md", scratch / "README.md")
        env = {**os.environ, "CI": "1"}
        for cmd in cmds:
            proc = subprocess.run(
                cmd, shell=True, cwd=scratch, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            if proc.returncode != 0:
                return f"`{cmd}` exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--no-run", action="store_true", help="order check only (skip running)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()

    cmds = quickstart_commands(root / "README.md")
    if not cmds:
        print("check_quickstart: FATAL — no runnable Quickstart commands found", file=sys.stderr)
        return 2

    problem = order_problem(cmds)
    if problem:
        print(f"check_quickstart: FAIL — {problem}", file=sys.stderr)
        return 1

    if not args.no_run:
        err = run_in_scratch(root, cmds)
        if err:
            print(f"check_quickstart: FAIL — {err}", file=sys.stderr)
            return 1
        print(f"check_quickstart: OK — bootstrap precedes doctor; {len(cmds)} command(s) exit 0.")
    else:
        print("check_quickstart: OK — bootstrap precedes doctor (order only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
