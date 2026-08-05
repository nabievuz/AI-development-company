#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate
from untrusted_input import screen, signal_names

TOOL_NAME = "agentshield"


_RED_FLAGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\brm\s+-rf\s+/"), "destructive-filesystem-command"),
    (re.compile(r"(?i)\bdrop\s+table\b"), "destructive-sql"),
    (re.compile(r"(?i)ignore (all )?(previous|prior) instructions"), "prompt-injection-marker"),
    (re.compile(r"(?i)\bexfiltrat"), "exfiltration-intent"),
    (re.compile(r"(?i)\bdisable\b.*\b(guardrail|audit|logging)\b"), "guardrail-tamper-intent"),
]


def scan_action(action_summary: str) -> str:
    text = action_summary if isinstance(action_summary, str) else str(action_summary)
    hits = [label for pattern, label in _RED_FLAGS if pattern.search(text)]
    hits.extend(f"injection:{name}" for name in signal_names(screen(text)))
    verdict = "flagged" if hits else "safe"
    summary = f"agentshield: {verdict}"
    if hits:
        summary += f" ({', '.join(hits)})"
    return redact_then_truncate(summary, 2000)


def build_server():
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
