"""In-tenant LiteLLM model gateway — DasLab WS-E (ADR-0038, DAS-1583).

Public surface:
  - :class:`LiteLLMGateway`, :class:`ModelRoute`, :class:`GatewayCall`,
    :class:`GatewayConfigError`, :func:`default_gateway`, :func:`enforce_boundary`
    (FR-004, TN-1 — the near-term Claude-subscription default, gateway.py).
  - :class:`OpenWeightBackend`, :func:`build_route`, :func:`register_ejectpath`,
    :func:`mock_call`, :class:`EjectPathInactiveError` (FR-005 — the DEFERRED
    vLLM/SGLang eject-path, ejectpath.py).
  - :func:`tenant_hardening_on`, :func:`openweight_ejectpath_on` (flag.py).

Feature-flagged: this package's wiring is inert while ``ws_e_tenant_hardening``
is OFF (default, ``config/features.yaml``); the eject-path is additionally
gated by its own nested sub-flag ``ws_e_openweight_ejectpath`` (also default
OFF). Importing this package changes no interactive ``/daslab-cycle`` wave —
these are libraries, like ``scripts/ws_b_admission.py``.
"""
from __future__ import annotations

# Fully-qualified imports — see ejectpath.py's comment: several `tools/*`
# packages ship a same-named `flag.py`/`gateway.py`; a bare `import flag`
# collides via `sys.modules` caching across a single pytest session. This
# package is imported fully-qualified throughout (requires the repo root on
# `sys.path`, true for `python3 -m pytest` run from the repo root).
from tools.model_gateway.ejectpath import (
    DEFAULT_MOCK_URL,
    EJECTPATH_ROUTE_NAME,
    EjectPathInactiveError,
    OpenWeightBackend,
    build_route,
    mock_call,
    register_ejectpath,
)
from tools.model_gateway.flag import (
    OPENWEIGHT_EJECTPATH_FLAG,
    TENANT_HARDENING_FLAG,
    openweight_ejectpath_on,
    tenant_hardening_on,
)
from tools.model_gateway.gateway import (
    ACCEPTED_EXTERNAL_ROLES,
    DEFAULT_CLAUDE_ROUTE_NAME,
    DEFAULT_ROUTES,
    GatewayCall,
    GatewayConfigError,
    LiteLLMGateway,
    ModelRoute,
    default_gateway,
    enforce_boundary,
)

__all__ = [
    "ACCEPTED_EXTERNAL_ROLES",
    "DEFAULT_CLAUDE_ROUTE_NAME",
    "DEFAULT_MOCK_URL",
    "DEFAULT_ROUTES",
    "EJECTPATH_ROUTE_NAME",
    "EjectPathInactiveError",
    "GatewayCall",
    "GatewayConfigError",
    "LiteLLMGateway",
    "ModelRoute",
    "OPENWEIGHT_EJECTPATH_FLAG",
    "OpenWeightBackend",
    "TENANT_HARDENING_FLAG",
    "build_route",
    "default_gateway",
    "enforce_boundary",
    "mock_call",
    "openweight_ejectpath_on",
    "register_ejectpath",
    "tenant_hardening_on",
]
