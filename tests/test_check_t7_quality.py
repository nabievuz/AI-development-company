#!/usr/bin/env python3
"""tests/test_check_t7_quality.py — T7 hard-blocker validator (R-3 / ADR-002).

Proves: the real rubric is intact; weights cannot be silently lowered; the
weighted score math is correct; and any T7 regression vs baseline fails closed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_t7_quality as t7  # noqa: E402  (import after path manipulation)

REAL_RUBRIC = REPO_ROOT / "config" / "t7_rubric.yaml"


def _canonical_rubric() -> dict:
    return {
        "dimensions": {
            "correctness": {"weight": 0.30},
            "evidence_factuality": {"weight": 0.20},
            "tests": {"weight": 0.15},
            "security": {"weight": 0.15},
            "completeness": {"weight": 0.10},
            "maintainability": {"weight": 0.10},
        },
        "constraint": {"immutable": True, "max_quality_drop": 0, "rule": "max_quality_drop = 0"},
    }


# --------------------------------------------------------------------------- #
# Rubric integrity
# --------------------------------------------------------------------------- #

def test_real_rubric_is_intact():
    rubric = t7.load_rubric(REAL_RUBRIC)
    assert t7.check_rubric_integrity(rubric) == []


def test_weights_must_sum_to_one():
    bad = _canonical_rubric()
    bad["dimensions"]["correctness"]["weight"] = 0.50  # now sums to 1.20
    problems = t7.check_rubric_integrity(bad)
    assert any("sum" in p for p in problems)


def test_silently_lowered_weight_is_caught():
    bad = _canonical_rubric()
    # Lower correctness, raise maintainability so the sum still equals 1.00.
    bad["dimensions"]["correctness"]["weight"] = 0.20
    bad["dimensions"]["maintainability"]["weight"] = 0.20
    problems = t7.check_rubric_integrity(bad)
    assert any("!= immutable" in p for p in problems)


def test_missing_dimension_is_caught():
    bad = _canonical_rubric()
    del bad["dimensions"]["security"]
    assert any("missing dimension 'security'" in p for p in t7.check_rubric_integrity(bad))


def test_non_immutable_rubric_is_caught():
    bad = _canonical_rubric()
    bad["constraint"]["immutable"] = False
    assert any("immutable" in p for p in t7.check_rubric_integrity(bad))


def test_rule_must_state_max_quality_drop_zero():
    bad = _canonical_rubric()
    bad["constraint"]["rule"] = "quality may wander"
    assert any("max_quality_drop" in p for p in t7.check_rubric_integrity(bad))


def test_relaxed_nonzero_drop_is_caught():
    bad = _canonical_rubric()
    bad["constraint"]["max_quality_drop"] = 0.02
    bad["constraint"]["rule"] = "max_quality_drop relaxed to 0.02 per RFC-001 exploration budget"
    assert any("max_quality_drop must be 0" in p for p in t7.check_rubric_integrity(bad))


def test_missing_drop_field_is_caught():
    bad = _canonical_rubric()
    del bad["constraint"]["max_quality_drop"]
    assert any("max_quality_drop must be 0" in p for p in t7.check_rubric_integrity(bad))


def test_bool_drop_is_caught():
    bad = _canonical_rubric()
    bad["constraint"]["max_quality_drop"] = False
    assert any("max_quality_drop must be 0" in p for p in t7.check_rubric_integrity(bad))


# --------------------------------------------------------------------------- #
# Weighted score + no-degradation gate
# --------------------------------------------------------------------------- #

def test_weighted_score_all_ones_is_one():
    rubric = _canonical_rubric()
    perfect = dict.fromkeys(t7.EXPECTED_DIMENSIONS, 1.0)
    assert t7.weighted_score(rubric, perfect) == pytest.approx(1.0)


def test_no_degradation_equal_is_ok():
    rubric = _canonical_rubric()
    scores = dict.fromkeys(t7.EXPECTED_DIMENSIONS, 0.9)
    assert t7.check_no_degradation(rubric, scores, scores, 0.0) == []


def test_any_drop_fails_with_zero_max_drop():
    rubric = _canonical_rubric()
    base = dict.fromkeys(t7.EXPECTED_DIMENSIONS, 1.0)
    worse = dict(base, correctness=0.99)  # tiny drop on a 0.30-weight dim
    assert t7.check_no_degradation(rubric, base, worse, 0.0)


def test_improvement_is_ok():
    rubric = _canonical_rubric()
    base = dict.fromkeys(t7.EXPECTED_DIMENSIONS, 0.8)
    better = dict.fromkeys(t7.EXPECTED_DIMENSIONS, 0.95)
    assert t7.check_no_degradation(rubric, base, better, 0.0) == []


# --------------------------------------------------------------------------- #
# CLI / exit codes
# --------------------------------------------------------------------------- #

def test_main_exit_0_on_real_rubric():
    assert t7.main(["--rubric", str(REAL_RUBRIC)]) == 0


def test_main_exit_2_on_missing_rubric(tmp_path):
    assert t7.main(["--rubric", str(tmp_path / "nope.yaml")]) == 2


def test_main_exit_1_on_drifted_rubric(tmp_path):
    bad = _canonical_rubric()
    bad["dimensions"]["correctness"]["weight"] = 0.99
    p = tmp_path / "rubric.yaml"
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    assert t7.main(["--rubric", str(p)]) == 1


def test_main_exit_1_on_regression(tmp_path):
    scores = {
        "baseline": dict.fromkeys(t7.EXPECTED_DIMENSIONS, 1.0),
        "candidate": dict(dict.fromkeys(t7.EXPECTED_DIMENSIONS, 1.0), tests=0.5),
    }
    p = tmp_path / "scores.json"
    p.write_text(json.dumps(scores), encoding="utf-8")
    assert t7.main(["--rubric", str(REAL_RUBRIC), "--scores", str(p)]) == 1


def test_main_exit_0_with_clean_scores(tmp_path):
    scores = {
        "baseline": dict.fromkeys(t7.EXPECTED_DIMENSIONS, 0.9),
        "candidate": dict.fromkeys(t7.EXPECTED_DIMENSIONS, 0.95),
    }
    p = tmp_path / "scores.yaml"
    p.write_text(yaml.safe_dump(scores), encoding="utf-8")
    assert t7.main(["--rubric", str(REAL_RUBRIC), "--scores", str(p)]) == 0
