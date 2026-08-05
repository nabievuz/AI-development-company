#!/usr/bin/env python3

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
    argparse.ArgumentParser(description='bootstrap.py — idempotent first-run setup for a fresh DasLab clone.').parse_args(argv)
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


    _run("environment preflight (doctor.py)", [sys.executable, str(ROOT / "scripts" / "doctor.py")])

    print("bootstrap complete — open `claude` at the repo root, then /daslab-plan \"<goal>\".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
