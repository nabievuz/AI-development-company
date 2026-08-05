#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _paths import ROOT

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_NO_DATA = 3

_QUICKSTART_RE = re.compile(r"##\s+Quickstart.*?```(?:bash)?\n(.*?)\n```", re.S)

_SCRIPT_NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.py"
_FLAG = r"--[A-Za-z0-9][A-Za-z0-9-]*(?:=[A-Za-z0-9_./-]+)?"
_CMD_RE = re.compile(rf"python3\s+scripts/{_SCRIPT_NAME}(?:\s+{_FLAG})*")


class UnsafeQuickstartCommand(ValueError):
    pass


def is_runnable_command(code: str) -> bool:
    return _CMD_RE.fullmatch(code) is not None


def command_argv(code: str) -> list[str]:
    if not is_runnable_command(code):
        raise UnsafeQuickstartCommand(code)
    argv = shlex.split(code)
    if any(tok in argv for tok in (";", "&&", "||", "|", "&", ">", "<", "`")):
        raise UnsafeQuickstartCommand(code)
    return argv


def quickstart_commands(readme: Path) -> list[str]:
    m = _QUICKSTART_RE.search(readme.read_text(encoding="utf-8", errors="ignore"))
    if not m:
        return []
    cmds: list[str] = []
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code = line.split("#", 1)[0].strip()
        if is_runnable_command(code):
            cmds.append(code)
    return cmds


def order_problem(cmds: list[str]) -> str | None:
    def idx(name: str) -> int:
        return next((i for i, c in enumerate(cmds) if name in c), -1)

    boot, doc = idx("bootstrap.py"), idx("doctor.py")
    if boot == -1:
        return "Quickstart never runs scripts/bootstrap.py (first-run setup)"
    if doc != -1 and boot > doc:
        return "bootstrap.py must precede doctor.py (doctor's projects/ check needs bootstrap)"
    return None


def run_in_scratch(root: Path, cmds: list[str]) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "clone"
        scratch.mkdir()
        try:
            arch = subprocess.run(
                ["git", "archive", "HEAD"], cwd=root, capture_output=True, check=True
            ).stdout
            subprocess.run(["tar", "-x", "-C", str(scratch)], input=arch, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        shutil.copytree(root / "scripts", scratch / "scripts", dirs_exist_ok=True)
        shutil.copy2(root / "README.md", scratch / "README.md")
        env = {**os.environ, "CI": "1"}
        for cmd in cmds:
            try:
                argv = command_argv(cmd)
            except UnsafeQuickstartCommand:
                return f"`{cmd}` is not a plain `python3 scripts/<name>.py` invocation; refusing to run it"
            proc = subprocess.run(
                argv, cwd=scratch, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            if proc.returncode != 0:
                return f"`{cmd}` exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_quickstart.py",
        description="check_quickstart.py — the README Quickstart actually works on a fresh clone.",
        epilog=f"exit codes: {EXIT_OK} quickstart works · {EXIT_FAIL} quickstart broken · "
               f"{EXIT_USAGE} usage error · {EXIT_NO_DATA} no README/Quickstart to check",
    )
    parser.add_argument("--root", type=Path, default=None, help="repository root to check")
    parser.add_argument("--no-run", action="store_true", help="order check only (skip running)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()

    readme = root / "README.md"
    if not readme.is_file():
        print(f"check_quickstart: NO DATA — {readme} does not exist; nothing was checked",
              file=sys.stderr)
        return EXIT_NO_DATA

    cmds = quickstart_commands(readme)
    if not cmds:
        print("check_quickstart: NO DATA — no runnable Quickstart commands found", file=sys.stderr)
        return EXIT_NO_DATA

    problem = order_problem(cmds)
    if problem:
        print(f"check_quickstart: FAIL — {problem}", file=sys.stderr)
        return EXIT_FAIL

    if not args.no_run:
        err = run_in_scratch(root, cmds)
        if err:
            print(f"check_quickstart: FAIL — {err}", file=sys.stderr)
            return EXIT_FAIL
        print(f"check_quickstart: OK — bootstrap precedes doctor; {len(cmds)} command(s) exit 0.")
    else:
        print("check_quickstart: OK — bootstrap precedes doctor (order only).")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
