#!/usr/bin/env python3
"""bootstrap.py — idempotent first-run setup for a fresh DasLab clone.

Resolves the repository root at runtime (LAW A — self-locating), ensures the
gitignored ``projects/`` workspace exists, (re)generates the 32 agent shims from
the org tree, and reports the environment via ``doctor.py``.

    git clone … && python3 scripts/bootstrap.py && claude

is the entire onboarding. Safe to re-run: every step is idempotent.

Exit code is 0 on a successful bootstrap. ``doctor.py`` is informational — a
missing MCP server or Ollama model is reported but does not fail bootstrap, so
the repo is usable for board work even before the optional services are wired.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from _paths import ROOT


def _run(label: str, argv: list[str]) -> int:
    print(f"→ {label}")
    rc = subprocess.run(argv, cwd=ROOT).returncode
    print(f"  {'ok' if rc == 0 else f'(rc={rc})'}")
    return rc


def _provision_memory() -> None:
    """Best-effort provisioning of the optional memory layer — never fails bootstrap.

    Full mode needs Ollama (embeddings) + ~/ArcRift (persistent memory). When they
    are absent the org still boots in memory-optional mode; print the exact setup
    commands. See governance/policies/memory-modes.md.
    """
    ollama = shutil.which("ollama")
    arcrift = (Path.home() / "ArcRift").exists()
    if ollama:
        print("→ Ollama present — ensuring nomic-embed-text (best-effort)")
        subprocess.run([ollama, "pull", "nomic-embed-text"], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ollama and arcrift:
        print("→ memory layer available (Ollama + ~/ArcRift) — full mode")
        return
    print("→ memory layer not fully present — booting in MEMORY-OPTIONAL mode")
    if not ollama:
        print("    embeddings:  install Ollama, then `ollama pull nomic-embed-text`")
    if not arcrift:
        print("    persistent:  set up ~/ArcRift (see governance/policies/memory-modes.md)")
    print("    the org boots + runs now; recall/store are best-effort until provisioned.")


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    print(f"DasLab bootstrap — repository root: {ROOT}")

    projects = ROOT / "projects"
    if projects.exists():
        print("→ projects/ exists")
    else:
        projects.mkdir(parents=True)
        print(f"→ created {projects}")

    rc = _run("regenerate agent shims", [sys.executable, str(ROOT / "scripts" / "gen_subagents.py")])
    if rc != 0:
        print("bootstrap FAILED: gen_subagents.py errored", file=sys.stderr)
        return rc

    _provision_memory()

    # doctor.py exits 0 when REQUIRED checks pass (OPTIONAL memory checks = WARN).
    _run("environment preflight (doctor.py)", [sys.executable, str(ROOT / "scripts" / "doctor.py")])

    print("bootstrap complete — open `claude` at the repo root, then /daslab-plan \"<goal>\".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
