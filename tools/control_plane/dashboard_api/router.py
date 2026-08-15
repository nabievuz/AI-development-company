from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from . import capabilities, readers, series

MAX_LIMIT = 500

QUERY_40 = Query(default=40, ge=1, le=MAX_LIMIT)
QUERY_50 = Query(default=50, ge=1, le=MAX_LIMIT)
QUERY_100 = Query(default=100, ge=1, le=MAX_LIMIT)


@dataclass(frozen=True)
class ControlPlaneDeps:
    identify: Callable[[Request], dict[str, Any]]
    audit: Callable[..., None]
    flag_on: Callable[[], bool]
    load_grants: Callable[[], dict[str, Any] | None]


class RequireModule:
    def __init__(self, deps: ControlPlaneDeps, module_id: str) -> None:
        self.deps = deps
        self.module_id = module_id

    def __call__(self, request: Request) -> dict[str, Any]:
        if not self.deps.flag_on():
            raise HTTPException(404, "control plane disabled (ws_h_control_plane OFF)")
        grants = self.deps.load_grants()
        if grants is None:
            raise HTTPException(503, "control plane RBAC not configured/loadable (fail-closed)")
        who = self.deps.identify(request)
        principal = str(who.get("principal") or "")
        capability = capabilities.capability_set(principal, grants, str(who.get("role") or ""))
        action = f"dashboard.{self.module_id}"
        if self.module_id and self.module_id not in capability["modules"]:
            reason = next(
                (d["reason"] for d in capability["denied"] if d["module"] == self.module_id),
                "module not in the effective capability set",
            )
            self.deps.audit(action, principal, str(who.get("kind") or ""), "deny", reason)
            raise HTTPException(
                403, f"principal '{principal}' may not read the '{self.module_id}' module"
            )
        self.deps.audit(action, principal, str(who.get("kind") or ""), "allow", capability["tier"])
        return {**who, "capability": capability}


def _safe(fn: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return readers.panel(False, f"module failed in isolation: {type(exc).__name__}: {exc}")


def _clamp(value: int) -> int:
    return max(1, min(int(value), MAX_LIMIT))


def build_router(deps: ControlPlaneDeps) -> APIRouter:
    router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

    def gate(module_id: str) -> Any:
        return Depends(RequireModule(deps, module_id))

    dep_overview = gate("overview")
    dep_org = gate("org.directory")
    dep_board = gate("product.board")
    dep_waves = gate("engineering.waves")
    dep_runs = gate("engineering.runs")
    dep_agents = gate("engineering.agents")
    dep_tools = gate("engineering.tools")
    dep_quality = gate("engineering.quality")
    dep_metrics = gate("operations.metrics")
    dep_memory = gate("operations.memory")
    dep_cost = gate("operations.cost")
    dep_flags = gate("governance.flags")
    dep_audit = gate("governance.audit")
    dep_gates = gate("governance.gates")
    dep_rbac = gate("governance.rbac")
    dep_interrupts = gate("governance.interrupts")

    @router.get("/me")
    def me(request: Request) -> dict[str, Any]:
        if not deps.flag_on():
            raise HTTPException(404, "control plane disabled (ws_h_control_plane OFF)")
        grants = deps.load_grants()
        if grants is None:
            raise HTTPException(503, "control plane RBAC not configured/loadable (fail-closed)")
        who = deps.identify(request)
        principal = str(who.get("principal") or "")
        capability = capabilities.capability_set(principal, grants, str(who.get("role") or ""))
        deps.audit("dashboard.me", principal, str(who.get("kind") or ""), "allow", capability["tier"])
        return {
            "user": who.get("user", "unknown"),
            "principal": principal,
            "kind": who.get("kind", ""),
            "role": capability["role"],
            "tier": capability["tier"],
            "base_tier": capability["base_tier"],
            "department": capability["department"],
            "ladder": capability["ladder"],
            "modules": capability["modules"],
            "actions": capability["actions"],
            "denied": capability["denied"],
            "catalogue": capabilities.module_catalogue(),
        }

    @router.get("/summary")
    def summary(who: dict = dep_overview) -> dict[str, Any]:
        visible = set(who["capability"]["modules"])
        panels: dict[str, Any] = {
            "org": _safe(readers.org_overview) if "org.directory" in visible else None,
            "board": _safe(readers.board_tickets) if "product.board" in visible else None,
            "projects": _safe(readers.project_boards, 1) if "product.board" in visible else None,
            "waves": _safe(readers.waves) if "engineering.waves" in visible else None,
            "interrupts": (
                _safe(readers.interrupt_cards) if "governance.interrupts" in visible else None
            ),
            "flags": _safe(readers.feature_flags) if "governance.flags" in visible else None,
            "metrics": _safe(series.health_tracks) if "operations.metrics" in visible else None,
            "cost": _safe(series.cost_ledger) if "operations.cost" in visible else None,
            "throughput": _safe(series.throughput) if "operations.metrics" in visible else None,
            "audit": _safe(readers.audit_tail, 25) if "governance.audit" in visible else None,
        }
        return {
            "tier": who["capability"]["tier"],
            "modules": sorted(visible),
            "panels": {k: v for k, v in panels.items() if v is not None},
        }

    @router.get("/org")
    def org(who: dict = dep_org) -> dict[str, Any]:
        return _safe(readers.org_directory)

    @router.get("/board")
    def board(
        who: dict = dep_board,
        limit: int = QUERY_50,
    ) -> dict[str, Any]:
        platform = _safe(readers.board_tickets, _clamp(limit))
        return {**platform, "projects": _safe(readers.project_boards, MAX_LIMIT)}

    @router.get("/waves")
    def wave_timeline(
        who: dict = dep_waves,
        limit: int = QUERY_40,
    ) -> dict[str, Any]:
        return _safe(readers.waves, _clamp(limit))

    @router.get("/runs")
    def run_feed(
        who: dict = dep_runs,
        limit: int = QUERY_40,
    ) -> dict[str, Any]:
        return _safe(readers.runs, _clamp(limit))

    @router.get("/events")
    def events(
        who: dict = dep_runs,
        limit: int = QUERY_100,
    ) -> dict[str, Any]:
        return _safe(readers.events_tail, _clamp(limit))

    @router.get("/agents")
    def agents(who: dict = dep_agents) -> dict[str, Any]:
        usage = _safe(series.agent_usage)
        return {**usage, "templates": _safe(readers.agent_templates)}

    @router.get("/tools")
    def tools(who: dict = dep_tools) -> dict[str, Any]:
        return _safe(series.tool_usage)

    @router.get("/quality")
    def quality(who: dict = dep_quality) -> dict[str, Any]:
        return {"tracks": _safe(series.health_tracks), "gate6": _safe(series.gate6_records)}

    @router.get("/metrics")
    def metrics(who: dict = dep_metrics) -> dict[str, Any]:
        return {"tracks": _safe(series.health_tracks), "throughput": _safe(series.throughput)}

    @router.get("/memory")
    def memory(who: dict = dep_memory) -> dict[str, Any]:
        return _safe(series.memory_health)

    @router.get("/cost")
    def cost(who: dict = dep_cost) -> dict[str, Any]:
        return _safe(series.cost_ledger)

    @router.get("/flags")
    def flags(who: dict = dep_flags) -> dict[str, Any]:
        return _safe(readers.feature_flags)

    @router.get("/audit")
    def audit_trail(
        who: dict = dep_audit,
        limit: int = QUERY_100,
    ) -> dict[str, Any]:
        return _safe(readers.audit_tail, _clamp(limit))

    @router.get("/gates")
    def gates(who: dict = dep_gates) -> dict[str, Any]:
        return _safe(series.gate6_records)

    @router.get("/rbac")
    def rbac_view(who: dict = dep_rbac) -> dict[str, Any]:
        return _safe(readers.rbac_catalogue)

    @router.get("/interrupts")
    def interrupts(who: dict = dep_interrupts) -> dict[str, Any]:
        return _safe(readers.interrupt_cards)

    return router
