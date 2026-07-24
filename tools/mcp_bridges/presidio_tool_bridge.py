#!/usr/bin/env python3
"""DasLab WS-D — Presidio PII-detection sidecar, admitted through the ADR-0033 edge.

A FastMCP sidecar (ADR-0033 TB-1) that re-exposes a PII detection/anonymize
check as a governed MCP tool, admitted through the *same* edge WS-A built
(``audit_external_tool.py`` PreToolUse hook + the compiled TB-2 allow-list) —
DAS-1574 does not fork or add a second admission path (design
``docs/design/ws-d-langfuse-lens.md`` §5).

**The Presidio caveat (design §5.1):** Presidio's whole job is processing PII,
so its OWN tool I/O must be redacted exactly like any other tool transcript
(ADR-0012) — it does not get a pass just because PII-handling is its stated
purpose. This module therefore NEVER returns a raw detected value: the
``analyze_text`` tool returns only entity TYPES + a count, plus the input text
run through the same ADR-0012 §2 scrubber (redact-then-truncate) that any
other Tier-B tool transcript uses. Presidio's findings complement — never
replace — the ADR-0012 §2 scrubber the WS-A tool-event path already applies.

This reference sidecar ships a dependency-light, regex-based detector
(stdlib only) so the bridge pattern is provable end to end and runnable in CI
without network access or the real ``presidio-analyzer`` package. In
production, swap the backend for the real Presidio analyzer/anonymizer while
keeping this module's I/O-redaction and egress posture unchanged. CONSUME,
don't rebuild (ADR-0010 C1).

Egress: Presidio here analyzes text handed to it directly — it gets the
``eval-guardrail-deny-all`` profile (empty list). No production credentials,
no network calls, by default.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redaction import redact_then_truncate, scrub  # noqa: E402

TOOL_NAME = "presidio"

# Reference entity detectors — a stand-in for presidio-analyzer's recognizer
# set. Reuses the SAME classes the ADR-0012 §2 scrubber already knows (email,
# phone, high-entropy secret shapes) so a "finding" and a "redaction" agree on
# what counts as sensitive; a real Presidio backend would report a richer
# entity taxonomy (PERSON, LOCATION, CREDIT_CARD, ...).
_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+\b")),
    ("PHONE", re.compile(r"(?<![\w.])\+?\d[\d ().\-]{5,15}\d(?![\w.])")),
    ("API_KEY", re.compile(r"\bsk-ant-[a-z0-9]+-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
]


def analyze_text(text: str) -> str:
    """Detect PII entity TYPES in *text* — never echoes a raw detected value.

    Returns a summary of the form ``presidio: N entit(y|ies) [TYPE, ...] |
    redacted: <scrubbed text>`` — the redacted text is the SAME ADR-0012 §2
    scrub-then-truncate pass any other tool transcript gets (the Presidio
    caveat, design §5.1): this sidecar's own output is Tier-B and must not
    carry an unredacted value, regardless of the fact that finding PII is its
    job. Never raises: a non-string input is coerced first.
    """
    raw = text if isinstance(text, str) else str(text)
    found = [label for label, pattern in _ENTITY_PATTERNS if pattern.search(raw)]
    redacted = scrub(raw)
    count = len(found)
    noun = "entity" if count == 1 else "entities"
    summary = f"presidio: {count} {noun}"
    if found:
        summary += f" [{', '.join(found)}]"
    summary += f" | redacted: {redacted}"
    # Belt-and-suspenders (§2 fail-closed ordering): redact-then-truncate the
    # WHOLE returned string too, in case a future entity type's label itself
    # could ever carry raw content.
    return redact_then_truncate(summary, 4000)


def build_server():
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is testable without it."""
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
