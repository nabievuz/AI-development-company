#!/usr/bin/env python3
"""tests/test_check_loop_mode.py — loop stays OFF in P1 (PRD §6 / RFC-001 / ADR-001)."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_loop_mode as lm  # noqa: E402  (import after path manipulation)

REAL_CONFIG = REPO_ROOT / "config" / "loop.yaml"


def _cfg(**over) -> dict:
    base = {"mode": "shadow", "auto_apply": False, "ladder": ["shadow", "measured", "limited_live", "full"]}
    base.update(over)
    return base


def test_real_loop_config_is_off():
    cfg = yaml.safe_load(REAL_CONFIG.read_text(encoding="utf-8"))
    assert lm.check_loop(cfg) == []
    # The loop ships in shadow mode; catch a silent shadow->measured drift
    assert cfg["mode"] == "shadow"
    assert cfg["auto_apply"] is False


def test_full_mode_rejected():
    assert any("live" in p for p in lm.check_loop(_cfg(mode="full")))


def test_limited_live_mode_rejected():
    assert any("live" in p for p in lm.check_loop(_cfg(mode="limited_live")))


def test_auto_apply_true_rejected():
    assert any("auto_apply" in p for p in lm.check_loop(_cfg(auto_apply=True)))


def test_mode_off_ladder_rejected():
    assert any("ladder" in p for p in lm.check_loop(_cfg(mode="turbo")))


def test_measured_mode_allowed():
    assert lm.check_loop(_cfg(mode="measured")) == []


def test_main_exit_0_on_real_config():
    assert lm.main(["--config", str(REAL_CONFIG)]) == 0


def test_main_exit_1_on_unsafe(tmp_path):
    p = tmp_path / "loop.yaml"
    p.write_text(yaml.safe_dump(_cfg(mode="full", auto_apply=True)), encoding="utf-8")
    assert lm.main(["--config", str(p)]) == 1


def test_main_exit_2_on_missing(tmp_path):
    assert lm.main(["--config", str(tmp_path / "nope.yaml")]) == 2
