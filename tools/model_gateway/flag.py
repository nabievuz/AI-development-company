"""Feature-flag reads for WS-E's model gateway — DAS-1583 (ADR-0038, ADR-0019).

Two independent flags gate this package, nested (parent -> sub-flag):

  ``ws_e_tenant_hardening``     — the WS-E workstream flag (shared with
                                   DAS-1582/DAS-1584). Gates the whole
                                   in-tenant gateway wiring.
  ``ws_e_openweight_ejectpath`` — the DEFERRED vLLM/SGLang eject-path's OWN
                                   sub-flag (design §4.2). Nested UNDER the
                                   parent: the eject-path is inert whenever
                                   EITHER flag is OFF, and stays OFF even if
                                   the parent flips ON, until a Founder
                                   decision explicitly opens it.

Follows the WS-A/WS-C pattern (``tools/sandbox/flag.py``,
``tools/mcp_bridges/audit_external_tool.py``): a plain line-scan of
``config/features.yaml`` — no yaml dependency, no coupling to
``scripts/feature_flags.py``'s own restricted ``DEFAULTS`` allow-list (a new
key added here does not require touching that shared module). Fail-safe to
OFF: an absent/unreadable file, or the key simply not present, resolves
``False`` — a broken config can never silently turn either flag ON.
"""
from __future__ import annotations

from pathlib import Path

TENANT_HARDENING_FLAG = "ws_e_tenant_hardening"
OPENWEIGHT_EJECTPATH_FLAG = "ws_e_openweight_ejectpath"

_DEFAULT_REL = "config/features.yaml"
_TRUE = {"1", "true", "on", "yes"}

#: Anchored to THIS file's location (LAW A — resolved at runtime, never written
#: down), not to the process cwd. Two env doors were removed here: a per-flag
#: override (``DASLAB_WS_E_TENANT_HARDENING_FLAG`` /
#: ``DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG``) and a ``DASLAB_FEATURES`` redirect,
#: which was a complete substitute for it. Because the parent flag is committed
#: ON, EITHER door alone was enough to open ``ws_e_openweight_ejectpath`` — the
#: vLLM/SGLang eject-path that ADR-0038 Q9 explicitly DEFERS pending a Founder
#: decision. An ambient value must not be able to open a deferred capability.
DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / _DEFAULT_REL


def _read_flag(flag: str, features_path: Path | None = None) -> bool:
    """``True`` only if ``flag`` resolves truthy in the features file.

    Resolution is ``features_path`` when given, else :data:`DEFAULT_FEATURES`.
    No environment variable participates. Any failure resolves ``False``.
    """
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{flag}:"):
                return raw.split(":", 1)[1].strip().lower() in _TRUE
    except OSError:
        return False
    return False


def tenant_hardening_on(features_path: Path | None = None) -> bool:
    """``True`` iff the shared WS-E workstream flag is ON."""
    return _read_flag(TENANT_HARDENING_FLAG, features_path)


def openweight_ejectpath_on(features_path: Path | None = None) -> bool:
    """``True`` iff the vLLM/SGLang eject-path sub-flag is ON.

    Nested gating (design §4.2): the eject-path is inert unless BOTH the
    parent ``ws_e_tenant_hardening`` AND this sub-flag are ON. This function
    enforces that nesting itself so no caller can accidentally open the
    eject-path by flipping only the sub-flag. Both reads take the SAME file, so
    parent and sub-flag can never be sourced from different places.
    """
    return _read_flag(TENANT_HARDENING_FLAG, features_path) and _read_flag(
        OPENWEIGHT_EJECTPATH_FLAG, features_path
    )
