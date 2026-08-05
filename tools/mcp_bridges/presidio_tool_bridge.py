#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate, scrub

TOOL_NAME = "presidio"


_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+\b")),
    ("PHONE", re.compile(r"(?<![\w.])\+?\d[\d ().\-]{5,15}\d(?![\w.])")),
    ("API_KEY", re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]


def analyze_text(text: str) -> str:
    raw = text if isinstance(text, str) else str(text)
    found = [label for label, pattern in _ENTITY_PATTERNS if pattern.search(raw)]
    redacted = scrub(raw)
    count = len(found)
    noun = "entity" if count == 1 else "entities"
    summary = f"presidio: {count} {noun}"
    if found:
        summary += f" [{', '.join(found)}]"
    summary += f" | risk: {screen_injection_risk(raw)}"
    summary += f" | redacted: {redacted}"


    return redact_then_truncate(summary, 4000)


UNSCREENED_RISK = "unscreened"


def screen_injection_risk(text: str) -> str:
    try:
        from untrusted_input import risk_name, screen
    except ImportError:
        return UNSCREENED_RISK
    try:
        return risk_name(screen(text))
    except Exception:
        return UNSCREENED_RISK


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(analyze_text)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab WS-D Presidio PII sidecar (ADR-0033 edge, reused)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
