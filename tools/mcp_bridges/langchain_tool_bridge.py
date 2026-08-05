#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egress_guard import active_profile, check_egress
from untrusted_input import describe, quarantine, screen

TOOL_NAME = "langchain-tools"
_UA = "DasLab-WS-A-bridge/0.1"
_MAX_CHARS = 4000
_MAX_RESPONSE_BYTES = 200_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def web_fetch(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"

    allowed, reason = check_egress(url, active_profile())
    if not allowed:
        return f"error: {reason}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with _OPENER.open(req, timeout=20) as resp:
            body = resp.read(_MAX_RESPONSE_BYTES).decode("utf-8", "replace")
    except Exception as exc:
        return f"error: {exc}"
    title = ""
    lower = body.lower()
    if "<title>" in lower and "</title>" in lower:
        title = body[lower.index("<title>") + 7 : lower.index("</title>")].strip()
    content = f"title: {title}\n---\n{body[:_MAX_CHARS]}"
    verdict = screen(content)
    return f"injection-screen: {describe(verdict)}\n{quarantine(content, url)}"


def build_server():
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
