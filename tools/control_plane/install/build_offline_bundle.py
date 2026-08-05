#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REQUIREMENTS = REPO_ROOT / "tools" / "control_plane" / "requirements-control.txt"
DEFAULT_VENDOR = REPO_ROOT / "tools" / "control_plane" / ".vendor"


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
    bp = plan(**plan_kwargs)
    if dry_run:
        return bp
    subprocess.run(bp.download_cmd, check=True)
    subprocess.run(bp.install_cmd, check=True)
    return bp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='build_offline_bundle.py — FR-008 vendored-wheel offline install recipe (CP-6).')
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
