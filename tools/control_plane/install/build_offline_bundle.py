#!/usr/bin/env python3
"""build_offline_bundle.py — FR-008 vendored-wheel offline install recipe (CP-6).

Builds `tools/control_plane/.vendor/` (gitignored, machine-specific install
cache) on a network-connected build host: a platform-matched dependency closure
for `tools/control_plane/requirements-control.txt` (fastapi/uvicorn), meant to be
verified against real `Requires-Dist` metadata by `verify_closure.py` — NOT
trusting pip's cross-platform resolver alone. That resolver evaluates
environment markers (e.g. anyio's `exceptiongroup; python_version<"3.11"`)
against the CURRENT interpreter rather than the TARGET one, and has silently
dropped a real transitive dependency this way before (see
`docs/runbooks/ws-h-control-plane.md`).

Two phases, each an explicit subprocess call — nothing runs implicitly:
  1. `pip download` the closure as wheels, platform-matched, `--only-binary=:all:`.
     Needs network; run ONCE on the build host.
  2. `pip install --no-index --find-links=<wheels> --target=<site-packages>` —
     `--no-index` means this phase never touches the network. Copy `.vendor/`
     to the offline target and run phase 2 there (or just point `PYTHONPATH`
     at the already-installed `site-packages/`, skipping phase 2 entirely).

`plan()` is a pure function (no I/O). `build(dry_run=True)` (the default) never
calls `subprocess` at all — it only returns the planned commands, which is what
lets a test assert "no external fetch is attempted" without mocking anything.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REQUIREMENTS = REPO_ROOT / "tools" / "control_plane" / "requirements-control.txt"
DEFAULT_VENDOR = REPO_ROOT / "tools" / "control_plane" / ".vendor"

# The full closure this recipe expects to land as wheels. `verify_closure.py`
# checks this against the REAL Requires-Dist graph — this tuple is the
# verification target, not a second source of truth pip is asked to trust.
EXPECTED_CLOSURE: tuple[str, ...] = (
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_core",
    "anyio",
    "exceptiongroup",
    "click",
    "h11",
    "idna",
    "typing_extensions",
    "typing_inspection",
    "annotated_types",
    "annotated_doc",
    "uvicorn",
)

DEFAULT_PLATFORMS: tuple[str, ...] = (
    "manylinux2014_aarch64",
    "manylinux_2_17_aarch64",
    "manylinux_2_28_aarch64",
)


@dataclass(frozen=True)
class BuildPlan:
    download_cmd: list[str]
    install_cmd: list[str]


def plan(
    *,
    requirements: Path = DEFAULT_REQUIREMENTS,
    wheels_dir: Path,
    site_packages_dir: Path,
    python_version: str = "3.10",
    abi: str = "cp310",
    platforms: tuple[str, ...] = DEFAULT_PLATFORMS,
) -> BuildPlan:
    """Build the two pip commands. Pure — no I/O, no subprocess, no network."""
    download_cmd = [sys.executable, "-m", "pip", "download", "-r", str(requirements)]
    for plat in platforms:
        download_cmd += ["--platform", plat]
    download_cmd += [
        "--python-version",
        python_version,
        "--implementation",
        "cp",
        "--abi",
        abi,
        "--only-binary=:all:",
        "-d",
        str(wheels_dir),
    ]
    install_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(wheels_dir),
        "--target",
        str(site_packages_dir),
        "-r",
        str(requirements),
    ]
    return BuildPlan(download_cmd=download_cmd, install_cmd=install_cmd)


def build(*, dry_run: bool = True, **plan_kwargs: object) -> BuildPlan:
    """Return the plan; run it only when `dry_run=False`.

    `dry_run=True` (the default) touches neither the filesystem nor the
    network — it is safe to call from a test with no mocking at all.
    """
    bp = plan(**plan_kwargs)  # type: ignore[arg-type]
    if dry_run:
        return bp
    subprocess.run(bp.download_cmd, check=True)  # network — build host only
    subprocess.run(bp.install_cmd, check=True)  # --no-index — no network
    return bp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    ap.add_argument("--wheels-dir", type=Path, default=DEFAULT_VENDOR / "wheels")
    ap.add_argument("--site-packages-dir", type=Path, default=DEFAULT_VENDOR / "site-packages")
    ap.add_argument("--python-version", default="3.10")
    ap.add_argument("--abi", default="cp310")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the commands; do not run them"
    )
    args = ap.parse_args(argv)

    bp = build(
        dry_run=args.dry_run,
        requirements=args.requirements,
        wheels_dir=args.wheels_dir,
        site_packages_dir=args.site_packages_dir,
        python_version=args.python_version,
        abi=args.abi,
    )
    print("download:", " ".join(bp.download_cmd))
    print("install: ", " ".join(bp.install_cmd))
    if args.dry_run:
        print("(--dry-run: nothing was executed, no network touched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
