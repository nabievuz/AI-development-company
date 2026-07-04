#!/usr/bin/env python3
"""tests/test_gate_promotion.py — warn→enforce promotion controller (ADR-0020 / P1b).

These tests ARE the adversarial verification the plan requires: they assert the classifier
cannot be gamed into a false green. The grid test proves there is no (samples, fp, override)
input that reaches ENFORCE without meeting all three criteria, and that an unmeasured gate is
ALWAYS skipped (never green).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gate_promotion as gp  # noqa: E402  (import after path manipulation)


def test_zero_or_negative_samples_always_skipped():
    for fp in (None, 0.0, 0.05, 0.10, 0.9):
        for ov in (None, 0.0, 0.01, 0.05, 0.9):
            assert gp.classify(0, fp, ov) == gp.SKIPPED
            assert gp.classify(-5, fp, ov) == gp.SKIPPED


def test_enforce_requires_ALL_criteria_adversarial_grid():
    sample_vals = (0, 1, 29, 30, 31, 100)
    rate_vals = (None, -0.1, 0.0, 0.05, 0.06, 0.10, 0.11, 0.5)
    for s in sample_vals:
        for fp in rate_vals:
            for ov in rate_vals:
                if gp.classify(s, fp, ov) == gp.ENFORCE:
                    assert s >= gp.MIN_SAMPLES
                    assert fp is not None and 0 <= fp <= gp.MAX_FP_RATE
                    assert ov is not None and 0 <= ov <= gp.MAX_OVERRIDE_RATE


def test_qualified_gate_enforces():
    assert gp.classify(30, 0.10, 0.05) == gp.ENFORCE
    assert gp.classify(100, 0.0, 0.0) == gp.ENFORCE


def test_measured_but_unqualified_is_warn_never_enforce():
    assert gp.classify(30, 0.11, 0.0) == gp.WARN   # fp too high
    assert gp.classify(30, 0.0, 0.06) == gp.WARN   # override too high
    assert gp.classify(29, 0.0, 0.0) == gp.WARN    # too few samples
    assert gp.classify(50, None, 0.0) == gp.WARN   # missing safety metric


def test_real_registry_gates_all_skipped_no_data():
    # no metrics/gate_metrics.json snapshot exists → every registry gate is honestly skipped.
    st = gp.statuses()
    assert st, "registry should list gates"
    assert all(v == gp.SKIPPED for v in st.values())
    assert gp.ENFORCE not in st.values()  # nothing falsely green


def test_reporter_runs_clean():
    assert gp.main([]) == 0
