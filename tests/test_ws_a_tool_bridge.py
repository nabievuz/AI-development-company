"""WS-A tool-bridge tests (ADR-0033). MCP-dependent parts skip if ``mcp`` is absent."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("tools/mcp_bridges/audit_external_tool.py", "audit_external_tool")
bridge = _load("tools/mcp_bridges/langchain_tool_bridge.py", "langchain_tool_bridge")


def test_denies_unlisted_external_tool():
    assert hook.decide("mcp__playwright__browser_navigate", "engineer-ic", {})[0] == "deny"


def test_allows_listed_role_only():
    allow = {"mcp__playwright": ["qa-lead", "design-ic"]}
    assert hook.decide("mcp__playwright__browser_navigate", "qa-lead", allow)[0] == "allow"
    assert hook.decide("mcp__playwright__browser_navigate", "engineer-ic", allow)[0] == "deny"


def test_wildcard_allows_any_role():
    allow = {"mcp__langchain-tools": "*"}
    assert hook.decide("mcp__langchain-tools__web_fetch", "anyone", allow)[0] == "allow"


def test_non_external_tools_pass_through():
    assert hook.decide("Read", "engineer-ic", {})[0] == "allow"


def test_server_of_parsing():
    assert hook.server_of("mcp__playwright__browser_click") == "mcp__playwright"


def test_web_fetch_rejects_non_url():
    assert bridge.web_fetch("not-a-url").startswith("error:")


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp not installed")
def test_sidecar_builds_and_registers_tool():
    server = bridge.build_server()
    assert server is not None
