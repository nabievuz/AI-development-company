#!/usr/bin/env python3
"""DasLab WS-D — promptfoo eval sidecar, admitted through the ADR-0033 edge.

A FastMCP sidecar (ADR-0033 TB-1) that re-exposes a prompt/eval regression
check as a governed MCP tool, admitted through the *same* edge WS-A built
(``audit_external_tool.py`` PreToolUse hook + the compiled TB-2 allow-list) —
DAS-1574 does not fork or add a second admission path (design
``docs/design/ws-d-langfuse-lens.md`` §5).

This reference sidecar ships a dependency-light, local-fixture-only
``run_eval`` tool (stdlib only) so the bridge pattern is provable end to end
and runnable in CI without network access or the real ``promptfoo`` CLI. In
production, swap the backend for the real promptfoo binary/npm package —
e.g. shelling out to ``promptfoo eval --no-progress-bar -c <config>`` — while
keeping this module's egress posture (deny-all, TB-4) and audit path
(PreToolUse, TB-3) unchanged. CONSUME, don't rebuild (ADR-0010 C1).

Egress: promptfoo here is a LOCAL eval harness (fixtures only) — it gets the
``eval-guardrail-deny-all`` profile (empty list, config/egress-allowlist.yaml),
identical in shape to the browser's deny-all-by-default posture. No production
credentials, no network calls, by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Sibling modules (redaction) live beside this file. When the sidecar runs as a
# script its dir is already sys.path[0]; when a test imports it by path it is
# not — so make the sibling import robust either way (ADR-0003).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate  # noqa: E402

TOOL_NAME = "promptfoo"
_MAX_CASES = 200


def run_eval(fixture_path: str) -> str:
    """Run a local prompt-eval fixture and return a pass/fail summary.

    *fixture_path* must be a local JSON file shaped
    ``{"cases": [{"name": str, "prompt": str, "expected_contains": str,
    "actual": str}, ...]}`` — a stand-in for a promptfoo eval-result file. No
    network I/O; a missing/invalid fixture is reported as a failure, never
    raised, so a bad path cannot crash the sidecar process.

    The returned summary never echoes a full case body verbatim past the
    ADR-0012 length cap — it is passed through the same redact-then-truncate
    ordering as any other tool transcript before being handed back (belt and
    suspenders; the primary control is that this sidecar never sees a
    production secret in the first place — fixtures are local test data).
    """
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
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is testable without it."""
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
