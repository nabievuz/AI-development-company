#!/usr/bin/env python3
"""DasLab WS-D — AgentShield guardrail sidecar, admitted through the ADR-0033 edge.

A FastMCP sidecar (ADR-0033 TB-1) that re-exposes an agent-guardrail / red-team
check as a governed MCP tool, admitted through the *same* edge WS-A built
(``audit_external_tool.py`` PreToolUse hook + the compiled TB-2 allow-list) —
DAS-1574 does not fork or add a second admission path (design
``docs/design/ws-d-langfuse-lens.md`` §5).

This reference sidecar ships a dependency-light, heuristic ``scan_action``
tool (stdlib only) so the bridge pattern is provable end to end and runnable
in CI without network access or the real AgentShield package. In production,
swap the backend for the real AgentShield guardrail engine while keeping this
module's egress posture (deny-all, TB-4) and audit path (PreToolUse, TB-3)
unchanged. CONSUME, don't rebuild (ADR-0010 C1).

Egress: AgentShield here scans a LOCAL action description only — it gets the
``eval-guardrail-deny-all`` profile (empty list). No production credentials,
no network calls, by default.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate  # noqa: E402

TOOL_NAME = "agentshield"

# Reference heuristic red-flag patterns for an agent-action description — a
# stand-in for AgentShield's real guardrail rule set. Not exhaustive by design
# (a real AgentShield engine owns full coverage); this proves the admission
# path, not a production-grade guardrail.
_RED_FLAGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\brm\s+-rf\s+/"), "destructive-filesystem-command"),
    (re.compile(r"(?i)\bdrop\s+table\b"), "destructive-sql"),
    (re.compile(r"(?i)ignore (all )?(previous|prior) instructions"), "prompt-injection-marker"),
    (re.compile(r"(?i)\bexfiltrat"), "exfiltration-intent"),
    (re.compile(r"(?i)\bdisable\b.*\b(guardrail|audit|logging)\b"), "guardrail-tamper-intent"),
]


def scan_action(action_summary: str) -> str:
    """Classify an agent-action description as ``safe`` or ``flagged``.

    Never raises: a non-string input is coerced; the returned verdict string
    is passed through the same redact-then-truncate ordering as any other
    tool transcript (ADR-0012 §2) so a flagged action's own free-text
    description cannot itself leak a secret back through this tool's output.
    """
    text = action_summary if isinstance(action_summary, str) else str(action_summary)
    hits = [label for pattern, label in _RED_FLAGS if pattern.search(text)]
    verdict = "flagged" if hits else "safe"
    summary = f"agentshield: {verdict}"
    if hits:
        summary += f" ({', '.join(hits)})"
    return redact_then_truncate(summary, 2000)


def build_server():
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is testable without it."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(scan_action)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab WS-D AgentShield guardrail sidecar (ADR-0033 edge, reused)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
