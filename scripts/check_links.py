#!/usr/bin/env python3
"""check_links.py — broken-relative-link scanner for tracked Markdown.

Scans every tracked ``*.md`` file for Markdown links ``[text](target)`` and
flags those whose *relative* target does not resolve to an existing file or
directory on disk. External links (``http://``, ``https://``, ``mailto:``,
protocol-relative ``//host``) and pure in-page anchors (``#section``) are
ignored. A ``target`` may carry an ``#anchor`` suffix, which is stripped before
the existence check (anchors themselves are not validated).

Exit codes
----------
0  no broken relative links
1  at least one broken relative link
2  usage / environment error

This validator backs EPIC B (reference & link integrity) and is wired into CI
and ``diagnostics.py`` (Documentation dimension). It is the source of truth for
the ``check_links`` release gate.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# [text](target) — non-greedy text, target up to the first unbalanced ')'.
_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)]+)\)")
# Targets we never resolve on disk.
_EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|mailto:)", re.IGNORECASE)


def repo_root() -> Path:
    """Return the git repository root (falls back to CWD if not in git)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def tracked_markdown(root: Path) -> list[Path]:
    """Return tracked ``*.md`` paths; fall back to a filesystem walk."""
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
    return [p for p in root.rglob("*.md") if ".git" not in p.parts]


def link_targets(text: str) -> list[tuple[int, str]]:
    """Yield ``(line_number, target)`` for every Markdown link in ``text``."""
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        # Ignore link-looking syntax inside inline code spans (`...`) — those are
        # documentation examples, not real links.
        scrubbed = re.sub(r"`[^`]*`", " ", line)
        for m in _LINK_RE.finditer(scrubbed):
            out.append((i, m.group("target").strip()))
    return out


def broken_links(md_file: Path) -> list[tuple[int, str]]:
    """Return ``(line, target)`` for each broken relative link in ``md_file``."""
    try:
        text = md_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    broken: list[tuple[int, str]] = []
    for line_no, target in link_targets(text):
        if _EXTERNAL_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].strip()
        if not path_part:  # pure anchor like (#foo)
            continue
        # Absolute (web-root) targets and template placeholders ({{ }}) are not
        # relative file links — out of scope.
        if path_part.startswith("/") or "{{" in path_part or "}}" in path_part:
            continue
        resolved = (md_file.parent / path_part).resolve()
        if not resolved.exists():
            broken.append((line_no, target))
    return broken


def check(root: Path) -> list[str]:
    """Return a list of human-readable broken-link messages (empty == clean)."""
    failures: list[str] = []
    for md in sorted(tracked_markdown(root)):
        # Skip test-data dirs — golden-eval tasks (e.g. tech-writer/doc-link-check)
        # deliberately embed broken links in fixtures/submissions as the input to
        # detect; linting that test data is a false positive (ORGANISM WS6 evals).
        if "fixtures" in md.parts or "submissions" in md.parts:
            continue
        for line_no, target in broken_links(md):
            rel = md.relative_to(root) if md.is_relative_to(root) else md
            failures.append(f"{rel}:{line_no}: broken relative link -> {target}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
    print(f"check_links: OK — no broken relative links in tracked Markdown ({root}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
