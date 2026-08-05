#!/usr/bin/env python3

from __future__ import annotations

import os


DEFAULT_GRANT: frozenset[str] = frozenset({"navigate", "read", "screenshot"})


PRIVILEGED_ACTIONS: frozenset[str] = frozenset(
    {
        "click",
        "type",
        "form_fill",
        "submit",
        "upload",
        "clipboard_read",
        "clipboard_write",
        "local_app_control",
    }
)


ALL_ACTIONS: frozenset[str] = DEFAULT_GRANT | PRIVILEGED_ACTIONS

_ENV_GRANTS = "DASLAB_BROWSER_ACTION_GRANTS"


def granted_actions(env: dict | None = None) -> frozenset[str]:
    source = env if env is not None else os.environ
    raw = source.get(_ENV_GRANTS, "") or ""
    requested = {tok.strip() for tok in raw.split(",") if tok.strip()}
    granted = set(DEFAULT_GRANT)
    for action in requested:
        if action in PRIVILEGED_ACTIONS:
            granted.add(action)


    return frozenset(granted)


def check_action(action: str, granted: frozenset[str] | None = None) -> tuple[bool, str]:
    if granted is None:
        granted = granted_actions()
    if action not in ALL_ACTIONS:
        return False, f"unknown browser action {action!r} — denied (fail-closed, C8)"
    if action in granted:
        return True, f"{action} is granted"
    if action in DEFAULT_GRANT:


        return False, f"{action} is not granted (C8 default grant regression)"
    return False, (
        f"{action} requires an explicit reviewed grant — the C8 default grant is "
        "navigate+read+screenshot only (write/submit/upload/clipboard/"
        "local-app-control actions are never on by default)"
    )
