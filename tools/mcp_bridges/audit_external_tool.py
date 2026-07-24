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
from datetime import UTC, datetime
from pathlib import Path

# Sibling scrubber (ADR-0012 §2). Robust import whether run as a script (dir is
# sys.path[0]) or imported by path in a test (dir is not).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:  # scrubbing is best-effort; its absence must never crash the hook
    from redaction import redact_then_truncate
except Exception:  # noqa: BLE001
    def redact_then_truncate(text: object, cap: int = 280) -> str:  # type: ignore[misc]
        return str(text)[:cap]

EXTERNAL_PREFIX = "mcp__"
_FLAG = "ws_a_tool_bridge"


def server_of(tool_name: str) -> str:
    """``mcp__<server>__<tool>`` -> ``mcp__<server>``."""
    parts = tool_name.split("__")
    return "__".join(parts[:2]) if len(parts) >= 2 else tool_name


def _flag_on() -> bool:
    """Read ``ws_a_tool_bridge`` from config/features.yaml. Fail-safe to OFF.

    OFF (the default, and the only state at merge) makes the whole hook inert —
    it passes every call through unchanged (TB-5: flag-off == byte-identical).
    An unreadable/absent features file also resolves OFF, so a broken config can
    never silently turn governance ON.
    """
    override = os.environ.get("DASLAB_WS_A_FLAG")
    if override is not None:
        return override.strip().lower() in {"1", "true", "on", "yes"}
    path = os.environ.get("DASLAB_FEATURES")
    p = Path(path) if path else None
    if p is None:
        here = Path.cwd()
        for base in (here, *here.parents):
            cand = base / "config" / "features.yaml"
            if cand.is_file():
                p = cand
                break
    if p is None or not p.is_file():
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
    """C2 — a compiled allow-list must never carry a ``"*"`` value. If one is
    present the map is untrustworthy; treat the whole thing as deny-all."""
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
        # C2 fail-closed: a ``"*"`` any-role value must never widen access.
        return {}
    return data


def decide(tool_name: str, agent_type: str, allowlist: dict) -> tuple[str, str]:
    """Pure allow/deny decision (unit-tested).

    Non-external tools are always allowed here — other hooks govern built-ins.
    An external tool is allowed only when the agent's role is EXPLICITLY listed
    (by exact role key) for that tool or its server. There is NO any-role
    wildcard: a ``"*"`` roles value is never honoured (C2) — the compiler emits
    only explicit role-key lists, and a ``"*"`` that reaches here denies.
    """
    if not tool_name.startswith(EXTERNAL_PREFIX):
        return "allow", "not an external tool"
    roles = allowlist.get(tool_name)
    if roles is None:
        roles = allowlist.get(server_of(tool_name))
    if roles is None:
        return "deny", f"{tool_name} is not allow-listed (TB-2: no default-allow)"
    if not isinstance(roles, list) or "*" in roles:
        # C2 — a non-list value (e.g. the string "*") or a "*" list member is
        # never any-role; the map is malformed → deny.
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
        pass  # auditing must never block or crash a wave


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit_allow() -> None:
    print(json.dumps({}))  # empty object == allow


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


def main() -> int:
    # TB-5: with the WS-A flag OFF (the only state at merge) the hook is INERT —
    # it passes every call through, so a wave is byte-identical to pre-merge and
    # existing MCP servers (ArcRift/obsidian) are never denied. No audit line is
    # written in the inert path (no side effect).
    if not _flag_on():
        _emit_allow()
        return 0

    raw = sys.stdin.read() or "{}"
    try:
        event = json.loads(raw)
    except ValueError:
        event = {}
    tool_name = event.get("tool_name", "")
    agent_type = event.get("agent_type") or event.get("agent") or "unknown"
    decision, reason = decide(tool_name, agent_type, load_allowlist())
    # ADR-0012 §2: the audit ``reason`` is a Tier-B field — scrub-then-truncate
    # before it is appended to the append-only log.
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
    # C3 — the hook must fail CLOSED. Any uncaught error here would otherwise let
    # the harness fail OPEN (a non-blocking hook error → tool proceeds). Catch it,
    # deny, and exit 2 so the CLI/SDK block the call even on an internal crash.
    # (The shell wrapper in .claude/settings.json adds the spawn-failure guard —
    # if python3 itself cannot start, `|| exit 2` still denies.)
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _emit_deny(f"hook internal error — fail-closed deny ({type(exc).__name__})")
        raise SystemExit(2) from exc
