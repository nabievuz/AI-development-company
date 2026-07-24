"""Feature-flag read for ``ws_c_langgraph_loop`` — DasLab WS-C (ADR-0035 LG-5).

Follows the WS-A pattern (``tools/mcp_bridges/audit_external_tool.py``
``_flag_on``): fail-safe to OFF. An absent/unreadable ``config/features.yaml``,
or the key simply not being present, resolves OFF — a broken config can never
silently turn the sandbox adapter's callers ON. No third-party dependency
(plain line scan, not a YAML parse) so this module has zero optional deps.
"""
from __future__ import annotations

import os
from pathlib import Path

_FLAG = "ws_c_langgraph_loop"
_ENV_OVERRIDE = "DASLAB_WS_C_FLAG"
_ENV_FEATURES = "DASLAB_FEATURES"
_DEFAULT_REL = "config/features.yaml"


def _features_path() -> Path | None:
    env = os.environ.get(_ENV_FEATURES)
    if env:
        return Path(env)
    here = Path.cwd()
    for base in (here, *here.parents):
        cand = base / _DEFAULT_REL
        if cand.is_file():
            return cand
    return None


def flag_on() -> bool:
    """``True`` only if ``ws_c_langgraph_loop`` resolves truthy.

    Order: an explicit env override (``DASLAB_WS_C_FLAG``) wins outright
    (useful for a narrow shadow test); otherwise read the tracked
    ``config/features.yaml``. Any failure — missing file, missing key,
    unreadable file — resolves ``False`` (fail-safe to OFF, matching WS-A).
    """
    override = os.environ.get(_ENV_OVERRIDE)
    if override is not None:
        return override.strip().lower() in {"1", "true", "on", "yes"}
    path = _features_path()
    if path is None or not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{_FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False
