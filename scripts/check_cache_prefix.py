#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from _paths import ROOT


_STABLE_PREFIX_END_MARKER = "## Prompt-cache prefix layout (ADR 0006 — W4)"


_DEFAULT_SKILL = ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"
_DEFAULT_BASELINE = ROOT / "scripts" / ".cache_prefix_baseline"


_MIN_TOKENS = 4096


_DEFAULT_TOKENS_PER_CHAR = 0.25


_VOLATILE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [

    (
        "ISO timestamp",
        re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        ),
    ),

    (
        "UUID / run-id",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}"
            r"-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
        ),
    ),

    (
        "ticket-id",
        re.compile(r"\bDAS-\d{4,}\b"),
    ),

    (
        "wave-counter",
        re.compile(r"\bwave[-\s]\d+\b", re.IGNORECASE),
    ),
]


_VERSION_RE = re.compile(r"^CACHE_PREFIX_VERSION:\s*(\S+)", re.MULTILINE)


def extract_stable_prefix(skill_text: str) -> str:
    idx = skill_text.find(_STABLE_PREFIX_END_MARKER)
    if idx == -1:
        return skill_text
    return skill_text[:idx]


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approx_tokens(text: str, tokens_per_char: float) -> int:
    return int(len(text) * tokens_per_char)


def check_volatile(prefix: str) -> list[str]:
    violations: list[str] = []
    for label, pattern in _VOLATILE_PATTERNS:
        matches = pattern.findall(prefix)
        if matches:

            examples = ", ".join(repr(m) for m in matches[:3])
            suffix = f" (and {len(matches) - 3} more)" if len(matches) > 3 else ""
            violations.append(
                f"volatile token [{label}] found in stable prefix: {examples}{suffix}"
            )
    return violations


def read_baseline(baseline_path: Path) -> dict[str, str]:
    if not baseline_path.exists():
        return {}
    with baseline_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_baseline(baseline_path: Path, data: dict[str, str]) -> None:
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with baseline_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def run_checks(
    skill_path: Path,
    baseline_path: Path,
    *,
    fix: bool = False,
    tokens_per_char: float = _DEFAULT_TOKENS_PER_CHAR,
) -> int:

    if not skill_path.is_file():
        print(
            f"ERROR: skill file not found: {skill_path}",
            file=sys.stderr,
        )
        return 2

    with skill_path.open(encoding="utf-8") as fh:
        skill_text = fh.read()


    prefix = extract_stable_prefix(skill_text)


    volatile_violations = check_volatile(prefix)


    token_count = approx_tokens(prefix, tokens_per_char)
    length_ok = token_count >= _MIN_TOKENS


    current_hash = sha256_of(prefix)
    baseline_data = read_baseline(baseline_path)
    stored_hash = baseline_data.get("stable_prefix_sha256", "")
    stored_version = baseline_data.get("cache_prefix_version", "")


    version_match = _VERSION_RE.search(skill_text)
    current_version = version_match.group(1) if version_match else ""

    hash_changed = bool(stored_hash) and current_hash != stored_hash
    version_bumped = bool(current_version) and current_version != stored_version

    if fix:
        write_baseline(
            baseline_path,
            {
                "stable_prefix_sha256": current_hash,
                "cache_prefix_version": current_version,
                "note": (
                    "Written by check_cache_prefix.py --fix.  "
                    "Commit this file together with any stable-prefix changes."
                ),
            },
        )
        print(
            f"check_cache_prefix: baseline updated "
            f"(hash={current_hash[:12]}…, version={current_version or 'unset'})."
        )
        return 0


    if not stored_hash:
        write_baseline(
            baseline_path,
            {
                "stable_prefix_sha256": current_hash,
                "cache_prefix_version": current_version,
                "note": (
                    "Auto-created on first run by check_cache_prefix.py.  "
                    "Commit this file."
                ),
            },
        )
        print(
            f"check_cache_prefix: baseline created "
            f"(hash={current_hash[:12]}…).  Commit scripts/.cache_prefix_baseline."
        )


    errors: list[str] = []

    errors.extend(volatile_violations)

    if not length_ok:
        errors.append(
            f"stable prefix too short: ~{token_count} tokens "
            f"(minimum {_MIN_TOKENS} for Opus 4.8 cache engagement); "
            f"prefix is {len(prefix)} chars"
        )

    if hash_changed and not version_bumped:
        errors.append(
            f"stable-prefix content changed (hash {stored_hash[:12]}… → "
            f"{current_hash[:12]}…) without a CACHE_PREFIX_VERSION bump — "
            "this would silently invalidate the cache fleet-wide.  "
            "Either revert the change or bump CACHE_PREFIX_VERSION in the skill "
            "file and re-run with --fix."
        )

    if errors:
        print(
            f"check_cache_prefix: {len(errors)} violation(s):",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  FAIL  {err}", file=sys.stderr)
        return 1


    print(
        f"check_cache_prefix: OK — "
        f"~{token_count} tokens in stable prefix "
        f"(min {_MIN_TOKENS}); no volatile tokens; hash stable "
        f"({current_hash[:12]}…)."
    )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_cache_prefix",
        description='check_cache_prefix.py — enforce ADR 0006 static cache-prefix invariants.\n\nThe DasLab dispatch preamble (~27 KB) lives before the ``cache_control``\nbreakpoint and must remain byte-stable across agents, waves, and runs.  Any\nvolatile byte placed before the breakpoint invalidates the cache fleet-wide.\n\nThis script inspects the **designated stable-prefix region** of the\n``daslab-cycle`` skill file (the canonical definition of the preamble) and\nasserts three invariants (ADR 0006 §CI enforcement):\n\n    (a) Volatile-token check: no ISO timestamp, run-id/UUID pattern, ticket-id\n        pattern, or wave-counter appears inside the stable-prefix region.\n    (b) Version-bump gate: if the byte content of the stable-prefix region\n        differs from the stored baseline hash, the script fails unless a\n        ``CACHE_PREFIX_VERSION`` marker has been bumped in the skill file.\n    (c) Minimum-length check: the stable-prefix region must be at least 4096\n        tokens long (Opus 4.8 minimum cacheable prefix).  Token count is\n        approximated as ``len(text) / 4`` (conservative GPT-family estimate;\n        sufficient for a length gate).\n\nStable-prefix region definition\n---------------------------------\nThe stable-prefix region is the content of the skill file up to (but not\nincluding) the sentinel comment::\n\n    ## Prompt-cache prefix layout (ADR 0006 — W4)\n\nEverything from that heading onward is documentation *about* the boundary,\nnot subject to the byte-stability constraint.  Before that heading is the\noperational dispatch preamble: system text, triage rules, and dispatch steps 1–7\n(the invariant orchestration logic).  That region is checked.\n\nBaseline hash\n--------------\nThe baseline SHA-256 of the stable-prefix region is stored in::\n\n    scripts/.cache_prefix_baseline\n\nIf the file does not exist the script creates it and exits 0 (first-run\nbootstrapping).  On subsequent runs, a mismatch exits 1 unless the skill file\ncontains ``CACHE_PREFIX_VERSION:`` with a value that differs from the one in\nthe baseline file — a deliberate version bump.\n\nStandalone usage::\n\n    python3 scripts/check_cache_prefix.py [options]\n\n    --skill PATH   Path to the skill file (default: auto-detected).\n    --baseline PATH\n                   Path to the baseline hash file\n                   (default: scripts/.cache_prefix_baseline).\n    --fix          Write the current hash as the new baseline (bump version).\n    --tokens-per-char FLOAT\n                   Token-length approximation ratio (default: 0.25, i.e. 4\n                   chars per token — conservative GPT-family estimate).\n\nExit codes: 0 = all invariants pass, 1 = invariant violated, 2 = usage / IO.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--skill",
        type=Path,
        default=_DEFAULT_SKILL,
        help=(
            "Path to the daslab-cycle SKILL.md file "
            "(default: auto-detected from repo root)"
        ),
    )
    p.add_argument(
        "--baseline",
        type=Path,
        default=_DEFAULT_BASELINE,
        help=(
            "Path to the baseline hash file "
            "(default: scripts/.cache_prefix_baseline)"
        ),
    )
    p.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Write the current stable-prefix hash as the new baseline.  "
            "Use after a deliberate, reviewed stable-prefix change."
        ),
    )
    p.add_argument(
        "--tokens-per-char",
        type=float,
        default=_DEFAULT_TOKENS_PER_CHAR,
        metavar="RATIO",
        help=(
            "Token-length approximation ratio (default: 0.25 = 4 chars/token). "
            "Conservative; sufficient for the minimum-length gate."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run_checks(
        skill_path=args.skill,
        baseline_path=args.baseline,
        fix=args.fix,
        tokens_per_char=args.tokens_per_char,
    )


if __name__ == "__main__":
    sys.exit(main())
