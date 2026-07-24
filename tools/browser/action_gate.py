#!/usr/bin/env python3
"""C8 (F8) browser action-level least-privilege gate — DasLab WS-A (DAS-1548).

The browser / computer-use surface is far wider than a plain `web_fetch`: it
can navigate, read, screenshot, but ALSO click, type, submit forms, upload
files, read/write the clipboard, and drive local applications. The DAS-1546
GATE-2 security condition **C8** requires that least privilege stop at the
ACTION, not just the destination — a form-submit to an allow-listed host can
still exfiltrate (the egress allow-list governs *where*, never *what*).

**Enumerated action surface** (this module is the single source of truth for
it — every browser tool function in ``browser_bridge.py`` MUST route through
:func:`check_action` before doing anything else):

  * ``navigate``   — load a URL (subject to the TB-4 egress guard, C4/C5/C6).
  * ``read``       — return the current page's text as inert, untrusted DATA.
  * ``screenshot`` — capture a visual snapshot of the current page.

Those three are the **DEFAULT GRANT** (C8). Everything else is a PRIVILEGED
action, denied unless a role's overlay/launch context explicitly widens the
grant (a reviewed, non-default act):

  * ``click``, ``type``, ``form_fill``, ``submit`` — write/interaction actions.
  * ``upload``                                      — local-file exfil surface.
  * ``clipboard_read``, ``clipboard_write``         — clipboard I/O.
  * ``local_app_control``                           — drive a local application.

Grant source: ``$DASLAB_BROWSER_ACTION_GRANTS`` — a comma-separated list of
PRIVILEGED action names explicitly granted for this sidecar invocation. Unset,
empty, or unreadable resolves to the empty grant (fail-closed): only the
default three actions ever run. An unrecognised action name is always denied
(there is no way to "grant" something not in the enumerated surface).
"""
from __future__ import annotations

import os

# The C8 default grant — navigate + read + screenshot ONLY.
DEFAULT_GRANT: frozenset[str] = frozenset({"navigate", "read", "screenshot"})

# Every action requiring a separate, explicit, reviewed grant (C8).
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

# The complete enumerated action surface. An action outside this set is not a
# browser action at all — it is denied unconditionally (fail-closed), never
# "unknown ⇒ allow".
ALL_ACTIONS: frozenset[str] = DEFAULT_GRANT | PRIVILEGED_ACTIONS

_ENV_GRANTS = "DASLAB_BROWSER_ACTION_GRANTS"


def granted_actions(env: dict | None = None) -> frozenset[str]:
    """Return the full set of actions granted for this invocation.

    Always includes :data:`DEFAULT_GRANT`. Adds any name from
    ``$DASLAB_BROWSER_ACTION_GRANTS`` that is a recognised PRIVILEGED action —
    an unset/empty var, or a var naming only unrecognised tokens, changes
    nothing (fail-closed: the default grant is the floor and the ceiling
    unless a privileged action is named exactly).
    """
    source = env if env is not None else os.environ
    raw = source.get(_ENV_GRANTS, "") or ""
    requested = {tok.strip() for tok in raw.split(",") if tok.strip()}
    granted = set(DEFAULT_GRANT)
    for action in requested:
        if action in PRIVILEGED_ACTIONS:
            granted.add(action)
        # A requested token that is not a recognised privileged action (typo,
        # a default-grant name repeated, or a bogus value) is silently
        # ignored rather than denying the whole grant — but it never widens
        # anything either. This keeps the gate itself always fail-closed.
    return frozenset(granted)


def check_action(action: str, granted: frozenset[str] | None = None) -> tuple[bool, str]:
    """C8 decision: is *action* permitted for this invocation?

    Pure and unit-testable. ``granted`` defaults to :func:`granted_actions`
    (the live environment) when not supplied, so tests can pin an explicit
    grant set without touching env vars.
    """
    if granted is None:
        granted = granted_actions()
    if action not in ALL_ACTIONS:
        return False, f"unknown browser action {action!r} — denied (fail-closed, C8)"
    if action in granted:
        return True, f"{action} is granted"
    if action in DEFAULT_GRANT:
        # Should be unreachable (DEFAULT_GRANT ⊆ every granted set) but keep
        # the fail-closed message accurate if that invariant is ever broken.
        return False, f"{action} is not granted (C8 default grant regression)"
    return False, (
        f"{action} requires an explicit reviewed grant — the C8 default grant is "
        "navigate+read+screenshot only (write/submit/upload/clipboard/"
        "local-app-control actions are never on by default)"
    )
