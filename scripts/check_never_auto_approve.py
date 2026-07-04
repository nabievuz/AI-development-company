#!/usr/bin/env python3
"""
check_never_auto_approve.py — DasLab safety validator.

Fails CI if any ticket in a "never-auto-approve" category was auto-approved.
Enforces QONUN-5 and the risk taxonomy *in code*.

The board frontmatter schema is documented in board/README.md, e.g.:
    ---
    id: DAS-123
    approval: auto            # or "manual:cxo" / "human:founder"
    ticket_type: feature      # feature | goal | epic-root | ...
    stage: GATE-3
    labels: [security]
    paths: ["src/auth/login.py"]
    ---
"Auto-approved" == the approval field starts with "auto".

Matching is fail-CLOSED and shape-tolerant:
  - unparseable OR fence-smuggled frontmatter is a violation (never a silent skip),
  - path globs honour recursive ** and are case-insensitive, so a top-level path,
    a bare filename (``.env``, ``CODEOWNERS``) or a bare directory is matched,
  - ticket_type / stage / labels / paths are coerced (scalar OR list) so a careless
    YAML shape cannot silently bypass a safety gate.

Usage:
    python scripts/check_never_auto_approve.py [--board board] [--config config/risk_taxonomy.yaml]

Exit 0 = clean. Exit 1 = violation(s). Exit 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

try:
    # Consume the generated SSOT (R-12 / ADR-009) so the never-auto-approve list
    # cannot drift from the Org Schema. Falls back to the config list if absent.
    from _org_generated import NEVER_AUTO_APPROVE as _GENERATED_NEVER
except ImportError:
    _GENERATED_NEVER = None

# Hard-coded QONUN-5 floor — UNIONed onto whatever the SSOT/config provides so this
# gate always checks at least these seven categories, even if the generated module is
# absent or a schema edit shortened it (the drift gate blocks that, this is belt-and-suspenders).
_QONUN5_FLOOR = (
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
)

# Frontmatter keys that decide a safety classification. If any of these appears
# at the top of a SECOND fenced block, the frontmatter is smuggled -> fail closed.
_SAFETY_KEYS = ("approval", "ticket_type", "stage", "labels", "paths")


def _smuggled_safety_fence(lines: list[str], after: int) -> bool:
    """True if a safety key sits before a *second* doc fence (fields hidden past
    the first block). Stops at the first markdown heading so body text never trips it."""
    saw_safety_key = False
    for line in lines[after:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return False  # reached the markdown body
        if line in ("---", "..."):
            return saw_safety_key
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in _SAFETY_KEYS:
            saw_safety_key = True
    return False


def parse_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter.

    Returns {} when there is no frontmatter block (or an empty one — legitimate),
    the parsed dict when present and valid, or None when the block is unparseable,
    not a mapping, or smuggled past a second fence — the caller fails closed on None.
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    # Closing fence = the first line (after the opening) that is exactly '---'/'...';
    # an indented '---' inside a block scalar is NOT a fence (column-0 only).
    end = next((i for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
    if end is None:
        return {}
    if _smuggled_safety_fence(lines, end + 1):
        return None
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return None
    if data is None:
        return {}  # empty frontmatter block is legitimate
    return data if isinstance(data, dict) else None


def _as_list(value) -> list:
    """Coerce a scalar-or-list frontmatter value into a list of items."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _clean_tokens(value) -> set:
    """Coerce a matcher SELECTOR (scalar or list) to the set of usable string tokens.

    Drops None / dict / bool / blank entries and ``str()``s the rest, mirroring how the
    ticket side is coerced. This is the SINGLE definition of "what a selector binds":
    check_org_drift.py imports it so the matcher-completeness CI gate and this runtime
    matcher share one notion of non-empty — a selector that yields an empty set here binds
    no ticket and must fail the gate, closing the truthiness/usability gap between them.
    """
    out: set = set()
    for item in _as_list(value):
        if item is None or isinstance(item, dict | bool):
            continue
        token = str(item).strip()
        if token:
            out.add(token)
    return out


def _glob_to_regex(glob: str) -> str:
    """Translate a path glob with globstar into a full-match regex.

    ``**/`` -> optionally-any directories, ``**`` -> anything, ``*`` -> a run
    within a path segment, ``?`` -> one non-separator char. Unlike stdlib fnmatch
    this gives real recursive-** semantics, so ``**/auth/**`` matches both
    ``auth/x`` (top level) and ``src/auth/x``.
    """
    out: list[str] = []
    i, n = 0, len(glob)
    while i < n:
        if glob[i:i + 3] == "**/":
            out.append(r"(?:.*/)?")
            i += 3
        elif glob[i:i + 2] == "**":
            out.append(r".*")
            i += 2
        elif glob[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return "".join(out)


def path_matches(path: str, glob: str) -> bool:
    """Case-insensitive recursive-glob match of one path against one glob."""
    return re.fullmatch(_glob_to_regex(glob), path, re.IGNORECASE) is not None


def matches_category(fm: dict, matcher: dict) -> bool:
    """True if a ticket's frontmatter matches a never-auto-approve matcher.

    A null / non-dict matcher (e.g. an empty ``category:`` block that YAML parses to
    None) matches NOTHING rather than crashing the scan — matcher *completeness* is a
    separate CI invariant enforced by check_org_drift.py. This guard also protects the
    other callers (intent_preview.py, approval_digest.py) from the same malformed input.
    """
    if not isinstance(matcher, dict):
        return False
    # The MATCHER side is coerced symmetrically with the ticket side (_clean_tokens):
    # a scalar selector becomes a one-item list, None/dict/blank entries are dropped, and
    # every entry is str()'d. So `paths: '**/.env*'` (scalar) binds like `['**/.env*']`,
    # and a malformed `paths: [null]` / `paths: true` cannot crash on `.endswith`.
    # All comparisons are case-INSENSITIVE (paths already were): a never-auto-approve gate
    # must err toward catching MORE, so a mis-cased matcher (`stage: [gate-5]` vs a `GATE-5`
    # ticket) still binds rather than silently letting a QONUN-5 ticket auto-approve.
    # ticket_type / stage — case-insensitive membership against the coerced matcher set.
    for key in ("ticket_type", "stage"):
        want = {t.lower() for t in _clean_tokens(matcher.get(key))}
        if want:
            for val in _as_list(fm.get(key)):
                if val is not None and str(val).strip().lower() in want:
                    return True
    # labels — any overlap (ticket labels may be a scalar or a list), case-insensitive.
    want_labels = {t.lower() for t in _clean_tokens(matcher.get("labels"))}
    if want_labels & {str(v).strip().lower() for v in _as_list(fm.get("labels"))}:
        return True
    # paths — any declared path matches any glob (recursive **, case-insensitive).
    # A `dir/**` glob also matches the bare directory (`dir`) it names.
    declared = [str(p) for p in _as_list(fm.get("paths"))]
    for glob in _clean_tokens(matcher.get("paths")):
        globs = [glob, glob[:-3]] if glob.endswith("/**") else [glob]
        for g in globs:
            for p in declared:
                if path_matches(p, g):
                    return True
    return False


def is_auto_approved(fm: dict) -> bool:
    approval = str(fm.get("approval", "")).strip().lower()
    return approval.startswith("auto")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default="board")
    ap.add_argument("--config", default="config/risk_taxonomy.yaml")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        sys.stderr.write(f"ERROR: risk taxonomy not found: {cfg_path}\n")
        return 2
    cfg = yaml.safe_load(cfg_path.read_text())
    base = _GENERATED_NEVER if _GENERATED_NEVER is not None else cfg.get("never_auto_approve", [])
    never = sorted(set(base) | set(_QONUN5_FLOOR))
    matchers = cfg.get("matchers", {})

    board = Path(args.board)
    if not board.exists():
        sys.stderr.write(f"ERROR: board dir not found: {board}\n")
        return 2

    violations: list[tuple[str, str]] = []
    checked = 0
    for md in sorted(board.rglob("*.md")):
        fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="ignore"))
        if fm is None:
            # Frontmatter present but unparseable / smuggled -> fail closed.
            checked += 1
            violations.append((md.name, "unparseable-or-smuggled-frontmatter"))
            continue
        if not fm:
            continue
        checked += 1
        if not is_auto_approved(fm):
            continue
        for category in never:
            matcher = matchers.get(category) or {}   # key-present-but-null -> {} (not None)
            if matches_category(fm, matcher):
                tid = str(fm.get("id", md.name))
                violations.append((tid, category))

    if violations:
        sys.stderr.write("FAIL: never-auto-approve violations (QONUN-5):\n")
        for tid, cat in violations:
            sys.stderr.write(f"  - {tid}: auto-approved but category '{cat}' requires human approval\n")
        sys.stderr.write(f"\n{len(violations)} violation(s) across {checked} tickets.\n")
        return 1

    print(f"OK: {checked} tickets checked, no never-auto-approve violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
