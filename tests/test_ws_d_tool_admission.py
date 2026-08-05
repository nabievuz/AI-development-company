from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGES = ROOT / "tools" / "mcp_bridges"


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_gen_subagents():
    sys.path.insert(0, str(ROOT / "scripts"))
    import gen_subagents

    return gen_subagents


hook = _load("tools/mcp_bridges/audit_external_tool.py", "audit_external_tool")
promptfoo = _load("tools/mcp_bridges/promptfoo_tool_bridge.py", "promptfoo_tool_bridge")
agentshield = _load("tools/mcp_bridges/agentshield_tool_bridge.py", "agentshield_tool_bridge")
presidio = _load("tools/mcp_bridges/presidio_tool_bridge.py", "presidio_tool_bridge")


def test_compiled_allowlist_grants_only_designed_roles():
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    assert committed["mcp__promptfoo__run_eval"] == ["qa-eng", "qa-lead"]
    assert committed["mcp__agentshield__scan_action"] == ["security-lead"]
    assert committed["mcp__presidio__analyze_text"] == ["security-lead"]


def test_compiled_allowlist_matches_overlays_no_drift():
    gen = _load_gen_subagents()
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    regenerated = gen.compile_tool_allowlist()
    assert committed == regenerated


def test_compiled_allowlist_has_no_wildcard_roles():
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    for value in committed.values():
        assert value != "*"
        assert "*" not in value


def test_non_allowlisted_eval_tool_refused_by_same_decide():
    allow = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())

    assert hook.decide("mcp__promptfoo__run_eval", "qa-eng", allow)[0] == "allow"
    assert hook.decide("mcp__agentshield__scan_action", "security-lead", allow)[0] == "allow"
    assert hook.decide("mcp__presidio__analyze_text", "security-lead", allow)[0] == "allow"

    assert hook.decide("mcp__promptfoo__run_eval", "backend-eng-1", allow)[0] == "deny"
    assert hook.decide("mcp__agentshield__scan_action", "backend-eng-1", allow)[0] == "deny"
    assert hook.decide("mcp__presidio__analyze_text", "backend-eng-1", allow)[0] == "deny"


def test_tool_present_in_mcp_json_but_no_overlay_denies_every_role():
    allow = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    assert hook.decide("mcp__presidio__some_other_tool", "security-lead", allow)[0] == "deny"


def test_mcp_json_wires_all_three_sidecars():
    mcp_config = json.loads((ROOT / ".mcp.json").read_text())
    servers = mcp_config["mcpServers"]
    for name, script in (
        ("promptfoo", "promptfoo_tool_bridge.py"),
        ("agentshield", "agentshield_tool_bridge.py"),
        ("presidio", "presidio_tool_bridge.py"),
    ):
        assert name in servers
        assert script in servers[name]["args"][-1]


def _features(tmp_path: Path, on: bool) -> Path:
    p = tmp_path / "features.yaml"
    p.write_text(f"ws_a_tool_bridge: {'true' if on else 'false'}\n", encoding="utf-8")
    return p


def _run_hook(
    event: dict, env_extra: dict, features: Path | None = None
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    cmd = [sys.executable, str(BRIDGES / "audit_external_tool.py")]
    if features is not None:
        cmd += ["--features", str(features)]
    return subprocess.run(
        cmd,
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def test_every_decision_is_audited_allow_and_deny(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    allow_file = tmp_path / "al.json"
    allow_file.write_text(json.dumps({"mcp__promptfoo__run_eval": ["qa-eng"]}))

    r_allow = _run_hook(
        {"tool_name": "mcp__promptfoo__run_eval", "agent": "qa-eng"},
        {
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(allow_file),
        },
        features=_features(tmp_path, on=True),
    )
    assert json.loads(r_allow.stdout) == {}

    r_deny = _run_hook(
        {"tool_name": "mcp__presidio__analyze_text", "agent": "backend-eng-1"},
        {
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(allow_file),
        },
        features=_features(tmp_path, on=True),
    )
    deny_out = json.loads(r_deny.stdout)
    assert deny_out["hookSpecificOutput"]["permissionDecision"] == "deny"

    lines = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert len(lines) == 2
    assert {rec["decision"] for rec in lines} == {"allow", "deny"}
    tools_audited = {rec["tool"] for rec in lines}
    assert tools_audited == {"mcp__promptfoo__run_eval", "mcp__presidio__analyze_text"}


def test_audit_skip_denied_malformed_event(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    r = subprocess.run(
        [
            sys.executable,
            str(BRIDGES / "audit_external_tool.py"),
            "--features",
            str(_features(tmp_path, on=True)),
        ],
        input="not json",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert r.returncode == 2
    assert audit_log.exists()


def test_settings_binding_present_covers_these_tools_too():
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    pre = settings["hooks"]["PreToolUse"]
    entry = next(e for e in pre if e.get("matcher") == "mcp__.*")
    assert "audit_external_tool.py" in entry["hooks"][0]["command"]
    import re

    matcher = re.compile(entry["matcher"])
    for tool in (
        "mcp__promptfoo__run_eval",
        "mcp__agentshield__scan_action",
        "mcp__presidio__analyze_text",
    ):
        assert matcher.match(tool)


def test_presidio_never_echoes_raw_pii():
    out = presidio.analyze_text("contact me at jane.doe@example.com or +1 415 555 0100")
    assert "jane.doe@example.com" not in out
    assert "415 555 0100" not in out
    assert "[REDACTED:pii]" in out
    assert "EMAIL" in out
    assert "PHONE" in out


def test_presidio_never_echoes_raw_secret():
    out = presidio.analyze_text("here is a key sk-ant-api03-" + "x" * 40)
    assert "sk-ant-api03-" not in out
    assert "API_KEY" in out


def test_presidio_output_passes_through_redact_then_truncate_cap():
    out = presidio.analyze_text("a" * 10_000)
    assert len(out) <= 4000


def test_presidio_no_findings_reports_zero_entities():
    out = presidio.analyze_text("nothing sensitive here")
    assert "presidio: 0 entities" in out


def test_flag_off_is_inert_for_all_three_tools(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    for tool in (
        "mcp__promptfoo__run_eval",
        "mcp__agentshield__scan_action",
        "mcp__presidio__analyze_text",
    ):
        r = _run_hook(
            {"tool_name": tool, "agent": "backend-eng-1"},
            {"DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
            features=_features(tmp_path, on=False),
        )
        assert json.loads(r.stdout) == {}
    assert not audit_log.exists()


def test_features_yaml_ws_d_flag_on_after_activation():
    text = (ROOT / "config" / "features.yaml").read_text()
    assert "ws_d_langfuse_lens: true" in text


def test_egress_profile_for_eval_tools_is_deny_all():
    import yaml

    data = yaml.safe_load((ROOT / "config" / "egress-allowlist.yaml").read_text())
    assert data["profiles"]["eval-guardrail-deny-all"] == []


def test_promptfoo_run_eval_against_local_fixture(tmp_path):
    fixture = tmp_path / "eval.json"
    fixture.write_text(
        json.dumps(
            {
                "cases": [
                    {"name": "greets", "expected_contains": "hello", "actual": "hello world"},
                    {"name": "fails", "expected_contains": "goodbye", "actual": "hello world"},
                ]
            }
        )
    )
    out = promptfoo.run_eval(str(fixture))
    assert "1/2 passed" in out
    assert "fails" in out


def test_promptfoo_missing_fixture_reports_error_not_crash():
    out = promptfoo.run_eval("/definitely/missing/fixture.json")
    assert "error" in out


def test_agentshield_flags_destructive_action():
    out = agentshield.scan_action("please run rm -rf / to clean up")
    assert "flagged" in out
    assert "destructive-filesystem-command" in out


def test_agentshield_safe_action_passes():
    out = agentshield.scan_action("read the file and summarize it")
    assert out == "agentshield: safe"
