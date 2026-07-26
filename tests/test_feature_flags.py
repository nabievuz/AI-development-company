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
    # ws_a_tool_bridge was ACTIVATED 2026-07-26 (Founder-authorized): the WS-A
    # ecosystem tool bridge + deny-all/allow-list egress (Q5) landed, and the
    # PreToolUse hook (audit_external_tool.py) enforces the compiled
    # board/.tool-allowlist.json (wired via DASLAB_TOOL_ALLOWLIST). Core infra
    # MCPs (ArcRift/obsidian) are carved out so the Persistent Memory Law is
    # never denied; ecosystem bridges are governed per role.
    # Assert the live contract against DEFAULTS (the SSOT) so adding a new latent
    # flag (e.g. the MUSTAQIL ws_* keys, DAS-1543) does not break this test: live
    # ws_h_control_plane was ACTIVATED 2026-07-26 (Founder-authorized): the WS-H
    # control plane is deployed on the tenant box as a loopback-only systemd user
    # unit (daslab-control-plane, 127.0.0.1:8899) with Founder-only RBAC
    # (DASLAB_CP_RBAC vault). Serves requests; dispatches nothing on its own (CP-5).
    # config = all DEFAULTS OFF except organism_emit + ws_a_tool_bridge +
    # ws_h_control_plane, which are ON.
    # ws_d_langfuse_lens was ACTIVATED 2026-07-26 (Founder-authorized): self-host
    # Langfuse v3 is deployed in-tenant on the tenant box (docker compose, loopback
    # 127.0.0.1:3000, OTLP ingestion verified); the read-side exporter is live
    # behind the flag. TN-1 boundary holds (check_in_tenant OK).
    # ws_b_agent_sdk_runner was ACTIVATED 2026-07-26 (Founder-authorized): the
    # claude-agent-sdk is installed and the headless runner authenticates via the
    # Claude account OAuth profile (a live query returned a real reply); ADR-0009
    # admission (scripts/ws_b_admission.py) wraps every dispatch. Additive to
    # /daslab-cycle; flag-on == flag-off DECISIONS.
    # ws_e_tenant_hardening was ACTIVATED 2026-07-26 (Founder-authorized): the
    # internal-only boundary (Q10) is enforced end-to-end — RBAC founder-only
    # double-lock, LiteLLM gateway boundary, TN-1 check_in_tenant, read-only
    # in-tenant SIEM export. The nested ws_e_openweight_ejectpath stays OFF (an
    # explicit-decision-only sub-flag, not in DEFAULTS).
    expected = dict.fromkeys(ff.DEFAULTS, False)
    expected["organism_emit"] = True
    expected["ws_a_tool_bridge"] = True
    expected["ws_h_control_plane"] = True
    expected["ws_d_langfuse_lens"] = True
    expected["ws_b_agent_sdk_runner"] = True
    expected["ws_e_tenant_hardening"] = True
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
