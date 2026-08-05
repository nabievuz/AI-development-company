#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from redaction import redact_then_truncate
except Exception:
    def redact_then_truncate(text: object, cap: int = 280) -> str:
        return str(text)[:cap]

EXTERNAL_PREFIX = "mcp__"
_FLAG = "ws_a_tool_bridge"


_DEFAULT_INFRA_MCP = "mcp__ArcRift,mcp__obsidian"


def _infra_servers() -> frozenset[str]:
    raw = os.environ.get("DASLAB_INFRA_MCP", _DEFAULT_INFRA_MCP)
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def server_of(tool_name: str) -> str:
    parts = tool_name.split("__")
    return "__".join(parts[:2]) if len(parts) >= 2 else tool_name


DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / "config" / "features.yaml"


def _flag_on(features_path: Path | None = None) -> bool:
    p = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not p.is_file():
        return False
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{_FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


def _reject_wildcard(allowlist: dict) -> bool:
    for value in allowlist.values():
        if value == "*":
            return True
        if isinstance(value, list) and "*" in value:
            return True
    return False


def load_allowlist() -> dict:
    path = os.environ.get("DASLAB_TOOL_ALLOWLIST")
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or _reject_wildcard(data):

        return {}
    return data


def decide(tool_name: str, agent_type: str, allowlist: dict) -> tuple[str, str]:
    if not tool_name.startswith(EXTERNAL_PREFIX):
        return "allow", "not an external tool"
    if server_of(tool_name) in _infra_servers():


        return "allow", f"{server_of(tool_name)} is internal infrastructure (WS-A governs ecosystem bridges only)"
    roles = allowlist.get(tool_name)
    if roles is None:
        roles = allowlist.get(server_of(tool_name))
    if roles is None:
        return "deny", f"{tool_name} is not allow-listed (TB-2: no default-allow)"
    if not isinstance(roles, list) or "*" in roles:


        return "deny", f"{tool_name} has a malformed allow-list entry — denied (C2)"
    if agent_type in roles:
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
        pass


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit_allow() -> None:
    print(json.dumps({}))


def _emit_deny(reason: str) -> None:
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


def _deny_unidentified(what: str) -> int:
    reason = (
        f"{what} with the WS-A flag ON — cannot determine tool identity; "
        "fail-closed deny (C3)"
    )
    audit(
        {
            "ts": _now(),
            "tool": "",
            "agent": "unknown",
            "decision": "deny",
            "reason": redact_then_truncate(reason, 280),
        }
    )
    _emit_deny(reason)
    return 2


def _features_arg(argv: list[str]) -> Path | None:
    for i, arg in enumerate(argv):
        if arg == "--features" and i + 1 < len(argv):
            return Path(argv[i + 1])
        if arg.startswith("--features="):
            return Path(arg.split("=", 1)[1])
    return None


def main(argv: list[str] | None = None) -> int:


    if not _flag_on(_features_arg(sys.argv[1:] if argv is None else argv)):
        _emit_allow()
        return 0

    raw = sys.stdin.read() or "{}"
    try:
        event = json.loads(raw)
    except ValueError:

        return _deny_unidentified("unparseable PreToolUse event")
    if not isinstance(event, dict):


        return _deny_unidentified("PreToolUse event is not an object")
    tool_name = event.get("tool_name", "")
    agent_type = event.get("agent_type") or event.get("agent") or "unknown"
    decision, reason = decide(tool_name, agent_type, load_allowlist())


    audit(
        {
            "ts": _now(),
            "tool": tool_name,
            "agent": agent_type,
            "decision": decision,
            "reason": redact_then_truncate(reason, 280),
        }
    )
    if decision == "deny":
        _emit_deny(reason)
    else:
        _emit_allow()
    return 0


if __name__ == "__main__":


    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        _emit_deny(f"hook internal error — fail-closed deny ({type(exc).__name__})")
        raise SystemExit(2) from exc
