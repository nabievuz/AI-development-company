#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
FEATURE_FLAG = "ws_h_control_plane"
OPTIONAL_DEPS: tuple[str, ...] = ("fastapi", "uvicorn")


@dataclass(frozen=True)
class Decision:
    mode: str
    reason: str


def _flag_on(features_path: Path | None = None) -> bool:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import feature_flags

    return feature_flags.enabled(FEATURE_FLAG, features_path)


def _deps_importable(deps: tuple[str, ...] = OPTIONAL_DEPS) -> bool:
    return all(importlib.util.find_spec(name) is not None for name in deps)


def resolve_surface(
    *, features_path: Path | None = None, force_static: bool = False
) -> Decision:
    if force_static:
        return Decision("static", "forced by --force-static")
    if not _flag_on(features_path):
        return Decision("static", f"feature flag {FEATURE_FLAG!r} is OFF")
    if not _deps_importable():
        return Decision(
            "static",
            "optional deps (fastapi/uvicorn) not importable — degrade, not a crash",
        )
    return Decision("control-plane", f"flag {FEATURE_FLAG!r} ON and deps importable")


def render_static_cockpit(repo_root: Path, out: Path | None = None) -> Path:
    out = out or (repo_root / "board" / ".cockpit.html")
    cmd = [sys.executable, str(repo_root / "scripts" / "cockpit_html.py"), "--out", str(out)]
    subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='degrade.py — WS-H NOT-a-daemon / degrade-to-static launcher (ADR-0039 CP-5, FR-006).')
    ap.add_argument("--repo-root", type=Path, default=ROOT)
    ap.add_argument("--features", type=Path, default=None)
    ap.add_argument("--force-static", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    decision = resolve_surface(features_path=args.features, force_static=args.force_static)
    if decision.mode == "static":
        out = render_static_cockpit(args.repo_root, args.out)
        print(f"[ws-h-install] degrade-to-static ({decision.reason}) -> {out}")
        return 0

    print(
        f"[ws-h-install] control-plane eligible ({decision.reason}); start it "
        "yourself: python3 -m uvicorn tools.control_plane.app:app --host "
        "127.0.0.1 --port 8899 (see docs/runbooks/ws-h-control-plane.md). This "
        "launcher only makes the routing decision — it never execs uvicorn "
        "itself (NOT-a-daemon, CP-5)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
