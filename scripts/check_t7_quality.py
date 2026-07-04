#!/usr/bin/env python3
"""check_t7_quality.py — T7 weighted-quality hard blocker.

T7 is the IMMUTABLE quality constraint every tuning change is subordinate to.
This validator has two jobs:

1.  Rubric integrity (always — the CI default). ``config/t7_rubric.yaml`` is the
    SSOT. The six weighted dimensions must each be present with a numeric weight,
    the weights must sum to 1.00, the canonical weights must not have been
    silently changed, and the rubric must declare itself immutable with a
    ``max_quality_drop = 0`` rule. A drifted/relaxed rubric fails the build — this
    is how "T7 weights cannot be silently lowered" is enforced as code.

2.  No-degradation gate (when ``--scores`` is given). Given baseline and candidate
    per-dimension scores, compute the weighted T7 score for each and FAIL if the
    candidate drops below baseline by more than ``--max-drop`` (default 0). This is
    the hard blocker on a T7 regression.

A change to the rubric itself is governance/policy → never-auto-approve (QONUN-5);
this validator only proves the rubric is intact, it does not authorise edits.

Exit codes: 0 = clean, 1 = rubric drift or T7 regression, 2 = usage/IO error.

Usage:
    python3 scripts/check_t7_quality.py
    python3 scripts/check_t7_quality.py --scores experiments/t7_scores.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

# The immutable canonical rubric. Weights MUST sum to 1.00.
EXPECTED_DIMENSIONS: dict[str, float] = {
    "correctness": 0.30,
    "evidence_factuality": 0.20,
    "tests": 0.15,
    "security": 0.15,
    "completeness": 0.10,
    "maintainability": 0.10,
}


def load_rubric(path: Path) -> dict:
    """Parse the T7 rubric YAML into a dict (empty dict if the file is empty)."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_rubric_integrity(rubric: dict) -> list[str]:
    """Return a list of problems with the rubric SSOT; empty == intact."""
    problems: list[str] = []
    dims = rubric.get("dimensions")
    if not isinstance(dims, dict):
        return ["rubric has no 'dimensions' mapping"]

    for name in EXPECTED_DIMENSIONS:
        if name not in dims:
            problems.append(f"missing dimension '{name}'")
    for name, spec in dims.items():
        if name not in EXPECTED_DIMENSIONS:
            problems.append(f"unexpected dimension '{name}' (rubric is immutable)")
        weight = (spec or {}).get("weight")
        if not isinstance(weight, int | float) or isinstance(weight, bool):
            problems.append(f"dimension '{name}' weight must be numeric; got {weight!r}")

    weights = [
        float((spec or {}).get("weight"))
        for spec in dims.values()
        if isinstance((spec or {}).get("weight"), int | float)
        and not isinstance((spec or {}).get("weight"), bool)
    ]
    total = sum(weights)
    if abs(total - 1.0) > 1e-6:
        problems.append(f"weights sum to {total}, must be 1.00")

    for name, want in EXPECTED_DIMENSIONS.items():
        got = (dims.get(name) or {}).get("weight")
        if isinstance(got, int | float) and not isinstance(got, bool) and abs(float(got) - want) > 1e-9:
            problems.append(f"dimension '{name}' weight {got} != immutable {want}")

    constraint = rubric.get("constraint", {}) or {}
    if constraint.get("immutable") is not True:
        problems.append("constraint.immutable must be true")
    # The zero-drop policy is enforced from a STRUCTURED numeric field, not by a
    # substring test on the free-text rule (which mentions "T7"/"GATE-6" and would
    # fool a digit check, and accept a relaxed "0.02").
    mqd = constraint.get("max_quality_drop")
    if isinstance(mqd, bool) or not isinstance(mqd, int | float) or mqd != 0:
        problems.append(f"constraint.max_quality_drop must be 0 (strict); got {mqd!r}")
    if "max_quality_drop" not in str(constraint.get("rule", "")):
        problems.append("constraint.rule must document the max_quality_drop policy")
    return problems


def weighted_score(rubric: dict, scores: dict[str, float]) -> float:
    """Weighted T7 score = sum(weight_i * dimension_score_i) over the rubric."""
    dims = rubric["dimensions"]
    return sum(
        float(dims[name]["weight"]) * float(scores.get(name, 0.0)) for name in dims
    )


def check_no_degradation(
    rubric: dict,
    baseline: dict[str, float],
    candidate: dict[str, float],
    max_drop: float,
) -> list[str]:
    """Return a problem if candidate T7 drops below baseline by more than max_drop."""
    base = weighted_score(rubric, baseline)
    cand = weighted_score(rubric, candidate)
    if (base - cand) > max_drop + 1e-12:
        return [
            f"T7 regression: candidate {cand:.4f} < baseline {base:.4f} "
            f"(max allowed drop {max_drop})"
        ]
    return []


def load_scores(path: Path) -> tuple[dict, dict]:
    """Load {baseline:{dim:score}, candidate:{dim:score}} from YAML or JSON."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if path.suffix in (".yaml", ".yml") else json.loads(raw)
    data = data or {}
    return data.get("baseline", {}) or {}, data.get("candidate", {}) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rubric", type=Path, default=ROOT / "config" / "t7_rubric.yaml")
    ap.add_argument(
        "--scores",
        type=Path,
        default=None,
        help="YAML/JSON with {baseline:{dim:score}, candidate:{dim:score}}",
    )
    ap.add_argument(
        "--max-drop",
        type=float,
        default=0.0,
        help="maximum allowed T7 drop (default 0 — immutable hard constraint)",
    )
    args = ap.parse_args(argv)

    if not args.rubric.is_file():
        sys.stderr.write(f"ERROR: rubric not found: {args.rubric}\n")
        return 2
    rubric = load_rubric(args.rubric)

    problems = check_rubric_integrity(rubric)

    if args.scores is not None:
        if not args.scores.is_file():
            sys.stderr.write(f"ERROR: scores file not found: {args.scores}\n")
            return 2
        if problems:
            # A drifted rubric must not be used to score: fail before comparing.
            sys.stderr.write("FAIL: rubric drift — refusing to score against it.\n")
        else:
            baseline, candidate = load_scores(args.scores)
            problems += check_no_degradation(rubric, baseline, candidate, args.max_drop)

    if problems:
        sys.stderr.write("FAIL: T7 quality check:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1

    tail = "and no degradation." if args.scores else "(no scores supplied)."
    print(f"OK: T7 rubric intact — weights sum 1.00, immutable {tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
