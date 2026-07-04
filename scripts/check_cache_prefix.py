#!/usr/bin/env python3
"""check_cache_prefix.py — enforce ADR 0006 static cache-prefix invariants.

The DasLab dispatch preamble (~27 KB) lives before the ``cache_control``
breakpoint and must remain byte-stable across agents, waves, and runs.  Any
volatile byte placed before the breakpoint invalidates the cache fleet-wide.

This script inspects the **designated stable-prefix region** of the
``daslab-cycle`` skill file (the canonical definition of the preamble) and
asserts three invariants (ADR 0006 §CI enforcement):

    (a) Volatile-token check: no ISO timestamp, run-id/UUID pattern, ticket-id
        pattern, or wave-counter appears inside the stable-prefix region.
    (b) Version-bump gate: if the byte content of the stable-prefix region
        differs from the stored baseline hash, the script fails unless a
        ``CACHE_PREFIX_VERSION`` marker has been bumped in the skill file.
    (c) Minimum-length check: the stable-prefix region must be at least 4096
        tokens long (Opus 4.8 minimum cacheable prefix).  Token count is
        approximated as ``len(text) / 4`` (conservative GPT-family estimate;
        sufficient for a length gate).

Stable-prefix region definition
---------------------------------
The stable-prefix region is the content of the skill file up to (but not
including) the sentinel comment::

    ## Prompt-cache prefix layout (ADR 0006 — W4)

Everything from that heading onward is documentation *about* the boundary,
not subject to the byte-stability constraint.  Before that heading is the
operational dispatch preamble: system text, triage rules, and dispatch steps 1–7
(the invariant orchestration logic).  That region is checked.

Baseline hash
--------------
The baseline SHA-256 of the stable-prefix region is stored in::

    scripts/.cache_prefix_baseline

If the file does not exist the script creates it and exits 0 (first-run
bootstrapping).  On subsequent runs, a mismatch exits 1 unless the skill file
contains ``CACHE_PREFIX_VERSION:`` with a value that differs from the one in
the baseline file — a deliberate version bump.

Standalone usage::

    python3 scripts/check_cache_prefix.py [options]

    --skill PATH   Path to the skill file (default: auto-detected).
    --baseline PATH
                   Path to the baseline hash file
                   (default: scripts/.cache_prefix_baseline).
    --fix          Write the current hash as the new baseline (bump version).
    --tokens-per-char FLOAT
                   Token-length approximation ratio (default: 0.25, i.e. 4
                   chars per token — conservative GPT-family estimate).

Exit codes: 0 = all invariants pass, 1 = invariant violated, 2 = usage / IO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from _paths import ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sentinel that splits the stable-prefix region from the ADR-0006 docs section.
_STABLE_PREFIX_END_MARKER = "## Prompt-cache prefix layout (ADR 0006 — W4)"

# Default locations (resolved at runtime via ROOT from _paths.py).
_DEFAULT_SKILL = ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"
_DEFAULT_BASELINE = ROOT / "scripts" / ".cache_prefix_baseline"

# Minimum stable-prefix length in tokens (Opus 4.8 requirement).
# Source: claude-api skill shared/prompt-caching.md, "Minimum cacheable prefix" table —
# Opus 4.8, Opus 4.7, Opus 4.6, Opus 4.5, Haiku 4.5 → 4096 tokens.
# (1024 was the Sonnet-4.5-era value and under-enforced on Opus 4.8 — fixed DAS-1450.)
_MIN_TOKENS = 4096

# Characters-per-token ratio (conservative estimate; 4 chars ≈ 1 token).
_DEFAULT_TOKENS_PER_CHAR = 0.25

# Volatile-token patterns that must NOT appear in the stable prefix.
_VOLATILE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ISO 8601 timestamps: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS
    (
        "ISO timestamp",
        re.compile(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        ),
    ),
    # UUIDv4 pattern: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    (
        "UUID / run-id",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}"
            r"-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
        ),
    ),
    # Ticket IDs: DAS-<digits>
    (
        "ticket-id",
        re.compile(r"\bDAS-\d{4,}\b"),
    ),
    # Wave counters: wave-N or wave N (case-insensitive)
    (
        "wave-counter",
        re.compile(r"\bwave[-\s]\d+\b", re.IGNORECASE),
    ),
]

# Pattern for the CACHE_PREFIX_VERSION marker in the skill file.
_VERSION_RE = re.compile(r"^CACHE_PREFIX_VERSION:\s*(\S+)", re.MULTILINE)

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def extract_stable_prefix(skill_text: str) -> str:
    """Return the stable-prefix region (everything before the ADR-0006 section).

    If the sentinel is absent, the whole file is treated as the stable prefix
    (conservative: more text is checked, not less).
    """
    idx = skill_text.find(_STABLE_PREFIX_END_MARKER)
    if idx == -1:
        return skill_text
    return skill_text[:idx]


def sha256_of(text: str) -> str:
    """Return the hex SHA-256 of *text* encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approx_tokens(text: str, tokens_per_char: float) -> int:
    """Approximate token count using a fixed chars-per-token ratio."""
    return int(len(text) * tokens_per_char)


def check_volatile(prefix: str) -> list[str]:
    """Return a list of violation strings for volatile tokens in *prefix*."""
    violations: list[str] = []
    for label, pattern in _VOLATILE_PATTERNS:
        matches = pattern.findall(prefix)
        if matches:
            # Report up to 3 examples to keep output readable.
            examples = ", ".join(repr(m) for m in matches[:3])
            suffix = f" (and {len(matches) - 3} more)" if len(matches) > 3 else ""
            violations.append(
                f"volatile token [{label}] found in stable prefix: {examples}{suffix}"
            )
    return violations


def read_baseline(baseline_path: Path) -> dict[str, str]:
    """Load the baseline JSON file, or return an empty dict if absent."""
    if not baseline_path.exists():
        return {}
    with baseline_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_baseline(baseline_path: Path, data: dict[str, str]) -> None:
    """Persist *data* as the baseline JSON file."""
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with baseline_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Main checks
# ---------------------------------------------------------------------------


def run_checks(
    skill_path: Path,
    baseline_path: Path,
    *,
    fix: bool = False,
    tokens_per_char: float = _DEFAULT_TOKENS_PER_CHAR,
) -> int:
    """Run all ADR 0006 invariant checks.  Returns 0 (pass) or 1 (fail)."""
    # --- Load skill file ----------------------------------------------------
    if not skill_path.is_file():
        print(
            f"ERROR: skill file not found: {skill_path}",
            file=sys.stderr,
        )
        return 2

    with skill_path.open(encoding="utf-8") as fh:
        skill_text = fh.read()

    # --- Extract stable-prefix region ---------------------------------------
    prefix = extract_stable_prefix(skill_text)

    # --- (a) Volatile-token check -------------------------------------------
    volatile_violations = check_volatile(prefix)

    # --- (c) Minimum-length check -------------------------------------------
    token_count = approx_tokens(prefix, tokens_per_char)
    length_ok = token_count >= _MIN_TOKENS

    # --- (b) Version-bump / hash check --------------------------------------
    current_hash = sha256_of(prefix)
    baseline_data = read_baseline(baseline_path)
    stored_hash = baseline_data.get("stable_prefix_sha256", "")
    stored_version = baseline_data.get("cache_prefix_version", "")

    # Extract CACHE_PREFIX_VERSION from skill file (optional marker).
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

    # First-run bootstrapping: no stored hash yet.
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
        # Still check volatile and length even on first run.

    # --- Collect and report violations --------------------------------------
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

    # All clear.
    print(
        f"check_cache_prefix: OK — "
        f"~{token_count} tokens in stable prefix "
        f"(min {_MIN_TOKENS}); no volatile tokens; hash stable "
        f"({current_hash[:12]}…)."
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_cache_prefix",
        description=__doc__,
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


def main(argv: list[str] | None = None) -> int:  # noqa: UP007
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
