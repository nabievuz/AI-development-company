#!/usr/bin/env python3
"""DasLab WS-A — inbound tool bridge (ADR-0033).

A FastMCP sidecar that re-exposes an external capability as an MCP tool so any
DasLab role (subject to the WS-A allowlist + PreToolUse audit hook) can use it,
governed at the MCP edge. It is an out-of-process sidecar like ArcRift, so the
engine stays server-free (ADR-0033 TB-1).

This reference sidecar ships a dependency-light ``web_fetch`` tool (stdlib only)
so the bridge pattern is provable end to end and runnable in CI. In production,
swap the backend for any LangChain-catalog tool — e.g.::

    from langchain_tavily import TavilySearch
    _BACKEND = TavilySearch(max_results=5)
    def web_search(query: str) -> str:
        return str(_BACKEND.invoke({"query": query}))

...or point roles directly at the ready-made Playwright MCP server for full
browser control (see ``mcp.snippet.json``). CONSUME, don't rebuild (ADR-0010 C1).
"""
from __future__ import annotations

import argparse
import urllib.request

TOOL_NAME = "langchain-tools"
_UA = "DasLab-WS-A-bridge/0.1"
_MAX_CHARS = 4000


def web_fetch(url: str) -> str:
    """Fetch a URL and return its ``<title>`` plus a text excerpt (stdlib backend)."""
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(200_000).decode("utf-8", "replace")
    except Exception as exc:  # surface any fetch error as tool output, never crash the wave
        return f"error: {exc}"
    title = ""
    lower = body.lower()
    if "<title>" in lower and "</title>" in lower:
        title = body[lower.index("<title>") + 7 : lower.index("</title>")].strip()
    return f"title: {title}\n---\n{body[:_MAX_CHARS]}"


def build_server():
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is testable without it."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(web_fetch)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab WS-A inbound tool bridge (ADR-0033)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
