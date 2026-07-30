"""Feature-flag read for ``ws_c_langgraph_loop`` — DasLab WS-C (ADR-0035 LG-5).

Follows the WS-A pattern (``tools/mcp_bridges/audit_external_tool.py``
``_flag_on``): fail-safe to OFF. An absent/unreadable ``config/features.yaml``,
or the key simply not being present, resolves OFF — a broken config can never
silently turn the sandbox adapter's callers ON. No third-party dependency
(plain line scan, not a YAML parse) so this module has zero optional deps.
"""
from __future__ import annotations

from pathlib import Path

_FLAG = "ws_c_langgraph_loop"
_DEFAULT_REL = "config/features.yaml"

#: Anchored to THIS file's location (LAW A — resolved at runtime, never written
#: down), not the process cwd. A ``DASLAB_WS_C_FLAG`` override and a
#: ``DASLAB_FEATURES`` redirect used to precede it; both are gone, so the flag a
#: caller sees no longer depends on the ambient environment or on which
#: directory the process happens to have started in.
DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / _DEFAULT_REL


def flag_on(features_path: Path | None = None) -> bool:
    """``True`` only if ``ws_c_langgraph_loop`` resolves truthy.

    Resolution is ``features_path`` when given, else :data:`DEFAULT_FEATURES`.
    No environment variable participates. Any failure — missing file, missing
    key, unreadable file — resolves ``False`` (fail-safe to OFF, matching WS-A).
    """
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{_FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False
