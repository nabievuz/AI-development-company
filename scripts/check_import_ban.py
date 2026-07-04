#!/usr/bin/env python3
"""check_import_ban.py — GATE-4 clean-room: fail on any banned donor library.

Five banned donor agent-framework libraries (§2.3 clean-room):
  1. langgraph
  2. agent-framework (Microsoft)
  3. crewai
  4. agency-swarm
  5. superagi

Scans two surfaces:
  * Dependency manifests: requirements*.txt, requirements*.in, pyproject.toml
    ([project.dependencies] / [tool.poetry.dependencies])
  * Python source:        scripts/**/*.py and tests/**/*.py (recursive)

Matching is word-boundary-safe (Python re with \\b — NOT git grep -E which
silently ignores \\b), so a substring like ``my_crewai_plugin`` is NOT a hit.

Exit codes
----------
0  no banned library found
1  at least one banned library found
2  usage / environment error
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

from _paths import ROOT

# ---------------------------------------------------------------------------
# Banned libraries: (canonical-distribution-name, [import-module-aliases])
#
# Distribution-name matching is normalised (hyphens == underscores, case-
# insensitive) per PEP 508.  Import-module aliases cover the actual top-level
# Python name(s) used in "import <x>" or "from <x> import …".
# ---------------------------------------------------------------------------
BANNED: list[tuple[str, list[str]]] = [
    ("langgraph", ["langgraph"]),
    ("agent-framework", ["agent_framework", "agentframework"]),
    ("crewai", ["crewai"]),
    ("agency-swarm", ["agency_swarm"]),
    ("superagi", ["superagi"]),
]


def _dist_pattern(name: str) -> re.Pattern[str]:
    """Case-insensitive, boundary-safe regex for a distribution/package name.

    Splits on ``[-_]`` and re-joins with ``[-_]`` so that PEP 508 normalised
    equivalents (hyphens == underscores) are both matched.
    Uses Python re ``\\b`` — NOT git grep -E which ignores ``\\b``.
    """
    parts = re.split(r"[-_]", name)
    norm = r"[-_]".join(re.escape(p) for p in parts)
    return re.compile(r"(?i)\b" + norm + r"\b")


def _import_pattern(aliases: list[str]) -> re.Pattern[str]:
    """Regex matching a Python import/from-import of any of ``aliases``.

    Anchored to line-start (after optional whitespace) so it matches actual
    import statements, not mid-line occurrences inside string literals.
    The trailing ``(?:\\b|\\.)`` also catches submodule imports such as
    ``import langgraph.graph``.
    """
    alts = "|".join(re.escape(a) for a in aliases)
    return re.compile(
        r"^\s*(?:import|from)\s+(?:" + alts + r")(?:\b|\.)",
        re.MULTILINE,
    )


# Pre-compile once; reused across all scanned files.
_DIST_PATS: list[tuple[str, re.Pattern[str]]] = [
    (name, _dist_pattern(name)) for name, _ in BANNED
]
_IMPORT_PATS: list[tuple[str, re.Pattern[str]]] = [
    (name, _import_pattern(aliases)) for name, aliases in BANNED
]


# ---------------------------------------------------------------------------
# Manifest scanning (requirements*.txt / requirements*.in)
# ---------------------------------------------------------------------------


def _is_pkg_line(line: str) -> bool:
    """True when a requirements line specifies a package (not a comment or option)."""
    s = line.strip()
    return bool(s) and not s.startswith("#") and not s.startswith("-")


def _pkg_name(line: str) -> str:
    """Extract the bare package name from a requirements line.

    Stops at the first version specifier character, bracket, space, comment,
    semicolon, or line-continuation backslash.
    """
    name = line.strip()
    for stop in ("[", "=", "<", ">", "!", "~", "@", " ", "\t", "#", ";", "\\"):
        idx = name.find(stop)
        if idx != -1:
            name = name[:idx]
    return name.strip()


def _scan_pyproject(root: Path, pyproject_path: Path) -> list[str]:
    """Scan pyproject.toml for banned libs in [project.dependencies] / [tool.poetry.dependencies].

    Uses ``tomllib`` (stdlib since Python 3.11) for correct TOML parsing.
    Checks both PEP 621 (``[project]``) and Poetry (``[tool.poetry]``) tables.
    Line numbers are omitted because tomllib does not expose them; the TOML
    section is included in the violation string so the location is still clear.
    """
    hits: list[str] = []
    rel = str(pyproject_path.relative_to(root))
    try:
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
    except Exception:  # noqa: BLE001 — treat any TOML error as non-fatal
        return hits

    # PEP 621: [project.dependencies] — a list of PEP 508 dependency strings.
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

    # Poetry: [tool.poetry.dependencies] — a table keyed by package name.
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
    """Return violation descriptions for banned libs found in requirements manifests.

    Scanned surfaces:
      * ``requirements*.txt`` and ``requirements*.in`` at the repo root.
      * ``pyproject.toml`` at the repo root (PEP 621 and Poetry dependency tables).
    """
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


# ---------------------------------------------------------------------------
# Import scanning (scripts/*.py)
# ---------------------------------------------------------------------------


def scan_imports(root: Path) -> list[str]:
    """Return violation descriptions for banned imports in scripts/ and tests/ (recursive).

    Scans all ``*.py`` files found by ``rglob`` under both ``scripts/`` and
    ``tests/``, so nested sub-packages (e.g. ``scripts/dgox/``) are covered.
    """
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
            rel = str(py_file.relative_to(root))
            for lib_name, pat in _IMPORT_PATS:
                for m in pat.finditer(text):
                    lineno = text[: m.start()].count("\n") + 1
                    # Skip lines that are comments (leading # after stripping).
                    raw_line = lines[lineno - 1] if lineno <= len(lines) else ""
                    if raw_line.lstrip().startswith("#"):
                        continue
                    hits.append(
                        f"{rel}:{lineno}: banned import '{lib_name}' "
                        f"(found '{m.group().strip()}')"
                    )
    return hits


# ---------------------------------------------------------------------------
# Public API + CLI
# ---------------------------------------------------------------------------


def check(root: Path) -> list[str]:
    """Return all violations (manifests + imports). Empty list = clean."""
    return scan_manifests(root) + scan_imports(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
