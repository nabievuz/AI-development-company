from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import engine

TIER_FOUNDER = "founder"
TIER_CXO = "cxo"
TIER_LEAD = "lead"
TIER_IC = "ic"
TIER_AUDIT = "audit"
TIER_ORCHESTRATOR = "orchestrator"

DEFAULT_LADDER = (TIER_IC, TIER_LEAD, TIER_CXO, TIER_FOUNDER)

DEPT_GOVERNANCE = "governance"
DEPT_ENGINEERING = "engineering"
DEPT_PRODUCT = "product"
DEPT_OPERATIONS = "operations"
DEPT_ORG = "org"


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    department: str
    permission: str
    min_tier: str
    own_scoped: bool = False


MODULES: tuple[Module, ...] = (
    Module("overview", "Command Overview", DEPT_ORG, "audit.read", TIER_IC),
    Module("org.directory", "Org Directory", DEPT_ORG, "audit.read", TIER_IC),
    Module("product.board", "Board & Risk", DEPT_PRODUCT, "audit.read", TIER_IC),
    Module("engineering.waves", "Wave Timeline", DEPT_ENGINEERING, "audit.read", TIER_IC),
    Module("engineering.runs", "Run Feed", DEPT_ENGINEERING, "audit.read", TIER_IC),
    Module("engineering.agents", "Per-Agent Usage", DEPT_ENGINEERING, "audit.read", TIER_LEAD),
    Module("engineering.tools", "Per-Tool Usage", DEPT_ENGINEERING, "audit.read", TIER_LEAD),
    Module("engineering.quality", "Quality Health", DEPT_ENGINEERING, "audit.read", TIER_LEAD),
    Module("operations.metrics", "Metrics T1-T7", DEPT_OPERATIONS, "audit.read", TIER_LEAD),
    Module("operations.memory", "Memory Health", DEPT_OPERATIONS, "audit.read", TIER_LEAD),
    Module("operations.cost", "Budget Burn", DEPT_OPERATIONS, "audit.read", TIER_CXO),
    Module("governance.flags", "Feature Flags", DEPT_GOVERNANCE, "audit.read", TIER_LEAD),
    Module("governance.audit", "Audit Trail", DEPT_GOVERNANCE, "audit.read", TIER_LEAD),
    Module("governance.gates", "GATE-6 Decisions", DEPT_GOVERNANCE, "audit.read", TIER_CXO),
    Module("governance.rbac", "Access Control", DEPT_GOVERNANCE, "audit.read", TIER_CXO),
    Module("governance.interrupts", "Action Console", DEPT_GOVERNANCE, "audit.read", TIER_CXO),
)

MODULES_BY_ID: dict[str, Module] = {m.id: m for m in MODULES}

@dataclass(frozen=True)
class Action:
    id: str
    permission: str
    min_tier: str


ACTIONS: tuple[Action, ...] = (
    Action("goal.submit", "board.work", TIER_FOUNDER),
    Action("run.trigger", "run.trigger", TIER_FOUNDER),
    Action("gate.approve", "gate.approve", TIER_FOUNDER),
)

CROSS_DEPARTMENT_TIERS = frozenset({TIER_FOUNDER, TIER_CXO, TIER_AUDIT})


def _org_path() -> Path:
    return engine.config_dir() / "org.yaml"


_ORG_CACHE: dict[str, Any] = {"key": None, "document": {}, "tiers": {}}


def _org_signature() -> tuple[str, float, int] | None:
    path = _org_path()
    try:
        stat = path.stat()
    except OSError:
        return None
    return (str(path), stat.st_mtime, stat.st_size)


def _org_document() -> dict[str, Any]:
    signature = _org_signature()
    if signature is not None and _ORG_CACHE["key"] == signature:
        return _ORG_CACHE["document"]
    mod, _ = engine.try_load("yaml")
    document: dict[str, Any] = {}
    if mod is not None and signature is not None:
        try:
            loaded = mod.safe_load(_org_path().read_text(encoding="utf-8"))
            document = loaded if isinstance(loaded, dict) else {}
        except Exception:
            document = {}
    _ORG_CACHE["key"] = signature
    _ORG_CACHE["document"] = document
    _ORG_CACHE["tiers"] = {}
    return document


def ladder() -> tuple[str, ...]:
    raw = _org_document().get("escalation_ladder")
    if not isinstance(raw, list):
        return DEFAULT_LADDER
    rungs = tuple(str(r).strip().lower() for r in raw if str(r).strip())
    return rungs or DEFAULT_LADDER


def _rank_map() -> dict[str, int]:
    ranks = {name: index + 1 for index, name in enumerate(ladder())}
    ranks.setdefault(TIER_IC, 1)
    ranks.setdefault(TIER_LEAD, 2)
    ranks.setdefault(TIER_CXO, 3)
    ranks.setdefault(TIER_FOUNDER, 4)
    ranks[TIER_AUDIT] = ranks[TIER_CXO]
    ranks[TIER_ORCHESTRATOR] = ranks[TIER_IC]
    return ranks


def rank_of(tier: str) -> int:
    return _rank_map().get(str(tier).strip().lower(), 0)


def role_tiers() -> dict[str, str]:
    doc = _org_document()
    cached = _ORG_CACHE.get("tiers")
    if cached:
        return cached
    roles = doc.get("roles")
    departments = doc.get("departments")
    if not isinstance(roles, list):
        return {}
    managers = set()
    if isinstance(departments, list):
        for dept in departments:
            if isinstance(dept, dict) and dept.get("manager_role"):
                managers.add(str(dept["manager_role"]))
    has_reports: set[str] = set()
    for role in roles:
        if isinstance(role, dict) and role.get("reports_to"):
            has_reports.add(str(role["reports_to"]))
    tiers: dict[str, str] = {}
    for role in roles:
        if not isinstance(role, dict) or not role.get("key"):
            continue
        key = str(role["key"])
        reports_to = role.get("reports_to")
        if key in managers or reports_to in (None, "", "ceo", "chairman"):
            tiers[key] = TIER_CXO
        elif key in has_reports:
            tiers[key] = TIER_LEAD
        else:
            tiers[key] = TIER_IC
    _ORG_CACHE["tiers"] = tiers
    return tiers


def role_key_of(principal: str) -> str:
    text = str(principal).strip().lower()
    for prefix in ("agent:", "agent/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return ""


def tier_of_principal(principal: str) -> str:
    text = str(principal).strip().lower()
    if text == TIER_FOUNDER:
        return TIER_FOUNDER
    if text in {"audit-team", "audit_team", "audit-reader"}:
        return TIER_AUDIT
    if text == TIER_ORCHESTRATOR:
        return TIER_ORCHESTRATOR
    role = role_key_of(text)
    if not role:
        return TIER_IC
    return role_tiers().get(role, TIER_IC)


def department_of_principal(principal: str) -> str:
    role = role_key_of(principal)
    if not role:
        return ""
    for entry in _org_document().get("roles") or []:
        if isinstance(entry, dict) and str(entry.get("key")) == role:
            return str(entry.get("dept") or "")
    return ""


def _substrate(principal: str, permission: str, own_scoped: bool, grants: dict) -> tuple[str, str]:
    rbac, error = engine.try_load("rbac")
    if rbac is None:
        return "deny", error
    scope = {"owner": str(principal)} if own_scoped else None
    try:
        return rbac.decide(principal, permission, scope=scope, config=grants or None)
    except Exception as exc:
        return "deny", f"rbac decision failed: {exc}"


def _tier_allows(module: Module, tier: str) -> bool:
    return rank_of(tier) >= rank_of(module.min_tier)


def role_tier(role: str) -> str:
    key = str(role).strip().lower()
    if not key:
        return ""
    if key in _rank_map():
        return key
    return role_tiers().get(key, "")


def role_department(role: str) -> str:
    key = str(role).strip().lower()
    for entry in _org_document().get("roles") or []:
        if isinstance(entry, dict) and str(entry.get("key")) == key:
            return str(entry.get("dept") or "")
    return ""


def _narrow(principal_tier: str, overlay_tier: str) -> str:
    if not overlay_tier:
        return principal_tier
    if rank_of(overlay_tier) < rank_of(principal_tier):
        return overlay_tier
    return principal_tier


def _department_allows(module: Module, tier: str, department: str) -> bool:
    if module.department == DEPT_ORG or not department:
        return True
    if tier in CROSS_DEPARTMENT_TIERS:
        return True
    return module.department == department


def capability_set(principal: str, grants: dict | None = None, role: str = "") -> dict[str, Any]:
    base_tier = tier_of_principal(principal)
    overlay_tier = role_tier(role)
    tier = _narrow(base_tier, overlay_tier)
    department = role_department(role) or department_of_principal(principal)
    resolved = grants or {}
    modules: list[str] = []
    denied: list[dict[str, str]] = []
    for module in MODULES:
        decision, reason = _substrate(principal, module.permission, module.own_scoped, resolved)
        if decision != "allow":
            denied.append({"module": module.id, "reason": reason, "stage": "substrate"})
            continue
        if not _tier_allows(module, tier):
            denied.append(
                {
                    "module": module.id,
                    "reason": f"tier {tier!r} is below the {module.min_tier!r} floor for this module",
                    "stage": "org_tier",
                }
            )
            continue
        if not _department_allows(module, tier, department):
            denied.append(
                {
                    "module": module.id,
                    "reason": f"module belongs to {module.department!r}, operator is scoped to {department!r}",
                    "stage": "department",
                }
            )
            continue
        modules.append(module.id)
    actions: list[str] = []
    for action in ACTIONS:
        decision, reason = _substrate(principal, action.permission, False, resolved)
        if decision != "allow":
            denied.append({"module": action.id, "reason": reason, "stage": "substrate"})
            continue
        if rank_of(tier) < rank_of(action.min_tier):
            denied.append(
                {
                    "module": action.id,
                    "reason": f"acting at tier {tier!r}; {action.id} requires {action.min_tier!r}",
                    "stage": "org_tier",
                }
            )
            continue
        actions.append(action.id)
    return {
        "principal": str(principal),
        "tier": tier,
        "base_tier": base_tier,
        "role": str(role or ""),
        "department": department,
        "ladder": list(ladder()),
        "modules": modules,
        "actions": sorted(actions),
        "denied": denied,
    }


def visible_modules(principal: str, grants: dict | None = None, role: str = "") -> set[str]:
    return set(capability_set(principal, grants, role)["modules"])


def module_catalogue() -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "title": m.title,
            "department": m.department,
            "permission": m.permission,
            "min_tier": m.min_tier,
        }
        for m in MODULES
    ]
