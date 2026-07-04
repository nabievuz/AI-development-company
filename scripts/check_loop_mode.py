#!/usr/bin/env python3
"""check_loop_mode.py — the self-optimizing loop stays OFF (PRD §6).

``config/loop.yaml`` is the SSOT for the loop's mode. The loop ships
its levers (registry, validators, GATE-6) but does NOT act: the mode must be
shadow (or at most measured) and no tuning may auto-apply. The live-promotion
modes (limited_live / full) are forbidden here — they require a GATE-6 record
plus a week of clean live T1-T7. This is how "no auto-apply path is reachable in
P1" and "no fake KPIs" are enforced as code. Editing config/loop.yaml is
governance/policy -> never-auto-approve (QONUN-5).

Exit codes: 0 = loop safely off, 1 = unsafe loop config, 2 = usage/IO error.

Usage:
    python3 scripts/check_loop_mode.py [--config config/loop.yaml]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

LIVE_MODES = {"limited_live", "full"}


def check_loop(cfg: dict) -> list[str]:
    """Return a list of problems with the loop config; empty == safely off."""
    problems: list[str] = []
    ladder = cfg.get("ladder") or []
    mode = cfg.get("mode")
    if mode not in ladder:
        problems.append(f"mode {mode!r} is not one of the ladder steps {ladder}")
    if mode in LIVE_MODES:
        problems.append(
            f"loop mode {mode!r} enables live tuning — P1 allows shadow/measured only"
        )
    if cfg.get("auto_apply") is not False:
        problems.append("auto_apply must be false in P1 (the loop reads, it does not act)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "loop.yaml")
    args = ap.parse_args(argv)

    if not args.config.is_file():
        sys.stderr.write(f"ERROR: loop config not found: {args.config}\n")
        return 2
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}

    problems = check_loop(cfg)
    if problems:
        sys.stderr.write("FAIL: the self-optimizing loop must stay OFF in P1 (PRD §6 / RFC-001):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: loop off — mode '{cfg.get('mode')}', auto_apply false (levers only, no controller).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
