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
import os
import sys
import urllib.request

# Sibling modules (egress guard, scrubber) live beside this file. When the sidecar
# runs as a script its dir is already sys.path[0]; when a test imports it by path
# it is not — so make the sibling import robust either way (ADR-0003).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egress_guard import active_profile, check_egress  # noqa: E402

TOOL_NAME = "langchain-tools"
_UA = "DasLab-WS-A-bridge/0.1"
_MAX_CHARS = 4000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """C4 — refuse to follow ANY 3xx redirect.

    An allow-listed host could 302 to an arbitrary (possibly internal) target,
    bypassing the egress gate that only ran against the ORIGINAL url. Returning
    None here makes urllib raise on a redirect instead of silently following it,
    so a 3xx surfaces as an error the caller sees rather than a covert hop.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


# A no-redirect opener is the single network path this sidecar uses.
_OPENER = urllib.request.build_opener(_NoRedirect)


def web_fetch(url: str) -> str:
    """Fetch a URL and return its ``<title>`` plus a text excerpt (stdlib backend).

    Gated by TB-4 egress (deny-all except the invoking role's domain allow-list,
    with resolved-IP SSRF blocking) and by a no-redirect opener (C4).
    """
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"
    # TB-4 egress check BEFORE any network syscall (C5/C6). Deny-all by default.
    allowed, reason = check_egress(url, active_profile())
    if not allowed:
        return f"error: {reason}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with _OPENER.open(req, timeout=20) as resp:
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
