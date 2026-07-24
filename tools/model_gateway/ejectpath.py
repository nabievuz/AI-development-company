"""ejectpath.py — DEFERRED vLLM/SGLang open-weight in-tenant eject-path (FR-005).

Design ``docs/design/ws-e-tenant-hardening.md`` §4.2: an open-weight in-tenant
inference eject-path (vLLM / SGLang behind the gateway) for a tenant whose
policy forbids ANY external model call, including the Claude subscription.
**NOT the near-term build** (Q9 keeps Claude-subscription the default,
``gateway.DEFAULT_ROUTES``) — this module exists so the eject-path is
*buildable and unit-testable now*, with **no live serving stack present**,
behind its **own** sub-flag ``ws_e_openweight_ejectpath`` (default OFF,
nested under the parent ``ws_e_tenant_hardening``, see ``flag.py``).

What this module proves, per design §4.2:
  (a) with the sub-flag OFF the route is inert — never selected, never
      registered onto a gateway;
  (b) the route target, when declared, MUST be an in-tenant host — the
      eject-path *strengthens* TN-1 (an open-weight model served in-tenant
      means even the model call no longer leaves the tenant); a caller
      that supplies an external URL is refused, not silently accepted;
  (c) no agent changes to switch to it — it is a :class:`gateway.ModelRoute`
      of the exact same shape as the Claude-subscription route, added to the
      SAME :class:`gateway.LiteLLMGateway` route table.

Live vLLM/SGLang serving against a real GPU/VM is explicitly OUT of this
ticket (the BLOCKED Deployment ticket DAS-1586) — this module talks to a
**mock** endpoint only; no serving process is stood up here.
"""
from __future__ import annotations

from dataclasses import dataclass

# Fully-qualified package imports (NOT bare `import flag`/`import gateway`):
# several sibling `tools/*` packages ship their own same-named `flag.py`
# (e.g. `tools/sandbox/flag.py`), and a bare module-name import gets cached
# in `sys.modules` by that bare name — the FIRST one imported in a pytest
# session wins for every subsequent bare `import flag` anywhere in the run.
# Qualifying under `tools.model_gateway.*` gives this package's modules their
# own distinct `sys.modules` keys, so they never collide with a same-named
# sibling module elsewhere in the repo (requires the repo root on
# `sys.path`, true for `python3 -m pytest` run from the repo root).
from tools.model_gateway.flag import openweight_ejectpath_on
from tools.model_gateway.gateway import (
    ACCEPTED_EXTERNAL_ROLES,
    GatewayCall,
    GatewayConfigError,
    LiteLLMGateway,
    ModelRoute,
    enforce_boundary,
)

EJECTPATH_ROUTE_NAME = "openweight_ejectpath"
# The default MOCK in-tenant target — a would-be local vLLM/SGLang server.
# Never resolved over a real network here; DAS-1586 (blocked) owns standing
# one up. Loopback keeps the default itself trivially TN-1-compliant.
DEFAULT_MOCK_URL = "http://127.0.0.1:8000"


class EjectPathInactiveError(Exception):
    """Raised when the eject-path is used while its sub-flag resolves OFF.

    Distinguishes "the adapter is disabled" from a :class:`gateway.
    GatewayConfigError` ("the adapter is enabled but misconfigured") — a
    caller can tell the two apart without string-matching an exception
    message.
    """


@dataclass(frozen=True)
class OpenWeightBackend:
    """One vLLM/SGLang backend declaration — engine + would-be endpoint.

    ``engine`` is descriptive only (``"vllm"`` / ``"sglang"``); it never
    changes the TN-1 evaluation, which looks solely at ``url``.
    """

    url: str = DEFAULT_MOCK_URL
    engine: str = "vllm"
    auth: str = "none"


def build_route(backend: OpenWeightBackend | None = None) -> ModelRoute:
    """Build the eject-path's :class:`gateway.ModelRoute`.

    Deliberately tags the route ``role="ejectpath"`` — NOT ``"model"`` — so
    it does NOT ride the ``accepted_external_roles`` exception the Claude
    route uses; the eject-path must independently prove it is in-tenant
    (design §4.2 item (b), "strengthens TN-1"). ``enforce_boundary`` (REUSED
    from ``gateway.py``, no parallel check) BLOCKS a caller-supplied external
    URL rather than silently accepting it.
    """
    backend = backend or OpenWeightBackend()
    route = ModelRoute(
        name=EJECTPATH_ROUTE_NAME,
        url=backend.url,
        role="ejectpath",
        auth=backend.auth,
        note=(
            f"DEFERRED {backend.engine} open-weight eject-path (FR-005) — "
            "in-tenant only, no external-role exception; behind "
            "ws_e_openweight_ejectpath (OFF by default)."
        ),
    )
    assert route.role not in ACCEPTED_EXTERNAL_ROLES  # nosec B101 - documents the design invariant
    enforce_boundary(route)  # BLOCKS here (not later) if backend.url is external
    return route


def register_ejectpath(
    gw: LiteLLMGateway, backend: OpenWeightBackend | None = None
) -> ModelRoute:
    """Register the eject-path route onto an existing gateway.

    Raises :class:`EjectPathInactiveError` while ``ws_e_openweight_ejectpath``
    (nested under ``ws_e_tenant_hardening``) is OFF — the DEFAULT, and the
    only state at merge. This is the inertness proof (design §4.2 item (a)):
    the route is never registered, so it can never be selected by
    ``gw.call(route_name=...)`` regardless of caller intent.
    """
    if not openweight_ejectpath_on():
        raise EjectPathInactiveError(
            "ws_e_openweight_ejectpath is OFF — the vLLM/SGLang eject-path is "
            "DEFERRED and inert; flip only on an explicit Founder decision."
        )
    route = build_route(backend)
    gw.register(route)
    return route


def mock_call(
    gw: LiteLLMGateway,
    *,
    ticket_id: str,
    role: str,
    model: str,
    backend: OpenWeightBackend | None = None,
) -> GatewayCall:
    """Register the eject-path (if the sub-flag is ON) and run one call
    against the mock endpoint, proving the call shape end-to-end without a
    live serving stack.

    Raises :class:`EjectPathInactiveError` if the sub-flag is OFF —
    identically to :func:`register_ejectpath` — so a caller cannot "call
    through" a disabled eject-path by any other door.
    """
    register_ejectpath(gw, backend)
    try:
        return gw.call(
            route_name=EJECTPATH_ROUTE_NAME,
            ticket_id=ticket_id,
            role=role,
            model=model,
        )
    except GatewayConfigError:  # pragma: no cover - defense in depth, unreachable
        raise
