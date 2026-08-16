#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import ROOT

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2
EXIT_NO_DATA = 3

ORG_REL = "config/org.yaml"
AGENTS_REL = ".claude/agents"

_PATH_RE = re.compile(
    r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:md|ya?ml|py|json|txt|toml))`"
)

_SKIP_PREFIXES = ("projects/", "http://", "https://", "~/")


def scanned_files(root: Path) -> list[Path]:
    out: list[Path] = []
    org = root / ORG_REL
    if org.is_file():
        out.append(org)
    agents = root / AGENTS_REL
    if agents.is_dir():
        out.extend(sorted(agents.glob("*.md")))
    return out


def referenced_paths(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _PATH_RE.finditer(line):
            rel = match.group(1)
            if rel.startswith(_SKIP_PREFIXES) or "*" in rel:
                continue
            hits.append((lineno, rel))
    return hits


def violations(root: Path) -> tuple[list[str], int, int]:
    files = scanned_files(root)
    broken: list[str] = []
    checked = 0
    for path in files:
        for lineno, rel in referenced_paths(path):
            checked += 1
            if not (root / rel).exists():
                broken.append(f"{path.relative_to(root).as_posix()}:{lineno}: `{rel}` does not exist")
    return broken, len(files), checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_charter_paths.py",
        description="check_charter_paths.py — every in-repo path an agent charter cites must exist.",
        epilog=f"exit codes: {EXIT_OK} all cited paths resolve · "
               f"{EXIT_VIOLATIONS} a charter cites a missing file · "
               f"{EXIT_USAGE} usage error · {EXIT_NO_DATA} nothing to scan",
    )
    parser.add_argument("--root", type=Path, default=None, help="repo root (default: self-located)")
    args = parser.parse_args(argv)
    root = (args.root or ROOT).resolve()
    if not root.is_dir():
        print(f"check_charter_paths: FATAL — {root} is not a directory", file=sys.stderr)
        return EXIT_USAGE

    broken, file_count, checked = violations(root)

    if file_count == 0:
        print("check_charter_paths: NO DATA — no config/org.yaml and no compiled charters; "
              "run scripts/gen_subagents.py", file=sys.stderr)
        return EXIT_NO_DATA

    if checked == 0:
        print(f"check_charter_paths: NO DATA — {file_count} file(s) scanned, "
              "no in-repo path citations found", file=sys.stderr)
        return EXIT_NO_DATA

    if broken:
        print(f"check_charter_paths: {len(broken)} dangling citation(s) "
              f"over {file_count} file(s):", file=sys.stderr)
        for line in broken:
            print(f"  FAIL  {line}", file=sys.stderr)
        return EXIT_VIOLATIONS

    print(f"check_charter_paths: OK — {checked} in-repo citation(s) over "
          f"{file_count} file(s) all resolve.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
