#!/usr/bin/env python3
"""tests/test_feature_flags.py — latent-machine feature flags (ADR-0019 / ADR-0002, P10)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import feature_flags as ff  # noqa: E402  (import after path manipulation)


def test_real_config_matches_live_flag_state():
    # organism_emit was ACTIVATED 2026-07-03 (Founder-authorized): its consumers
    # (dispatch_emitter, cost_ledger, check_spans, snapshot_evidence) are now live,
    # so the real config carries it ON. The other latent flags remain OFF (no live
    # consumer). DEFAULTS stay all-off (see the missing/empty-file tests below).
    # heartbeat_enabled was added by DAS-1475 (WS4 HEARTBEAT, ADR-0027 SI-7) and
    # ships default OFF — Founder flip-only after a >=3-day clean shadow window.
    # Assert the live contract against DEFAULTS (the SSOT) so adding a new latent
    # flag (e.g. the MUSTAQIL ws_* keys, DAS-1543) does not break this test: live
    # config = all DEFAULTS OFF except organism_emit, which is ON.
    expected = dict.fromkeys(ff.DEFAULTS, False)
    expected["organism_emit"] = True
    assert ff.load() == expected


def test_enabled_reads_a_true_flag(tmp_path):
    p = tmp_path / "features.yaml"
    p.write_text(
        "dgox_emit: true\nt4_t7_governors: false\norganism_emit: true\n",
        encoding="utf-8",
    )
    assert ff.enabled("dgox_emit", p) is True
    assert ff.enabled("t4_t7_governors", p) is False
    assert ff.enabled("organism_emit", p) is True


def test_missing_file_falls_back_off(tmp_path):
    # A missing file falls back to DEFAULTS (all OFF) — derive from the SSOT so new
    # flags do not break this.
    assert ff.load(tmp_path / "nope.yaml") == dict.fromkeys(ff.DEFAULTS, False)


def test_unknown_keys_are_ignored(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("dgox_emit: true\nbogus: true\n", encoding="utf-8")
    flags = ff.load(p)
    assert flags["dgox_emit"] is True and "bogus" not in flags


def test_empty_file_falls_back_off(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("", encoding="utf-8")
    # An empty file falls back to DEFAULTS (all OFF) — derive from the SSOT.
    assert ff.load(p) == dict.fromkeys(ff.DEFAULTS, False)
