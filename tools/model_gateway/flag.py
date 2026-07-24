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

import os
from pathlib import Path

TENANT_HARDENING_FLAG = "ws_e_tenant_hardening"
OPENWEIGHT_EJECTPATH_FLAG = "ws_e_openweight_ejectpath"

_ENV_OVERRIDE = {
    TENANT_HARDENING_FLAG: "DASLAB_WS_E_TENANT_HARDENING_FLAG",
    OPENWEIGHT_EJECTPATH_FLAG: "DASLAB_WS_E_OPENWEIGHT_EJECTPATH_FLAG",
}
_ENV_FEATURES = "DASLAB_FEATURES"
_DEFAULT_REL = "config/features.yaml"
_TRUE = {"1", "true", "on", "yes"}


def _features_path() -> Path | None:
    env = os.environ.get(_ENV_FEATURES)
    if env:
        return Path(env)
    here = Path.cwd()
    for base in (here, *here.parents):
        cand = base / _DEFAULT_REL
        if cand.is_file():
            return cand
    # Fall back to the path relative to this file (works even when the caller's
    # cwd is outside the repo, e.g. a test run from a different directory).
    repo_guess = Path(__file__).resolve().parents[2] / _DEFAULT_REL
    return repo_guess if repo_guess.is_file() else None


def _read_flag(flag: str) -> bool:
    """``True`` only if ``flag`` resolves truthy in ``config/features.yaml``.

    Order: an explicit env override wins outright (narrow shadow tests);
    otherwise scan the tracked features file. Any failure resolves ``False``.
    """
    override = os.environ.get(_ENV_OVERRIDE.get(flag, ""))
    if override is not None:
        return override.strip().lower() in _TRUE
    path = _features_path()
    if path is None or not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{flag}:"):
                return raw.split(":", 1)[1].strip().lower() in _TRUE
    except OSError:
        return False
    return False


def tenant_hardening_on() -> bool:
    """``True`` iff the shared WS-E workstream flag is ON."""
    return _read_flag(TENANT_HARDENING_FLAG)


def openweight_ejectpath_on() -> bool:
    """``True`` iff the vLLM/SGLang eject-path sub-flag is ON.

    Nested gating (design §4.2): the eject-path is inert unless BOTH the
    parent ``ws_e_tenant_hardening`` AND this sub-flag are ON. This function
    enforces that nesting itself so no caller can accidentally open the
    eject-path by flipping only the sub-flag.
    """
    return tenant_hardening_on() and _read_flag(OPENWEIGHT_EJECTPATH_FLAG)
