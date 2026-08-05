#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import action_gate


_MCP_BRIDGES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_bridges"
)
sys.path.insert(0, _MCP_BRIDGES)
from egress_guard import active_profile, check_egress

TOOL_NAME = "browser"
_UA = "DasLab-WS-A-browser-bridge/0.1"
_MAX_CHARS = 4000


_LAST_PAGE: dict | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


_PW_WIRED = False
_SHOT_N = 0


def _use_playwright() -> bool:
    if os.environ.get("DASLAB_BROWSER_BACKEND", "").strip().lower() != "playwright":
        return False
    return importlib.util.find_spec("playwright") is not None


def _pw():
    global _PW_WIRED
    import playwright_backend as pb

    if not _PW_WIRED:
        pb.set_guard(lambda u: check_egress(u, active_profile())[0])
        _PW_WIRED = True
    return pb


def _screenshot_path() -> str:
    global _SHOT_N
    _SHOT_N += 1
    outdir = os.environ.get("DASLAB_BROWSER_ARTIFACTS", "/tmp/daslab-browser")
    os.makedirs(outdir, exist_ok=True)
    return os.path.join(outdir, f"shot-{os.getpid()}-{_SHOT_N}.png")


def _deny(action: str) -> str | None:
    allowed, reason = action_gate.check_action(action)
    if not allowed:
        return f"error: {reason}"
    return None


def navigate(url: str) -> str:
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
    except Exception as exc:
        return f"error: {exc}"
    title = ""
    lower = body.lower()
    if "<title>" in lower and "</title>" in lower:
        title = body[lower.index("<title>") + 7 : lower.index("</title>")].strip()


    _LAST_PAGE = {"url": url, "title": title, "text": body[:_MAX_CHARS]}


    if _use_playwright():
        try:
            live = _pw().navigate(url)
            _LAST_PAGE = {
                "url": url,
                "title": live.get("title") or title,
                "text": (live.get("text") or body)[:_MAX_CHARS],
            }
            return f"navigated: {url} (live browser)"
        except Exception as exc:
            return f"navigated: {url} (stdlib fallback — live browser error: {exc})"
    return f"navigated: {url}"


def read() -> str:
    denial = _deny("read")
    if denial:
        return denial
    if _LAST_PAGE is None:
        return "error: no page loaded — call navigate first"
    return f"title: {_LAST_PAGE['title']}\n---\n{_LAST_PAGE['text']}"


def screenshot() -> str:
    denial = _deny("screenshot")
    if denial:
        return denial
    if _LAST_PAGE is None:
        return "error: no page loaded — call navigate first"
    if _use_playwright():
        try:
            path = _screenshot_path()
            w, h = _pw().screenshot(path)
            return f"screenshot saved: {path} ({w}x{h})"
        except Exception as exc:
            return f"error: screenshot failed: {exc}"
    return (
        "error: screenshot backend not installed (optional Playwright/"
        "browser-use dependency absent) — action grant confirmed, C8 passed"
    )


def _privileged(action: str, op=None) -> str:
    denial = _deny(action)
    if denial:
        return denial
    if op is not None and _use_playwright():
        try:
            return op(_pw())
        except Exception as exc:
            return f"error: {action} failed: {exc}"
    return (
        f"error: {action} backend not installed (optional Playwright/browser-use "
        f"dependency absent) — action grant confirmed, C8 passed for {action!r}"
    )


def click(selector: str) -> str:
    return _privileged("click", lambda pb: pb.click(selector))


def type_text(selector: str, text: str) -> str:
    return _privileged("type", lambda pb: pb.type_text(selector, text))


def form_fill(fields: str) -> str:
    def op(pb):
        import json

        try:
            pairs = json.loads(fields)
        except Exception as exc:
            return f"error: form_fill expects a JSON object of selector->value ({exc})"
        if not isinstance(pairs, dict):
            return "error: form_fill expects a JSON object of selector->value"
        return pb.form_fill(pairs)

    return _privileged("form_fill", op)


def submit(selector: str) -> str:
    return _privileged("submit", lambda pb: pb.submit(selector))


def upload(selector: str, file_path: str) -> str:
    return _privileged("upload", lambda pb: pb.upload(selector, file_path))


def clipboard_read() -> str:

    return _privileged("clipboard_read")


def clipboard_write(text: str) -> str:
    return _privileged("clipboard_write")


def local_app_control(command: str) -> str:
    return _privileged("local_app_control")


def build_server():
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
