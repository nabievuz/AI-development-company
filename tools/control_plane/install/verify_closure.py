#!/usr/bin/env python3
"""verify_closure.py — FR-008 real Requires-Dist closure verification (CP-6).

pip's cross-platform wheel resolution evaluates environment markers (e.g.
anyio's `exceptiongroup; python_version<"3.11"`) against the CURRENT
interpreter, not the TARGET one — and has silently dropped a real transitive
dependency this way before. This module verifies a built vendor bundle by
reading each wheel's REAL `Requires-Dist` metadata directly — zipfile +
`email` header parsing, no import, no pip, no network — and walking the
dependency graph from the requested roots to find anything the resolver
should have downloaded but did not.
"""
from __future__ import annotations

import argparse
import email
import re
import zipfile
from pathlib import Path

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _canonical(name: str) -> str:
    """PEP 503 canonicalization — runs/dashes/underscores/dots all collapse to
    a single dash, lowercased, so `pydantic_core` and `pydantic-core` compare
    equal (real wheel filenames and Requires-Dist values disagree on this).
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def read_requires_dist(wheel_path: Path) -> list[str]:
    """Return the canonical project names from a wheel's `Requires-Dist`
    metadata (environment-marker / extras / version-specifier suffixes
    stripped off — only the name is needed to walk the graph).
    """
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
    """Map canonical project name -> the wheel file for it in *wheels_dir*."""
    index: dict[str, Path] = {}
    for whl in wheels_dir.glob("*.whl"):
        stem = whl.name[: -len(".whl")]
        name = _canonical(stem.split("-")[0])
        index[name] = whl
    return index


def verify_closure(wheels_dir: Path, roots: tuple[str, ...]) -> list[str]:
    """Walk the real Requires-Dist graph from *roots*; return the canonical
    names that are required (directly or transitively) but MISSING as a wheel
    in *wheels_dir*. Empty means the closure is complete — this is the check
    that catches an `exceptiongroup`-class gap the resolver can leave behind.
    """
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
