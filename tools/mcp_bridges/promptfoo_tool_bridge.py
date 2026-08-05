#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate

TOOL_NAME = "promptfoo"
_MAX_CASES = 200


def run_eval(fixture_path: str) -> str:
    p = Path(fixture_path)
    if not p.is_file():
        return redact_then_truncate(f"error: fixture not found: {fixture_path}", 280)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return redact_then_truncate(f"error: could not read fixture: {exc}", 280)
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list):
        return "error: fixture must contain a 'cases' list"
    cases = cases[:_MAX_CASES]
    passed = 0
    failed_names: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        name = str(case.get("name", "unnamed"))
        expected = str(case.get("expected_contains", ""))
        actual = str(case.get("actual", ""))
        if expected and expected in actual:
            passed += 1
        else:
            failed_names.append(name)
    total = len(cases)
    summary = f"promptfoo: {passed}/{total} passed"
    if failed_names:
        summary += f"; failed: {', '.join(failed_names[:20])}"
    return redact_then_truncate(summary, 2000)


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(run_eval)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab WS-D promptfoo eval sidecar (ADR-0033 edge, reused)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
