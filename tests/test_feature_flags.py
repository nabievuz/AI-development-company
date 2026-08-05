#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import feature_flags as ff


def test_real_config_matches_live_flag_state():


    expected = dict.fromkeys(ff.DEFAULTS, False)
    expected["organism_emit"] = True
    expected["ws_a_tool_bridge"] = True
    expected["ws_h_control_plane"] = True
    expected["ws_d_langfuse_lens"] = True
    expected["ws_b_agent_sdk_runner"] = True
    expected["ws_e_tenant_hardening"] = True
    expected["ws_g_proof"] = True
    expected["a2a_outbound"] = True
    expected["ws_c_langgraph_loop"] = True
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


    assert ff.load(tmp_path / "nope.yaml") == dict.fromkeys(ff.DEFAULTS, False)


def test_unknown_keys_are_ignored(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("dgox_emit: true\nbogus: true\n", encoding="utf-8")
    flags = ff.load(p)
    assert flags["dgox_emit"] is True and "bogus" not in flags


def test_empty_file_falls_back_off(tmp_path):
    p = tmp_path / "f.yaml"
    p.write_text("", encoding="utf-8")

    assert ff.load(p) == dict.fromkeys(ff.DEFAULTS, False)
