"""WS-D eval/guardrail tool-admission tests (ADR-0033 reused / DAS-1574).

Admits promptfoo, AgentShield, and Presidio through the *existing* ADR-0033
governed MCP edge (WS-A: `audit_external_tool.decide()` + the compiled
TB-2 allow-list + PreToolUse audit/deny) — no second admission path, no
bulk import, no blanket grant. Design: `docs/design/ws-d-langfuse-lens.md`
§5 (FR-005/FR-006); ticket: DAS-1574.

  * a non-allow-listed eval tool is refused by the SAME `decide()` WS-A uses
  * audit-skip is denied (the PreToolUse binding + fail-closed decode holds
    for these three tools exactly as for any other external tool)
  * every decision is audited (allow AND deny)
  * the compiled allow-list has NO "*" roles value, and grants only the
    designed roles (least privilege, no blanket grant)
  * Presidio's own tool I/O is redacted (the design §5.1 caveat)
  * flag OFF ⇒ the sidecars are inert/absent-by-default; dispatch unchanged
"""
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
    import gen_subagents  # noqa: PLC0415

    return gen_subagents


hook = _load("tools/mcp_bridges/audit_external_tool.py", "audit_external_tool")
promptfoo = _load("tools/mcp_bridges/promptfoo_tool_bridge.py", "promptfoo_tool_bridge")
agentshield = _load("tools/mcp_bridges/agentshield_tool_bridge.py", "agentshield_tool_bridge")
presidio = _load("tools/mcp_bridges/presidio_tool_bridge.py", "presidio_tool_bridge")


# --------------------------------------------------------------------------- #
# FR-005 — one admission path only; least-privilege compiled allow-list
# --------------------------------------------------------------------------- #

def test_compiled_allowlist_grants_only_designed_roles():
    """board/.tool-allowlist.json (the tracked, generate-and-diff artifact) grants
    exactly the design §5.2 roles — no blanket/global grant, no drift from the
    overlays."""
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
    """C2 — no ``"*"`` roles value anywhere in the compiled map."""
    committed = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    for value in committed.values():
        assert value != "*"
        assert "*" not in value


def test_non_allowlisted_eval_tool_refused_by_same_decide():
    """A role WITHOUT the overlay entry is refused by the identical `decide()`
    WS-A uses — no WS-D-specific bypass, no exemption."""
    allow = json.loads((ROOT / "board" / ".tool-allowlist.json").read_text())
    # granted role passes for each of the three tools
    assert hook.decide("mcp__promptfoo__run_eval", "qa-eng", allow)[0] == "allow"
    assert hook.decide("mcp__agentshield__scan_action", "security-lead", allow)[0] == "allow"
    assert hook.decide("mcp__presidio__analyze_text", "security-lead", allow)[0] == "allow"
    # an ungranted role is denied for every one of the three
    assert hook.decide("mcp__promptfoo__run_eval", "backend-eng-1", allow)[0] == "deny"
    assert hook.decide("mcp__agentshield__scan_action", "backend-eng-1", allow)[0] == "deny"
    assert hook.decide("mcp__presidio__analyze_text", "backend-eng-1", allow)[0] == "deny"


def test_tool_present_in_mcp_json_but_no_overlay_denies_every_role():
    """A tool wired in .mcp.json but declared by NO overlay compiles to no key
    and denies structurally for every role (WS-A §1.3 reused verbatim)."""
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


# --------------------------------------------------------------------------- #
# FR-005 — every decision is audited; audit-skip is denied
# --------------------------------------------------------------------------- #

def _run_hook(event: dict, env_extra: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(BRIDGES / "audit_external_tool.py")],
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
            "DASLAB_WS_A_FLAG": "on",
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(allow_file),
        },
    )
    assert json.loads(r_allow.stdout) == {}

    r_deny = _run_hook(
        {"tool_name": "mcp__presidio__analyze_text", "agent": "backend-eng-1"},
        {
            "DASLAB_WS_A_FLAG": "on",
            "DASLAB_TOOL_AUDIT_LOG": str(audit_log),
            "DASLAB_TOOL_ALLOWLIST": str(allow_file),
        },
    )
    deny_out = json.loads(r_deny.stdout)
    assert deny_out["hookSpecificOutput"]["permissionDecision"] == "deny"

    lines = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert len(lines) == 2
    assert {rec["decision"] for rec in lines} == {"allow", "deny"}
    tools_audited = {rec["tool"] for rec in lines}
    assert tools_audited == {"mcp__promptfoo__run_eval", "mcp__presidio__analyze_text"}


def test_audit_skip_denied_malformed_event(tmp_path):
    """An unparseable/malformed PreToolUse event with the flag ON is a
    fail-closed deny — this IS the "audit-skip denied" behaviour: a call
    cannot dodge governance by sending an event the hook can't parse."""
    audit_log = tmp_path / "audit.jsonl"
    r = subprocess.run(
        [sys.executable, str(BRIDGES / "audit_external_tool.py")],
        input="not json",
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "DASLAB_WS_A_FLAG": "on", "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
    )
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert r.returncode == 2
    assert audit_log.exists()  # the attempt IS audited, not skipped


def test_settings_binding_present_covers_these_tools_too():
    """.claude/settings.json's mcp__.* PreToolUse binding is untouched (not
    re-edited by this ticket) — it already matches mcp__promptfoo__*,
    mcp__agentshield__*, mcp__presidio__* via the mcp__.* wildcard matcher."""
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


# --------------------------------------------------------------------------- #
# FR-005 — Presidio's own tool I/O is redacted (design §5.1 caveat)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# FR-006 / flag semantics — flag OFF is inert; no WS-D-specific bypass
# --------------------------------------------------------------------------- #

def test_flag_off_is_inert_for_all_three_tools(tmp_path):
    audit_log = tmp_path / "audit.jsonl"
    for tool in (
        "mcp__promptfoo__run_eval",
        "mcp__agentshield__scan_action",
        "mcp__presidio__analyze_text",
    ):
        r = _run_hook(
            {"tool_name": tool, "agent": "backend-eng-1"},
            {"DASLAB_WS_A_FLAG": "off", "DASLAB_TOOL_AUDIT_LOG": str(audit_log)},
        )
        assert json.loads(r.stdout) == {}  # allow (inert passthrough)
    assert not audit_log.exists()  # no side effect while flag OFF


def test_features_yaml_ws_d_flag_default_off():
    text = (ROOT / "config" / "features.yaml").read_text()
    assert "ws_d_langfuse_lens: false" in text


def test_egress_profile_for_eval_tools_is_deny_all():
    import yaml

    data = yaml.safe_load((ROOT / "config" / "egress-allowlist.yaml").read_text())
    assert data["profiles"]["eval-guardrail-deny-all"] == []


# --------------------------------------------------------------------------- #
# Sidecar reference-backend sanity (proves the bridge pattern end to end)
# --------------------------------------------------------------------------- #

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
