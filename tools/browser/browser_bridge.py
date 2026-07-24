#!/usr/bin/env python3
"""DasLab WS-A — governed browser / computer-use tool bridge (DAS-1548).

An out-of-process FastMCP sidecar (ADR-0033 TB-1, TB-4) exposing a browser /
computer-use tool the same way ``tools/mcp_bridges/langchain_tool_bridge.py``
exposes ``web_fetch`` — same governance shape, distinct repo zone (this ticket
does not modify anything under ``tools/mcp_bridges/``; it IMPORTS and reuses
``egress_guard.check_egress`` and ``redaction`` rather than forking them).

Every tool function below enforces, in this fixed order:

  1. **C8 action gate** (``action_gate.check_action``) — is this ACTION granted
     at all? The default grant is navigate + read + screenshot ONLY; every
     write/submit/upload/clipboard/local-app-control action is denied unless
     explicitly granted. This check runs BEFORE any egress check or browser
     call — a denied action never even reaches the network/automation layer.
  2. **TB-4 egress guard** (``egress_guard.check_egress``, C4/C5/C6) — for any
     action that performs navigation/network I/O: no unchecked redirects,
     resolved-IP SSRF blocking (loopback/link-local/RFC-1918), label-boundary
     domain matching. Reused verbatim from the DAS-1547 foundation.
  3. The actual browser action, via a real backend when available.

**Absent-by-default reference backend.** Real browser automation (Playwright
or browser-use) is an OPTIONAL dependency — never added to core
``requirements.txt`` (ADR-0033 TB-1: the engine stays server-free; absence
means the tool does not exist). This module ships a dependency-light
STAND-IN backend for ``navigate``/``read`` (stdlib ``urllib``, mirroring
``web_fetch``) so the governance chain (C8 + C4/C5/C6 + FR-006) is provable
and testable in CI without the optional dependency installed. Every
PRIVILEGED action (click/type/submit/upload/clipboard/local-app-control)
returns a clear "backend not installed" result when reached (i.e. when C8
would otherwise allow it) — swapping in a real Playwright/browser-use driver
there is a backend change, not a governance change (ADR-0010 C1: consume,
don't rebuild).

**FR-006 — fetched content is untrusted DATA.** ``read()`` returns the loaded
page's text as an inert string. Nothing in this module parses, evaluates, or
acts on that text as instructions — it is handed back to the caller as
observed data only. It can never change the agent's goal, approvals, tool
grants, or the C8 action gate itself (there is no code path from "page
content" to any of those). Raw fetched bodies are also capped and never
persisted by this module; classification/redaction of any transcript this
tool produces is the ADR-0012 concern already implemented in
``tools/mcp_bridges/redaction.py`` (reused, not forked, by the PreToolUse
audit hook that wraps every ``mcp__browser__*`` call, same as any other
external tool, TB-3).
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import action_gate  # noqa: E402

# Sibling of tools/browser/ — reuse (never fork) the DAS-1547 foundation.
_MCP_BRIDGES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_bridges"
)
sys.path.insert(0, _MCP_BRIDGES)
from egress_guard import active_profile, check_egress  # noqa: E402

TOOL_NAME = "browser"
_UA = "DasLab-WS-A-browser-bridge/0.1"
_MAX_CHARS = 4000

# The last-navigated page (title, text). Module-level, single-tab reference
# state — a real Playwright/browser-use backend would replace this with the
# live page/session object. `read()`/`screenshot()` act on THIS page only.
_LAST_PAGE: dict | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """C4 — refuse to follow ANY 3xx redirect (same control as the DAS-1547
    ``web_fetch`` opener; duplicated here rather than importing a private
    class across an unrelated sidecar boundary, per the ticket's zone split).
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _deny(action: str) -> str | None:
    """Run the C8 action gate. Returns an ``"error: ..."`` string to short-circuit
    the caller on denial, or ``None`` when the action is granted."""
    allowed, reason = action_gate.check_action(action)
    if not allowed:
        return f"error: {reason}"
    return None


def navigate(url: str) -> str:
    """Load *url* and remember it as the current page (C8 default: granted).

    Routed through the TB-4 egress guard (C4/C5/C6) exactly like
    ``langchain_tool_bridge.web_fetch`` — no unchecked redirects, resolved-IP
    SSRF blocking, label-boundary domain matching against the active browser
    egress profile (``$DASLAB_EGRESS_PROFILE``).
    """
    global _LAST_PAGE
    denial = _deny("navigate")
    if denial:
        return denial
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"
    allowed, reason = check_egress(url, active_profile())
    if not allowed:
        return f"error: {reason}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with _OPENER.open(req, timeout=20) as resp:
            body = resp.read(200_000).decode("utf-8", "replace")
    except Exception as exc:  # never crash the wave on a fetch error
        return f"error: {exc}"
    title = ""
    lower = body.lower()
    if "<title>" in lower and "</title>" in lower:
        title = body[lower.index("<title>") + 7 : lower.index("</title>")].strip()
    # Stored as inert reference state only — untrusted DATA (FR-006), never
    # interpreted as instructions by this module.
    _LAST_PAGE = {"url": url, "title": title, "text": body[:_MAX_CHARS]}
    return f"navigated: {url}"


def read() -> str:
    """Return the current page's text as an inert excerpt (C8 default: granted).

    FR-006: this is observed DATA, handed back verbatim. It is never executed,
    never used to alter the calling agent's goal/approvals/tool grants, and
    the C8 gate above this function is not reachable FROM this text.
    """
    denial = _deny("read")
    if denial:
        return denial
    if _LAST_PAGE is None:
        return "error: no page loaded — call navigate first"
    return f"title: {_LAST_PAGE['title']}\n---\n{_LAST_PAGE['text']}"


def screenshot() -> str:
    """Capture the current page (C8 default: granted; reference backend absent)."""
    denial = _deny("screenshot")
    if denial:
        return denial
    if _LAST_PAGE is None:
        return "error: no page loaded — call navigate first"
    return (
        "error: screenshot backend not installed (optional Playwright/"
        "browser-use dependency absent) — action grant confirmed, C8 passed"
    )


def _privileged(action: str) -> str:
    """Shared body for every PRIVILEGED action: gate first, then report the
    absent-by-default reference backend. A real backend swap only changes
    what happens AFTER the gate passes."""
    denial = _deny(action)
    if denial:
        return denial
    return (
        f"error: {action} backend not installed (optional Playwright/browser-use "
        f"dependency absent) — action grant confirmed, C8 passed for {action!r}"
    )


def click(selector: str) -> str:
    return _privileged("click")


def type_text(selector: str, text: str) -> str:
    return _privileged("type")


def form_fill(fields: str) -> str:
    return _privileged("form_fill")


def submit(selector: str) -> str:
    return _privileged("submit")


def upload(selector: str, file_path: str) -> str:
    return _privileged("upload")


def clipboard_read() -> str:
    return _privileged("clipboard_read")


def clipboard_write(text: str) -> str:
    return _privileged("clipboard_write")


def local_app_control(command: str) -> str:
    return _privileged("local_app_control")


def build_server():
    """Build the FastMCP server. ``mcp`` is imported lazily so this module is
    importable/testable without the optional dependency installed."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(TOOL_NAME)
    server.tool()(navigate)
    server.tool()(read)
    server.tool()(screenshot)
    server.tool()(click)
    server.tool()(type_text)
    server.tool()(form_fill)
    server.tool()(submit)
    server.tool()(upload)
    server.tool()(clipboard_read)
    server.tool()(clipboard_write)
    server.tool()(local_app_control)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="DasLab WS-A governed browser tool bridge (DAS-1548)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"])
    parser.parse_args()
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
