#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)


EXPECTED_DIMENSIONS: dict[str, float] = {
    "correctness": 0.30,
    "evidence_factuality": 0.20,
    "tests": 0.15,
    "security": 0.15,
    "completeness": 0.10,
    "maintainability": 0.10,
}


def load_rubric(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check_rubric_integrity(rubric: dict) -> list[str]:
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


    mqd = constraint.get("max_quality_drop")
    if isinstance(mqd, bool) or not isinstance(mqd, int | float) or mqd != 0:
        problems.append(f"constraint.max_quality_drop must be 0 (strict); got {mqd!r}")
    if "max_quality_drop" not in str(constraint.get("rule", "")):
        problems.append("constraint.rule must document the max_quality_drop policy")
    return problems


def weighted_score(rubric: dict, scores: dict[str, float]) -> float:
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
    base = weighted_score(rubric, baseline)
    cand = weighted_score(rubric, candidate)
    if (base - cand) > max_drop + 1e-12:
        return [
            f"T7 regression: candidate {cand:.4f} < baseline {base:.4f} "
            f"(max allowed drop {max_drop})"
        ]
    return []


def load_scores(path: Path) -> tuple[dict, dict]:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if path.suffix in (".yaml", ".yml") else json.loads(raw)
    data = data or {}
    return data.get("baseline", {}) or {}, data.get("candidate", {}) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_t7_quality.py — T7 weighted-quality hard blocker.')
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
