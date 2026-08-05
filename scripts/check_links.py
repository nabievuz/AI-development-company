#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)]+)\)")

_EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|mailto:)", re.IGNORECASE)


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


UNTRACKED_DIR_NAMES: frozenset[str] = frozenset(
    {".git", "projects", "node_modules", ".venv", "venv", ".vendor", "__pycache__"}
)


def tracked_markdown(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=root, capture_output=True, text=True, check=True,
        )
        files = [root / line for line in out.stdout.splitlines() if line]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return [
        p
        for p in root.rglob("*.md")
        if not UNTRACKED_DIR_NAMES.intersection(p.parts)
    ]


def link_targets(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):


        scrubbed = re.sub(r"`[^`]*`", " ", line)
        for m in _LINK_RE.finditer(scrubbed):
            out.append((i, m.group("target").strip()))
    return out


def broken_links(md_file: Path) -> list[tuple[int, str]]:
    try:
        text = md_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    broken: list[tuple[int, str]] = []
    for line_no, target in link_targets(text):
        if _EXTERNAL_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].strip()
        if not path_part:
            continue


        if path_part.startswith("/") or "{{" in path_part or "}}" in path_part:
            continue
        resolved = (md_file.parent / path_part).resolve()
        if not resolved.exists():
            broken.append((line_no, target))
    return broken


def check(root: Path) -> list[str]:
    failures: list[str] = []
    for md in sorted(tracked_markdown(root)):


        if "fixtures" in md.parts or "submissions" in md.parts:
            continue
        for line_no, target in broken_links(md):
            rel = md.relative_to(root) if md.is_relative_to(root) else md
            failures.append(f"{rel}:{line_no}: broken relative link -> {target}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='check_links.py — broken-relative-link scanner for tracked Markdown.')
    parser.add_argument(
        "--root", type=Path, default=None,
        help="repository root to scan (default: git toplevel / CWD)",
    )
    args = parser.parse_args(argv)
    root = (args.root or repo_root()).resolve()
    if not root.is_dir():
        print(f"check_links: FATAL — root {root} is not a directory", file=sys.stderr)
        return 2

    failures = check(root)
    if failures:
        print(f"check_links: {len(failures)} broken relative link(s) found:", file=sys.stderr)
        for f in failures:
            print(f"  FAIL  {f}", file=sys.stderr)
        return 1
    scanned = len(tracked_markdown(root))
    print(
        f"check_links: OK — no broken relative links in "
        f"{scanned} tracked Markdown file(s) ({root})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
