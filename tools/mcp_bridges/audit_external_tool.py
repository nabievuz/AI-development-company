#!/usr/bin/env python3
"""PreToolUse governance hook for external (MCP) tools — DasLab WS-A (ADR-0033 TB-3).

Reads a Claude Code PreToolUse hook event on stdin, decides allow/deny for
external tool calls (MCP tools such as ``mcp__playwright__*`` or
``mcp__langchain-tools__*``), appends an append-only audit record, and returns
the hook decision on stdout.

Governance model (ADR-0033):
  * TB-2 least privilege — an external tool is allowed only if the calling
    agent's role is in that tool's (or its server's) allowlist. No default-allow.
  * TB-3 audit + redactable — every external-tool call is recorded to a JSONL log.
  * TB-4 browser is high-blast-radius — a browser tool requires an explicit
    allowlist entry, exactly like any other external tool.

No hardcoded paths (ADR-0003): the allowlist is read from ``$DASLAB_TOOL_ALLOWLIST``
(a JSON file) if set, else the conservative default is deny-all; the audit log
path comes from ``$DASLAB_TOOL_AUDIT_LOG``, defaulting to
``<cwd>/board/.tool-audit.jsonl``.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTERNAL_PREFIX = "mcp__"


def server_of(tool_name: str) -> str:
    """``mcp__<server>__<tool>`` -> ``mcp__<server>``."""
    parts = tool_name.split("__")
    return "__".join(parts[:2]) if len(parts) >= 2 else tool_name


def load_allowlist() -> dict:
    path = os.environ.get("DASLAB_TOOL_ALLOWLIST")
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def decide(tool_name: str, agent_type: str, allowlist: dict) -> tuple[str, str]:
    """Pure allow/deny decision (unit-tested).

    Non-external tools are always allowed here — other hooks govern built-ins.
    An external tool is allowed only when the agent's role is explicitly listed
    for that tool or its server (``"*"`` means any role).
    """
    if not tool_name.startswith(EXTERNAL_PREFIX):
        return "allow", "not an external tool"
    roles = allowlist.get(tool_name)
    if roles is None:
        roles = allowlist.get(server_of(tool_name))
    if roles is None:
        return "deny", f"{tool_name} is not allow-listed (TB-2: no default-allow)"
    if roles == "*" or agent_type in roles:
        return "allow", f"{agent_type} is allow-listed for {tool_name}"
    return "deny", f"{agent_type} is not allow-listed for {tool_name}"


def audit(record: dict) -> None:
    path = os.environ.get("DASLAB_TOOL_AUDIT_LOG") or str(Path.cwd() / "board" / ".tool-audit.jsonl")
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # auditing must never block or crash a wave


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    raw = sys.stdin.read() or "{}"
    try:
        event = json.loads(raw)
    except ValueError:
        event = {}
    tool_name = event.get("tool_name", "")
    agent_type = event.get("agent_type") or event.get("agent") or "unknown"
    decision, reason = decide(tool_name, agent_type, load_allowlist())
    audit({"ts": _now(), "tool": tool_name, "agent": agent_type, "decision": decision, "reason": reason})
    if decision == "deny":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"[WS-A governance] {reason}",
                    }
                }
            )
        )
    else:
        print(json.dumps({}))  # empty object == allow
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
