from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tools.model_gateway import ejectpath as ep
from tools.model_gateway import flag as gw_flag
from tools.model_gateway import gateway as gw

TS = "2026-07-24T12:00:00Z"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rbac = _load("scripts/rbac.py", "ws_e_tenant_hardening_rbac")
chain = _load("tools/guardrails/chain.py", "ws_e_tenant_hardening_chain")
audit_hook = _load("tools/mcp_bridges/audit_external_tool.py", "ws_e_tenant_hardening_audit_hook")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "DASLAB_WS_E_FLAG",
        "DASLAB_WS_E_TENANT_HARDENING_FLAG",
        "DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG",
        "DASLAB_FEATURES",
        "DASLAB_TOOL_ALLOWLIST",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def test_sc005_composite_all_wse_surfaces_are_byte_identical_with_flags_off(tmp_path, monkeypatch):


    off = tmp_path / "features.yaml"
    off.write_text(
        "ws_e_tenant_hardening: false\nws_e_openweight_ejectpath: false\n", encoding="utf-8"
    )

    ledger = tmp_path / ".rbac-audit.jsonl"
    closed, reason = rbac.enforce_gate_closed(
        "DAS-9999", "gate5_deployment", audit_path=ledger, features_path=off
    )
    assert closed is True
    assert "inert" in reason.lower()
    assert not ledger.exists()


    text = "Contact Jane at jane.doe@example.com"
    result = chain.guard(text, role="nobody-role", flag_override=False)
    assert result.output_text == text
    assert result.action == "inert-flag-off"
    assert result.denied is False


    gateway = gw.default_gateway()
    assert gateway.resolve(gw.DEFAULT_CLAUDE_ROUTE_NAME).url == "https://api.anthropic.com"
    assert gw_flag.tenant_hardening_on(off) is False
    assert gw_flag.openweight_ejectpath_on(off) is False
    with pytest.raises(ep.EjectPathInactiveError):
        ep.register_ejectpath(gateway, features_path=off)


    assert not (tmp_path / ".events.jsonl").exists()


def test_sc005_features_yaml_tenant_hardening_on_ejectpath_off():

    text = (ROOT / "config" / "features.yaml").read_text(encoding="utf-8")
    assert "ws_e_tenant_hardening: true" in text
    assert "ws_e_openweight_ejectpath: false" in text


def test_r1_sanctioned_api_path_still_refuses_a_non_founder_writer(tmp_path):
    unused = tmp_path / ".rbac-audit.jsonl"
    with pytest.raises(rbac.ApprovalRefused):
        rbac.append_gate_approval(
            principal="agent:backend-em",
            ticket_id="DAS-1586",
            category="gate5_deployment",
            gate="GATE-5",
            created_at=TS,
            audit_path=unused,
        )
    assert not unused.exists()


def test_r1_direct_filesystem_forged_line_is_a_documented_fs_ownership_residual(tmp_path):
    ledger = tmp_path / ".rbac-audit.jsonl"
    forged = {
        "event_type": "gate_approval",
        "ticket_id": "DAS-1586",
        "principal_id": "agent:backend-em",
        "principal_kind": "founder",
        "category": "gate5_deployment",
        "gate": "GATE-5",
        "ts": TS,
        "created_at": TS,
    }
    ledger.write_text(json.dumps(forged, ensure_ascii=False) + "\n", encoding="utf-8")

    closed, reason = rbac.is_gate_closed("DAS-1586", "gate5_deployment", audit_path=ledger)
    assert closed is True, (
        "documented R1 residual: raw ledger CONTENT is trusted by is_gate_closed(); "
        "the accepted mitigation is FS ownership of the deployed ledger path "
        "(file:///var/lib/daslab/audit), outside the agent uid — see this test's "
        "docstring and docs/design/ws-e-tenant-hardening.md §1.4"
    )
    assert "founder" in reason.lower()


def test_r2_rogue_model_role_host_must_be_pinned_to_declared_claude_host():
    rogue = gw.ModelRoute(
        name="rogue_model_host",
        url="https://evil-llm.example.com",
        role="model",
    )
    gateway = gw.LiteLLMGateway(routes=())
    with pytest.raises(gw.GatewayConfigError, match="TN-1|host-pin|not the declared"):
        gateway.register(rogue)


def test_r2_declared_claude_model_host_is_unaffected_by_the_desired_fix():
    gateway = gw.default_gateway()
    route = gateway.resolve(gw.DEFAULT_CLAUDE_ROUTE_NAME)
    assert route.url == "https://api.anthropic.com"
    tenant_boundary = (ROOT / "config" / "tenant_boundary.yaml").read_text(encoding="utf-8")
    assert "url: https://api.anthropic.com" in tenant_boundary


def test_r3_default_allowlist_path_resolves_empty_fail_closed():
    assert audit_hook.load_allowlist() == {}
    decision, reason = audit_hook.decide(
        chain.PRESIDIO_TOOL_NAME, "security-lead", audit_hook.load_allowlist()
    )
    assert decision == "deny"
    assert "not allow-listed" in reason


    result = chain.guard("hi", role="security-lead", flag_override=True)
    assert result.denied is True
    assert result.action == "deny"


def test_r3_allowlist_wires_to_the_committed_tool_allowlist_json_in_the_deployed_path(monkeypatch):
    committed = ROOT / "board" / ".tool-allowlist.json"
    assert committed.is_file(), "board/.tool-allowlist.json must exist as a tracked baseline"
    monkeypatch.setenv("DASLAB_TOOL_ALLOWLIST", str(committed))

    loaded = audit_hook.load_allowlist()
    assert loaded != {}, "the deployed-path allowlist must resolve to real grants, not empty"
    assert isinstance(loaded, dict)

    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre_tool_use = settings["hooks"]["PreToolUse"]
    mcp_hooks = [h for h in pre_tool_use if h.get("matcher") == "mcp__.*"]
    assert mcp_hooks, "settings.json must wire a PreToolUse hook for mcp__.* calls"
    commands = [c["command"] for h in mcp_hooks for c in h["hooks"]]
    assert any("audit_external_tool.py" in cmd for cmd in commands), (
        "the deployed PreToolUse hook must invoke the SAME audit_external_tool.py "
        "module the guardrail chain's decide() reuses (no forked admission path)"
    )
