#!/usr/bin/env python3

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


    from _org_generated import NEVER_AUTO_APPROVE as _GENERATED_NEVER
except ImportError:
    _GENERATED_NEVER = None


_QONUN5_FLOOR = (
    "new_goal", "security_sensitive", "schema_migration", "gate5_deployment",
    "governance_or_policy", "permission_change", "secret_change",
)


_SAFETY_KEYS = ("approval", "ticket_type", "stage", "labels", "paths")


def _smuggled_safety_fence(lines: list[str], after: int) -> bool:
    saw_safety_key = False
    for line in lines[after:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return False
        if line in ("---", "..."):
            return saw_safety_key
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in _SAFETY_KEYS:
            saw_safety_key = True
    return False


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()


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
        return {}
    return data if isinstance(data, dict) else None


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _clean_tokens(value) -> set:
    out: set = set()
    for item in _as_list(value):
        if item is None or isinstance(item, dict | bool):
            continue
        token = str(item).strip()
        if token:
            out.add(token)
    return out


def _glob_to_regex(glob: str) -> str:
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
    return re.fullmatch(_glob_to_regex(glob), path, re.IGNORECASE) is not None


def matches_category(fm: dict, matcher: dict) -> bool:
    if not isinstance(matcher, dict):
        return False


    for key in ("ticket_type", "stage"):
        want = {t.lower() for t in _clean_tokens(matcher.get(key))}
        if want:
            for val in _as_list(fm.get(key)):
                if val is not None and str(val).strip().lower() in want:
                    return True

    want_labels = {t.lower() for t in _clean_tokens(matcher.get("labels"))}
    if want_labels & {str(v).strip().lower() for v in _as_list(fm.get("labels"))}:
        return True


    declared = [str(p) for p in _as_list(fm.get("paths"))]
    for glob in _clean_tokens(matcher.get("paths")):
        globs = [glob, glob[:-3]] if glob.endswith("/**") else [glob]
        for g in globs:
            for p in declared:
                if path_matches(p, g):
                    return True
    return False


APPROVAL_MISSING = "missing"
APPROVAL_AUTO = "auto"
APPROVAL_HUMAN = "human"


_NON_APPROVAL_TOKENS = frozenset({
    "", "-", "?", "n/a", "na", "nil", "no", "none", "null",
    "false", "pending", "tbd", "todo", "unknown", "unset",
})


def approval_state(fm: dict) -> str:
    raw = fm.get("approval")
    if raw is None or isinstance(raw, bool | dict | list):
        return APPROVAL_MISSING
    value = str(raw).strip().lower()
    if value in _NON_APPROVAL_TOKENS:
        return APPROVAL_MISSING
    if value.startswith("auto"):
        return APPROVAL_AUTO
    return APPROVAL_HUMAN


def is_auto_approved(fm: dict) -> bool:
    return approval_state(fm) == APPROVAL_AUTO


def lacks_human_approval(fm: dict) -> bool:
    return approval_state(fm) != APPROVAL_HUMAN


_VIOLATION_REASON = {
    APPROVAL_AUTO: "auto-approved but category {category!r} requires human approval",
    APPROVAL_MISSING: (
        "category {category!r} requires an explicit human approval, but the ticket "
        "declares no usable 'approval' — absence fails CLOSED, not open"
    ),
}


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

            checked += 1
            violations.append((md.name, "frontmatter is unparseable or carries a smuggled safety fence"))
            continue
        if not fm:
            continue
        checked += 1
        state = approval_state(fm)
        if state == APPROVAL_HUMAN:
            continue
        for category in never:
            matcher = matchers.get(category) or {}
            if matches_category(fm, matcher):
                tid = str(fm.get("id", md.name))
                violations.append((tid, _VIOLATION_REASON[state].format(category=category)))

    if violations:
        sys.stderr.write("FAIL: never-auto-approve violations (QONUN-5):\n")
        for tid, reason in violations:
            sys.stderr.write(f"  - {tid}: {reason}\n")
        sys.stderr.write(f"\n{len(violations)} violation(s) across {checked} tickets.\n")
        return 1

    print(f"OK: {checked} tickets checked, no never-auto-approve violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
