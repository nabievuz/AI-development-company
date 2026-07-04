#!/usr/bin/env python3
"""tests/test_security_baseline.py — R-6 security baseline validators (ADR-006)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_injection_guard as cig  # noqa: E402  (import after path manipulation)
import check_permissions as cp  # noqa: E402
import check_secrets as cs  # noqa: E402


def _inv(**over) -> dict:
    e = {
        "event_type": "agent_invocation", "ticket_id": "DAS-1", "run_id": "r1",
        "role_key": "backend-eng-1", "model": "sonnet", "workspace_id": "wt-DAS-1",
        "context_contract": {"task": "x", "external_content_policy": "data"},
        "allowed_tools": ["read", "edit"], "secrets_policy": "no_secrets",
        "exit_contract": {}, "created_at": "2026-06-21T10:00:00Z",
    }
    e.update(over)
    return e


def _events(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / ".events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# check_permissions (least-privilege)
# --------------------------------------------------------------------------- #

def test_permissions_inert(tmp_path):
    assert cp.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_permissions_clean_passes(tmp_path):
    assert cp.main(["--events", str(_events(tmp_path, [_inv()]))]) == 0


def test_permissions_wildcard_tools_fails(tmp_path):
    assert cp.main(["--events", str(_events(tmp_path, [_inv(allowed_tools=["*"])]))]) == 1


def test_permissions_unsafe_secrets_policy_fails(tmp_path):
    assert cp.main(["--events", str(_events(tmp_path, [_inv(secrets_policy="all_secrets")]))]) == 1


def test_permissions_no_workspace_fails(tmp_path):
    inv = _inv()
    del inv["workspace_id"]
    assert cp.main(["--events", str(_events(tmp_path, [inv]))]) == 1


def test_permissions_glob_family_tool_fails(tmp_path):
    # canonical Claude Code family-grant syntax must be caught (review-found fail-open)
    for bad in ("mcp__*", "Bash(*)", "read-*"):
        assert cp.main(["--events", str(_events(tmp_path, [_inv(allowed_tools=[bad])]))]) == 1


def test_permissions_concrete_paren_tool_passes(tmp_path):
    # a SPECIFIC bash command (no glob) is bounded -> least-privilege ok
    assert cp.main(["--events", str(_events(tmp_path, [_inv(allowed_tools=["Bash(git status)", "read"])]))]) == 0


# --------------------------------------------------------------------------- #
# check_injection_guard
# --------------------------------------------------------------------------- #

def test_injection_inert(tmp_path):
    assert cig.main(["--events", str(tmp_path / "nope.jsonl")]) == 0


def test_injection_clean_passes(tmp_path):
    assert cig.main(["--events", str(_events(tmp_path, [_inv()]))]) == 0


def test_injection_raw_state_fails(tmp_path):
    inv = _inv(context_contract={"task": "x", "raw_full_state": True})
    assert cig.main(["--events", str(_events(tmp_path, [inv]))]) == 1


def test_injection_command_policy_fails(tmp_path):
    inv = _inv(context_contract={"task": "x", "external_content_policy": "command"})
    assert cig.main(["--events", str(_events(tmp_path, [inv]))]) == 1


def test_injection_no_allowlist_fails(tmp_path):
    inv = _inv()
    del inv["allowed_tools"]
    assert cig.main(["--events", str(_events(tmp_path, [inv]))]) == 1


def test_injection_glob_family_tool_fails(tmp_path):
    assert cig.main(["--events", str(_events(tmp_path, [_inv(allowed_tools=["mcp__*"])]))]) == 1


# --------------------------------------------------------------------------- #
# check_secrets
# --------------------------------------------------------------------------- #

def test_secrets_inert(tmp_path):
    # no event store + empty experiments dir -> clean/inert
    exp = tmp_path / "experiments"
    exp.mkdir()
    assert cs.main(["--events", str(tmp_path / "nope.jsonl"), "--experiments", str(exp)]) == 0


def test_secrets_in_event_store_fails(tmp_path):
    # build the pattern at runtime (split literals) so this test file itself is not flagged
    fake = "sk-ant-" + "api03-" + "x" * 45
    inv = _inv(context_contract={"prompt": fake})
    exp = tmp_path / "experiments"
    exp.mkdir()
    assert cs.scan_text(fake) is True
    assert cs.main(["--events", str(_events(tmp_path, [inv])), "--experiments", str(exp)]) == 1
