from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


DEFAULT_MOCK_URL = "http://127.0.0.1:8000"


class EjectPathInactiveError(Exception):
    pass


@dataclass(frozen=True)
class OpenWeightBackend:

    url: str = DEFAULT_MOCK_URL
    engine: str = "vllm"
    auth: str = "none"


def build_route(backend: OpenWeightBackend | None = None) -> ModelRoute:
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
    assert route.role not in ACCEPTED_EXTERNAL_ROLES
    enforce_boundary(route)
    return route


def register_ejectpath(
    gw: LiteLLMGateway,
    backend: OpenWeightBackend | None = None,
    features_path: Path | None = None,
) -> ModelRoute:
    if not openweight_ejectpath_on(features_path):
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
    features_path: Path | None = None,
) -> GatewayCall:
    register_ejectpath(gw, backend, features_path)
    try:
        return gw.call(
            route_name=EJECTPATH_ROUTE_NAME,
            ticket_id=ticket_id,
            role=role,
            model=model,
        )
    except GatewayConfigError:
        raise
