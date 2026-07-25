#!/usr/bin/env python3
"""Optional real browser backend for the WS-A governed browser bridge (DAS-1548).

Absent-by-default (ADR-0033 TB-1): ``browser_bridge.py`` imports this module
ONLY when ``DASLAB_BROWSER_BACKEND=playwright`` and the optional ``playwright``
package is installed (``tools/browser/requirements-browser.txt``). With the env
var unset the bridge never touches this file and its stdlib reference backend
runs — so CI and every existing test are unaffected.

Design constraints honoured (ADR-0010 C1 — consume, don't rebuild):

  * **Governance is NOT re-implemented here.** The C8 action gate and the
    C4/C5/C6 egress DECISION stay in ``browser_bridge.py``; this module only
    acts on a URL the bridge already vetted. As defence-in-depth it also
    installs a per-request route guard (:func:`set_guard`) that ABORTS any
    request the same egress function denies — covering every subresource a real
    browser would otherwise fetch (the stdlib stub only vetted the top URL).
    The guard defaults to deny-all, so an un-wired backend reaches nothing.
  * **Sync Playwright, off the event loop.** FastMCP serves tools on an asyncio
    loop and the Playwright *sync* API refuses to run inside one. So a single
    headless Chromium lives in a dedicated worker thread and every operation is
    marshalled to it through a queue. The live page persists across MCP calls,
    so a granted ``click`` acts on the page a prior ``navigate`` loaded.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable

_UA = "DasLab-WS-A-browser-bridge/0.1 (+playwright)"
_NAV_TIMEOUT_MS = 20_000
_MAX_TEXT = 4000

# Governance callback: ``url -> bool``. Fail-closed: deny-all until the bridge
# wires in its egress decision via :func:`set_guard`.
_GUARD: Callable[[str], bool] = lambda _url: False


def set_guard(fn: Callable[[str], bool]) -> None:
    """Install the bridge's egress decision as the per-request route guard."""
    global _GUARD
    _GUARD = fn


# --- worker thread that owns the sync Playwright session -------------------- #
_CMD_Q: "queue.Queue" = queue.Queue()
_STARTED = threading.Event()
_START_LOCK = threading.Lock()
_START_ERR: list[str] = []
_WORKER: threading.Thread | None = None


def _route(route) -> None:
    """Re-check egress on EVERY request the real browser attempts (C4/C5/C6 at
    the network layer). Deny => abort; the browser never reaches that host."""
    try:
        if _GUARD(route.request.url):
            route.continue_()
        else:
            route.abort()
    except Exception:
        route.abort()


def _worker() -> None:
    try:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=_UA)
        page = context.new_page()
        page.route("**/*", _route)
    except Exception as exc:  # start failed — record so callers get a clear error
        _START_ERR.append(str(exc))
        _STARTED.set()
        return
    _STARTED.set()
    while True:
        item = _CMD_Q.get()
        if item is None:
            break
        op, reply = item
        try:
            reply.put(("ok", op(page)))
        except Exception as exc:
            reply.put(("err", str(exc)))
    try:
        browser.close()
        pw.stop()
    except Exception:
        pass


def _ensure_started() -> None:
    global _WORKER
    with _START_LOCK:
        if _WORKER is None:
            _WORKER = threading.Thread(target=_worker, name="daslab-playwright", daemon=True)
            _WORKER.start()
    if not _STARTED.wait(timeout=60):
        raise RuntimeError("playwright backend did not start within 60s")
    if _START_ERR:
        raise RuntimeError(f"playwright backend failed to start: {_START_ERR[0]}")


def _call(op: Callable[[Any], Any], timeout: float = 45.0) -> Any:
    _ensure_started()
    reply: "queue.Queue" = queue.Queue()
    _CMD_Q.put((op, reply))
    status, val = reply.get(timeout=timeout)
    if status == "err":
        raise RuntimeError(val)
    return val


# --- public operations (each runs on the worker's live page) ---------------- #
def navigate(url: str) -> dict:
    def op(page):
        resp = page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        try:
            text = page.inner_text("body")
        except Exception:
            text = ""
        return {
            "url": url,
            "title": page.title(),
            "text": text[:_MAX_TEXT],
            "status": resp.status if resp else None,
        }

    return _call(op)


def screenshot(path: str) -> tuple[int, int]:
    def op(page):
        page.screenshot(path=path, full_page=False)
        vp = page.viewport_size or {"width": 0, "height": 0}
        return (vp["width"], vp["height"])

    return _call(op)


def click(selector: str) -> str:
    def op(page):
        page.click(selector, timeout=_NAV_TIMEOUT_MS)
        return f"clicked: {selector}"

    return _call(op)


def type_text(selector: str, text: str) -> str:
    def op(page):
        page.fill(selector, text, timeout=_NAV_TIMEOUT_MS)
        return f"typed into: {selector}"

    return _call(op)


def form_fill(pairs: dict) -> str:
    def op(page):
        for sel, val in pairs.items():
            page.fill(sel, str(val), timeout=_NAV_TIMEOUT_MS)
        return f"filled {len(pairs)} field(s)"

    return _call(op)


def submit(selector: str) -> str:
    def op(page):
        page.press(selector, "Enter", timeout=_NAV_TIMEOUT_MS)
        return f"submitted: {selector}"

    return _call(op)


def upload(selector: str, file_path: str) -> str:
    def op(page):
        page.set_input_files(selector, file_path, timeout=_NAV_TIMEOUT_MS)
        return f"uploaded {file_path} -> {selector}"

    return _call(op)
