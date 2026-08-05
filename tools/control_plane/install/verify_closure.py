#!/usr/bin/env python3

from __future__ import annotations

import argparse
import email
import re
import zipfile
from pathlib import Path

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_requires_dist(wheel_path: Path) -> list[str]:
    with zipfile.ZipFile(wheel_path) as zf:
        meta_names = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
        if not meta_names:
            return []
        raw = zf.read(meta_names[0]).decode("utf-8", errors="replace")
    msg = email.message_from_string(raw)
    values = msg.get_all("Requires-Dist") or []
    names = []
    for v in values:
        m = _NAME_RE.match(v.strip())
        if m:
            names.append(_canonical(m.group(1)))
    return names


def _wheel_index(wheels_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for whl in wheels_dir.glob("*.whl"):
        stem = whl.name[: -len(".whl")]
        name = _canonical(stem.split("-")[0])
        index[name] = whl
    return index


def verify_closure(wheels_dir: Path, roots: tuple[str, ...]) -> list[str]:
    by_name = _wheel_index(wheels_dir)
    seen: set[str] = set()
    missing: list[str] = []
    stack = [_canonical(r) for r in roots]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        wheel = by_name.get(name)
        if wheel is None:
            missing.append(name)
            continue
        for dep in read_requires_dist(wheel):
            if dep not in seen:
                stack.append(dep)
    return sorted(set(missing))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='verify_closure.py — FR-008 real Requires-Dist closure verification (CP-6).')
    ap.add_argument("--wheels-dir", type=Path, required=True)
    ap.add_argument("roots", nargs="+", help="top-level package names, e.g. fastapi uvicorn")
    args = ap.parse_args(argv)

    missing = verify_closure(args.wheels_dir, tuple(args.roots))
    if missing:
        print(f"[verify-closure] INCOMPLETE — missing: {', '.join(missing)}")
        return 1
    print("[verify-closure] OK — full closure present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
