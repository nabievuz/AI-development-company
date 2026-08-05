#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

from _paths import ROOT

BANNED: list[tuple[str, list[str]]] = [
    ("langgraph", ["langgraph"]),
    ("agent-framework", ["agent_framework", "agentframework"]),
    ("crewai", ["crewai"]),
    ("agency-swarm", ["agency_swarm"]),
    ("superagi", ["superagi"]),
]


SANCTIONED_IMPORT_PATHS: list[tuple[str, str]] = [
    ("langgraph", "scripts/dgox/"),
]


def _is_sanctioned_import(lib_name: str, rel_posix: str) -> bool:
    return any(
        lib_name == sanctioned_lib and rel_posix.startswith(prefix)
        for sanctioned_lib, prefix in SANCTIONED_IMPORT_PATHS
    )


def _dist_pattern(name: str) -> re.Pattern[str]:
    parts = re.split(r"[-_]", name)
    norm = r"[-_]".join(re.escape(p) for p in parts)
    return re.compile(r"(?i)\b" + norm + r"\b")


def _import_pattern(aliases: list[str]) -> re.Pattern[str]:
    alts = "|".join(re.escape(a) for a in aliases)
    return re.compile(
        r"^\s*(?:import|from)\s+(?:" + alts + r")(?:\b|\.)",
        re.MULTILINE,
    )


_DIST_PATS: list[tuple[str, re.Pattern[str]]] = [
    (name, _dist_pattern(name)) for name, _ in BANNED
]
_IMPORT_PATS: list[tuple[str, re.Pattern[str]]] = [
    (name, _import_pattern(aliases)) for name, aliases in BANNED
]


def _is_pkg_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#") and not s.startswith("-")


def _pkg_name(line: str) -> str:
    name = line.strip()
    for stop in ("[", "=", "<", ">", "!", "~", "@", " ", "\t", "#", ";", "\\"):
        idx = name.find(stop)
        if idx != -1:
            name = name[:idx]
    return name.strip()


def _scan_pyproject(root: Path, pyproject_path: Path) -> list[str]:
    hits: list[str] = []
    rel = str(pyproject_path.relative_to(root))
    try:
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
    except Exception:
        return hits


    pep621_deps: list[str] = data.get("project", {}).get("dependencies", [])
    for dep in pep621_deps:
        if not isinstance(dep, str):
            continue
        pkg = _pkg_name(dep)
        if not pkg:
            continue
        for lib_name, pat in _DIST_PATS:
            if pat.search(pkg):
                hits.append(
                    f"{rel} [project.dependencies]: banned distribution '{lib_name}' "
                    f"(found '{pkg}')"
                )


    poetry_deps: dict = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for dep_name in poetry_deps:
        if not isinstance(dep_name, str):
            continue
        for lib_name, pat in _DIST_PATS:
            if pat.search(dep_name):
                hits.append(
                    f"{rel} [tool.poetry.dependencies]: banned distribution '{lib_name}' "
                    f"(found '{dep_name}')"
                )

    return hits


def scan_manifests(root: Path) -> list[str]:
    hits: list[str] = []
    manifests = sorted(root.glob("requirements*.txt")) + sorted(
        root.glob("requirements*.in")
    )
    for manifest in manifests:
        try:
            lines = manifest.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        rel = manifest.relative_to(root)
        for lineno, raw in enumerate(lines, start=1):
            if not _is_pkg_line(raw):
                continue
            pkg = _pkg_name(raw)
            if not pkg:
                continue
            for lib_name, pat in _DIST_PATS:
                if pat.search(pkg):
                    hits.append(
                        f"{rel}:{lineno}: banned distribution '{lib_name}' "
                        f"(found '{pkg}')"
                    )

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        hits.extend(_scan_pyproject(root, pyproject))

    return hits


def scan_imports(root: Path) -> list[str]:
    hits: list[str] = []
    for scan_dir_name in ("scripts", "tests"):
        scan_dir = root / scan_dir_name
        if not scan_dir.is_dir():
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            try:
                text = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            lines = text.splitlines()
            rel = py_file.relative_to(root).as_posix()
            for lib_name, pat in _IMPORT_PATS:


                if _is_sanctioned_import(lib_name, rel):
                    continue
                for m in pat.finditer(text):
                    lineno = text[: m.start()].count("\n") + 1

                    raw_line = lines[lineno - 1] if lineno <= len(lines) else ""
                    if raw_line.lstrip().startswith("#"):
                        continue
                    hits.append(
                        f"{rel}:{lineno}: banned import '{lib_name}' "
                        f"(found '{m.group().strip()}')"
                    )
    return hits


def check(root: Path) -> list[str]:
    return scan_manifests(root) + scan_imports(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='check_import_ban.py — GATE-4 clean-room: fail on any banned donor library.')
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repo root (default: self-located via _paths.ROOT)",
    )
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()

    if not root.is_dir():
        print(
            f"check_import_ban: FATAL — {root} is not a directory",
            file=sys.stderr,
        )
        return 2

    hits = check(root)
    if hits:
        print(
            f"check_import_ban: {len(hits)} banned donor lib(s) found:",
            file=sys.stderr,
        )
        for h in hits:
            print(f"  FAIL  {h}", file=sys.stderr)
        return 1
    print("check_import_ban: OK — no banned donor libraries in manifests or imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
