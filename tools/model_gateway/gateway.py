"""gateway.py — in-tenant LiteLLM model gateway (FR-004, TN-1), DAS-1583.

Realizes the ADR-0009 admission layer as a real transport chokepoint on the
ADR-0034 SDK runner (design ``docs/design/ws-e-tenant-hardening.md`` §4.1):
every model call resolves through this gateway to an in-tenant endpoint; the
near-term default is the Claude subscription over **account auth** (Q9) —
the SOLE accepted external exception (``config/tenant_boundary.yaml``
``accepted_external_roles: [model]``). Any OTHER route this gateway holds —
or any route mistakenly registered under a non-``model`` role — that carries
code/IP and resolves off-box is a **config error that BLOCKS the run** (TN-1),
enforced by REUSING the landed ``scripts/check_in_tenant.py`` guard verbatim
(no parallel boundary check, per design §4 "no BOM element adds a parallel
boundary check").

The auth path stays swappable (FR-004): callers select a route by name, never
a provider SDK — Claude-subscription (default) <-> Bedrock/Vertex in-tenant
<-> the deferred vLLM/SGLang eject-path (``ejectpath.py``) are all the SAME
shape, swapped via config, not an agent rewrite.

Ships behind ``ws_e_tenant_hardening`` (default OFF, ``config/features.yaml``,
read via ``tools/model_gateway/flag.py``); importing/instantiating this
module does not change any interactive ``/daslab-cycle`` wave — it is a
library, exactly like ``scripts/ws_b_admission.py`` (design §4.1 honesty
reconciliation with ADR-0009: this gateway is the chokepoint realized on the
*future* SDK runner, not a retrofit onto the harness).
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a repo dependency
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
TENANT_BOUNDARY_PATH = ROOT / "config" / "tenant_boundary.yaml"

# ---------------------------------------------------------------------------
# Lazy, path-based loading of sibling repo modules — REUSE, never reimplement
# (mirrors tools/observability/otlp_exporter.py's `_load_module`). Avoids a
# package install/fork and keeps this ticket's footprint to tools/model_gateway/.
# ---------------------------------------------------------------------------


def _load_module(relpath: str, name: str) -> Any:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
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
    """Read the SSOT-declared ``claude_model`` endpoint host from
    ``config/tenant_boundary.yaml`` (R2, GATE-3 residual). Fail-closed: any
    parse problem or a missing entry returns ``""`` — an empty host never
    matches, so a mis-read config REFUSES every model route rather than
    silently accepting one.
    """
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


# Re-exported so callers of this module need not separately import ws_b_admission.
def _admission_symbols() -> tuple[Any, Any, Any, Any]:
    mod = _ws_b_admission_mod()
    return mod.admit, mod.AdmissionDecision, mod.UsageEstimate, mod.CreditState


# ---------------------------------------------------------------------------
# TN-1 boundary — the one accepted proprietary exception (Q9).
# ---------------------------------------------------------------------------

ACCEPTED_EXTERNAL_ROLES = frozenset({"model"})
DEFAULT_CLAUDE_ROUTE_NAME = "claude_subscription"


class GatewayConfigError(Exception):
    """Raised when a route fails the TN-1 in-tenant precondition (fail-closed).

    Never raised AFTER a model call is attempted — registration- and call-time
    checks both run strictly before any side effect (design §4, "a config
    error that BLOCKS the run").
    """


@dataclass(frozen=True)
class ModelRoute:
    """One gateway-declared backend a model call may resolve to.

    Mirrors a LiteLLM ``model_list`` entry: ``name`` is the caller-facing
    route id, ``url`` the backend endpoint, ``role`` the TN-1 role tag
    (``"model"`` is the sole role the boundary accepts external — matches
    ``config/tenant_boundary.yaml``'s ``accepted_external_roles``), ``auth``
    names the swappable auth path (``account`` / ``api_key`` / ``none`` —
    never the secret material itself, Tier-M discipline).
    """

    name: str
    url: str
    role: str = "model"
    auth: str = "account"
    note: str = ""


@dataclass(frozen=True)
class GatewayCall:
    """A resolved, TN-1-checked, admission-checked model call.

    ``admission.admitted`` tells the caller whether the model call may
    proceed. This dataclass never carries a live network handle — building
    one is side-effect-free; the actual call stays the runner's job
    (ADR-0009: the gateway governs admission, not the call itself).
    """

    route: ModelRoute
    ticket_id: str
    model: str
    admission: Any  # ws_b_admission.AdmissionDecision (typed loosely: lazy import)


# The near-term default (Q9): Claude subscription via account auth — the sole
# `accepted_external_roles` exception in `config/tenant_boundary.yaml`.
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
    """TN-1 fail-closed precondition (design §4). Raises on violation.

    A route whose ``role`` is the sole accepted exception (``"model"``) may
    resolve external ONLY to the ``config/tenant_boundary.yaml``-declared
    ``claude_model`` host (R2, GATE-3 residual DAS-1585): the
    ``accepted_external_roles: [model]`` exception pins to that ONE
    sanctioned Claude host, it does not blanket-exempt every ``role="model"``
    route. A rogue route claiming ``role="model"`` but pointing at any OTHER
    host is REFUSED fail-closed, exactly like a non-model external role.
    Every OTHER role MUST resolve in-tenant per
    ``scripts/check_in_tenant.is_in_tenant`` (REUSED verbatim) — a
    hosted/external code/IP endpoint outside that exception is a config
    error that BLOCKS, never a silent pass-through.
    """
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
    """The in-tenant model gateway (FR-004) — the swappable routing surface.

    Holds a small route table (LiteLLM ``model_list``-shaped); ``call()``
    resolves a route, re-enforces TN-1 (defense in depth), then runs the
    request through the ADR-0009 admission layer
    (``scripts/ws_b_admission.admit`` — REUSED, never re-implemented) before
    returning a well-formed :class:`GatewayCall`. Holds no mutable global
    state; a caller builds one instance per run.
    """

    def __init__(self, routes: tuple[ModelRoute, ...] = DEFAULT_ROUTES) -> None:
        self._routes: dict[str, ModelRoute] = {}
        for r in routes:
            self.register(r)

    def register(self, route: ModelRoute) -> None:
        """Add/replace a route. Enforces TN-1 at REGISTRATION time — fail
        closed before the route can ever be selected, not only at call time.
        """
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
        """Resolve ``route_name``, re-check TN-1, then admit via ws_b_admission.

        Raises :class:`GatewayConfigError` on a TN-1 boundary violation. Never
        itself makes the model call — that stays the runner's job (ADR-0009);
        this returns a :class:`GatewayCall` whose ``.admission.admitted``
        tells the caller whether the call may proceed.
        """
        route = self.resolve(route_name)
        enforce_boundary(route)  # defense in depth: re-check even a stored route
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
    """Convenience constructor: the gateway wired to the Q9 default route only."""
    return LiteLLMGateway()
