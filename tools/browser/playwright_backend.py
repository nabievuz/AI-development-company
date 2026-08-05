#!/usr/bin/env python3

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

_UA = "DasLab-WS-A-browser-bridge/0.1 (+playwright)"
_NAV_TIMEOUT_MS = 20_000
_MAX_TEXT = 4000


_GUARD: Callable[[str], bool] = lambda _url: False


def set_guard(fn: Callable[[str], bool]) -> None:
    global _GUARD
    _GUARD = fn


_CMD_Q: "queue.Queue" = queue.Queue()
_STARTED = threading.Event()
_START_LOCK = threading.Lock()
_START_ERR: list[str] = []
_WORKER: threading.Thread | None = None


def _route(route) -> None:
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
    except Exception as exc:
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
