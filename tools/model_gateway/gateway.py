from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
TENANT_BOUNDARY_PATH = ROOT / "config" / "tenant_boundary.yaml"


def _load_module(relpath: str, name: str) -> Any:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {relpath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_check_in_tenant = None
_ws_b_admission = None


def _check_in_tenant_mod() -> Any:
    global _check_in_tenant
    if _check_in_tenant is None:
        _check_in_tenant = _load_module(
            "scripts/check_in_tenant.py", "ws_e_check_in_tenant"
        )
    return _check_in_tenant


def _ws_b_admission_mod() -> Any:
    global _ws_b_admission
    if _ws_b_admission is None:
        _ws_b_admission = _load_module("scripts/ws_b_admission.py", "ws_e_ws_b_admission")
    return _ws_b_admission


_egress_guard = None


def _egress_guard_mod() -> Any:
    global _egress_guard
    if _egress_guard is None:
        _egress_guard = _load_module(
            "tools/mcp_bridges/egress_guard.py", "ws_e_gateway_egress_guard"
        )
    return _egress_guard


def _declared_claude_model_host() -> str:
    if yaml is None or not TENANT_BOUNDARY_PATH.is_file():
        return ""
    try:
        data = yaml.safe_load(TENANT_BOUNDARY_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return ""
    endpoints = data.get("endpoints") if isinstance(data, dict) else None
    if not isinstance(endpoints, list):
        return ""
    for ep in endpoints:
        if isinstance(ep, dict) and ep.get("name") == "claude_model":
            url = ep.get("url") or ""
            host = urlparse(str(url)).hostname or ""
            return host.strip().lower().rstrip(".")
    return ""


def _admission_symbols() -> tuple[Any, Any, Any, Any]:
    mod = _ws_b_admission_mod()
    return mod.admit, mod.AdmissionDecision, mod.UsageEstimate, mod.CreditState


ACCEPTED_EXTERNAL_ROLES = frozenset({"model"})
DEFAULT_CLAUDE_ROUTE_NAME = "claude_subscription"


class GatewayConfigError(Exception):
    pass


@dataclass(frozen=True)
class ModelRoute:

    name: str
    url: str
    role: str = "model"
    auth: str = "account"
    note: str = ""


@dataclass(frozen=True)
class GatewayCall:

    route: ModelRoute
    ticket_id: str
    model: str
    admission: Any


DEFAULT_ROUTES: tuple[ModelRoute, ...] = (
    ModelRoute(
        name=DEFAULT_CLAUDE_ROUTE_NAME,
        url="https://api.anthropic.com",
        role="model",
        auth="account",
        note=(
            "Q9 near-term default: Claude subscription over account auth, "
            "NOT a metered API key. Sole accepted external role=model exception."
        ),
    ),
)


def enforce_boundary(route: ModelRoute) -> None:
    cit = _check_in_tenant_mod()
    if route.role.strip().lower() in ACCEPTED_EXTERNAL_ROLES:
        declared_host = _declared_claude_model_host()
        eg = _egress_guard_mod()
        route_host = (urlparse(route.url).hostname or "").strip().lower().rstrip(".")
        if not declared_host or not eg.host_matches(route_host, [declared_host]):
            raise GatewayConfigError(
                f"TN-1 host-pin BLOCK: route {route.name!r} (role={route.role!r}) "
                f"resolves to {route.url!r} whose host is not the declared "
                f"claude_model host {declared_host!r} in config/tenant_boundary.yaml "
                "— the role=model exception is pinned to that ONE sanctioned host, "
                "not accepted blanket-external."
            )
        return
    if not cit.is_in_tenant(route.url):
        raise GatewayConfigError(
            f"TN-1 BLOCK: route {route.name!r} (role={route.role!r}) resolves to an "
            f"EXTERNAL host {route.url!r} — only role in "
            f"{sorted(ACCEPTED_EXTERNAL_ROLES)} may resolve outside the tenant."
        )


class LiteLLMGateway:

    def __init__(self, routes: tuple[ModelRoute, ...] = DEFAULT_ROUTES) -> None:
        self._routes: dict[str, ModelRoute] = {}
        for r in routes:
            self.register(r)

    def register(self, route: ModelRoute) -> None:
        enforce_boundary(route)
        self._routes[route.name] = route

    def routes(self) -> tuple[ModelRoute, ...]:
        return tuple(self._routes.values())

    def resolve(self, name: str) -> ModelRoute:
        try:
            return self._routes[name]
        except KeyError as exc:
            raise GatewayConfigError(f"no such gateway route: {name!r}") from exc

    def call(
        self,
        *,
        route_name: str,
        ticket_id: str,
        role: str,
        model: str,
        estimate: Any = None,
        credit_state: Any = None,
        budgets: dict[str, Any] | None = None,
    ) -> GatewayCall:
        route = self.resolve(route_name)
        enforce_boundary(route)
        admit, *_rest = _admission_symbols()
        decision = admit(
            ticket_id=ticket_id,
            role=role,
            model=model,
            estimate=estimate,
            credit_state=credit_state,
            budgets=budgets,
        )
        return GatewayCall(route=route, ticket_id=ticket_id, model=model, admission=decision)


def default_gateway() -> LiteLLMGateway:
    return LiteLLMGateway()
