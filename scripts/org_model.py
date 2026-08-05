#!/usr/bin/env python3

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from _paths import ROOT

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    raise

ORG_CONFIG_PATH = ROOT / "config" / "org.yaml"


class OrgConfigError(RuntimeError):
    pass


class Model(StrEnum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


class Effort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class Authority(StrEnum):
    BINDING = "binding"
    ADD_ONLY = "add_only"


MODELS_WITHOUT_EFFORT: frozenset[Model] = frozenset({Model.HAIKU})
DEFAULT_EFFORT_BY_MODEL: dict[Model, Effort] = {
    Model.OPUS: Effort.HIGH,
    Model.SONNET: Effort.MEDIUM,
}
CHARTER_SECTION_TITLES: tuple[str, ...] = (
    "Mission",
    "Scope",
    "Definition of Done",
    "Escalation",
)


@dataclass(frozen=True)
class ToolGrant:
    server: str
    tools: tuple[str, ...]
    egress_profile: str

    def allowlist_entries(self) -> tuple[str, ...]:
        if any(tool == "*" for tool in self.tools):
            return (self.server,)
        return tuple(f"{self.server}__{tool}" for tool in self.tools)


@dataclass(frozen=True)
class RoleCharter:
    mission: str
    scope: str
    definition_of_done: str
    escalation: str

    def sections(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Mission", self.mission),
            ("Scope", self.scope),
            ("Definition of Done", self.definition_of_done),
            ("Escalation", self.escalation),
        )


@dataclass(frozen=True)
class Role:
    key: str
    dept: str
    title: str
    model: Model
    effort: Effort | None
    reports_to: str | None
    rationale: str
    charter: RoleCharter
    tool_grants: tuple[ToolGrant, ...]

    @property
    def supports_effort(self) -> bool:
        return self.model not in MODELS_WITHOUT_EFFORT


@dataclass(frozen=True)
class Department:
    key: str
    title: str
    manager_role: str


@dataclass(frozen=True)
class PrecedenceLevel:
    level: int
    key: str
    authority: Authority
    paths: tuple[str, ...]


@dataclass(frozen=True)
class Routing:
    role: str
    title: str
    dept: str
    reviewer: str | None
    reviewer_title: str


@dataclass(frozen=True)
class Org:
    version: int
    departments: tuple[Department, ...]
    roles: tuple[Role, ...]
    escalation_ladder: tuple[str, ...]
    precedence: tuple[PrecedenceLevel, ...]

    def role(self, key: str) -> Role:
        for role in self.roles:
            if role.key == key:
                return role
        raise KeyError(key)

    def has_role(self, key: str) -> bool:
        return any(role.key == key for role in self.roles)

    def role_keys(self) -> frozenset[str]:
        return frozenset(role.key for role in self.roles)

    def dept(self, key: str) -> Department:
        for department in self.departments:
            if department.key == key:
                return department
        raise KeyError(key)

    def dept_of(self, role_key: str) -> Department:
        return self.dept(self.role(role_key).dept)

    def roles_in(self, dept_key: str) -> tuple[Role, ...]:
        return tuple(role for role in self.roles if role.dept == dept_key)

    def model_for(self, key: str) -> Model:
        return self.role(key).model

    def effort_for(self, key: str) -> Effort | None:
        return self.role(key).effort

    def title_of(self, key: str | None) -> str:
        if key is None:
            return "the Board"
        return self.role(key).title

    def routing_for(self, key: str) -> Routing:
        role = self.role(key)
        return Routing(
            role=role.key,
            title=role.title,
            dept=role.dept,
            reviewer=role.reports_to,
            reviewer_title=self.title_of(role.reports_to),
        )

    def routing_table(self) -> tuple[Routing, ...]:
        return tuple(self.routing_for(role.key) for role in self.roles)

    def escalation_chain(self, key: str) -> tuple[str, ...]:
        chain: list[str] = []
        current = self.role(key).reports_to
        while current is not None and current not in chain:
            chain.append(current)
            current = self.role(current).reports_to
        return tuple(chain)

    def reviewer_for(self, key: str) -> str | None:
        reviewer = self.role(key).reports_to
        if reviewer is None or reviewer != key:
            return reviewer
        chain = self.escalation_chain(key)
        return chain[1] if len(chain) > 1 else None

    def levels_with_authority(self, authority: Authority) -> tuple[PrecedenceLevel, ...]:
        return tuple(level for level in self.precedence if level.authority is authority)

    def tool_allowlist(self) -> dict[str, list[str]]:
        grants: dict[str, set[str]] = {}
        for role in self.roles:
            for grant in role.tool_grants:
                for entry in grant.allowlist_entries():
                    grants.setdefault(entry, set()).add(role.key)
        return {entry: sorted(keys) for entry, keys in sorted(grants.items())}

    def model_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for role in self.roles:
            counts[role.model.value] = counts.get(role.model.value, 0) + 1
        return counts


def _require_mapping(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise OrgConfigError(f"{where}: expected a mapping, got {type(value).__name__}")
    return value


def _require_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrgConfigError(f"{where}: expected a non-empty string")
    return value


def _parse_model(value: object, where: str) -> Model:
    try:
        return Model(str(value))
    except ValueError:
        raise OrgConfigError(
            f"{where}: '{value}' is not a valid model tier "
            f"(expected one of {[m.value for m in Model]})"
        ) from None


def _parse_effort(value: object, model: Model, where: str) -> Effort | None:
    if model in MODELS_WITHOUT_EFFORT:
        if value not in (None, ""):
            raise OrgConfigError(f"{where}: model '{model.value}' does not support effort")
        return None
    if value in (None, ""):
        return DEFAULT_EFFORT_BY_MODEL[model]
    try:
        return Effort(str(value))
    except ValueError:
        raise OrgConfigError(
            f"{where}: '{value}' is not a valid effort "
            f"(expected one of {[e.value for e in Effort]})"
        ) from None


def _parse_tool_grants(raw: object, where: str) -> tuple[ToolGrant, ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, list):
        raise OrgConfigError(f"{where}: tool_grants must be a list")
    grants: list[ToolGrant] = []
    for index, item in enumerate(raw):
        spec = _require_mapping(item, f"{where}.tool_grants[{index}]")
        tools = spec.get("tools") or []
        if not isinstance(tools, list) or not tools:
            raise OrgConfigError(f"{where}.tool_grants[{index}]: 'tools' must be a non-empty list")
        grants.append(
            ToolGrant(
                server=_require_str(spec.get("server"), f"{where}.tool_grants[{index}].server"),
                tools=tuple(str(t) for t in tools),
                egress_profile=_require_str(
                    spec.get("egress_profile"), f"{where}.tool_grants[{index}].egress_profile"
                ),
            )
        )
    return tuple(grants)


def _parse_charter(raw: object, where: str) -> RoleCharter:
    spec = _require_mapping(raw, f"{where}.charter")
    return RoleCharter(
        mission=str(spec.get("mission") or ""),
        scope=str(spec.get("scope") or ""),
        definition_of_done=str(spec.get("definition_of_done") or ""),
        escalation=str(spec.get("escalation") or ""),
    )


def _parse_precedence(raw: object) -> tuple[PrecedenceLevel, ...]:
    if not isinstance(raw, list) or not raw:
        raise OrgConfigError("precedence: expected a non-empty list of levels")
    levels: list[PrecedenceLevel] = []
    for index, item in enumerate(raw):
        spec = _require_mapping(item, f"precedence[{index}]")
        try:
            authority = Authority(str(spec.get("authority")))
        except ValueError:
            raise OrgConfigError(
                f"precedence[{index}]: authority must be one of {[a.value for a in Authority]}"
            ) from None
        paths = spec.get("paths") or []
        if not isinstance(paths, list) or not paths:
            raise OrgConfigError(f"precedence[{index}]: 'paths' must be a non-empty list")
        levels.append(
            PrecedenceLevel(
                level=int(spec.get("level", index + 1)),
                key=_require_str(spec.get("key"), f"precedence[{index}].key"),
                authority=authority,
                paths=tuple(str(p) for p in paths),
            )
        )
    ordered = [level.level for level in levels]
    if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        raise OrgConfigError("precedence: levels must be unique and listed in ascending order")
    return tuple(levels)


def parse_org(data: object, source: str) -> Org:
    doc = _require_mapping(data, source)

    departments: list[Department] = []
    for index, item in enumerate(doc.get("departments") or []):
        spec = _require_mapping(item, f"departments[{index}]")
        departments.append(
            Department(
                key=_require_str(spec.get("key"), f"departments[{index}].key"),
                title=_require_str(spec.get("title"), f"departments[{index}].title"),
                manager_role=_require_str(
                    spec.get("manager_role"), f"departments[{index}].manager_role"
                ),
            )
        )
    if not departments:
        raise OrgConfigError(f"{source}: no departments declared")
    dept_keys = {d.key for d in departments}
    if len(dept_keys) != len(departments):
        raise OrgConfigError(f"{source}: duplicate department key")

    roles: list[Role] = []
    for index, item in enumerate(doc.get("roles") or []):
        spec = _require_mapping(item, f"roles[{index}]")
        key = _require_str(spec.get("key"), f"roles[{index}].key")
        where = f"roles[{key}]"
        dept = _require_str(spec.get("dept"), f"{where}.dept")
        if dept not in dept_keys:
            raise OrgConfigError(f"{where}: unknown department '{dept}'")
        model = _parse_model(spec.get("model"), f"{where}.model")
        reports_to = spec.get("reports_to")
        if reports_to is not None:
            reports_to = _require_str(reports_to, f"{where}.reports_to")
        roles.append(
            Role(
                key=key,
                dept=dept,
                title=_require_str(spec.get("title"), f"{where}.title"),
                model=model,
                effort=_parse_effort(spec.get("effort"), model, f"{where}.effort"),
                reports_to=reports_to,
                rationale=str(spec.get("rationale") or ""),
                charter=_parse_charter(spec.get("charter"), where),
                tool_grants=_parse_tool_grants(spec.get("tool_grants"), where),
            )
        )
    if not roles:
        raise OrgConfigError(f"{source}: no roles declared")
    role_keys = {r.key for r in roles}
    if len(role_keys) != len(roles):
        raise OrgConfigError(f"{source}: duplicate role key")
    for role in roles:
        if role.reports_to is not None and role.reports_to not in role_keys:
            raise OrgConfigError(f"roles[{role.key}].reports_to: unknown role '{role.reports_to}'")
        if role.reports_to == role.key:
            raise OrgConfigError(f"roles[{role.key}].reports_to: a role cannot report to itself")
    for department in departments:
        if department.manager_role not in role_keys:
            raise OrgConfigError(
                f"departments[{department.key}].manager_role: unknown role "
                f"'{department.manager_role}'"
            )

    ladder = doc.get("escalation_ladder") or []
    if not isinstance(ladder, list) or not ladder:
        raise OrgConfigError(f"{source}: escalation_ladder must be a non-empty list")

    return Org(
        version=int(doc.get("version", 0)),
        departments=tuple(departments),
        roles=tuple(roles),
        escalation_ladder=tuple(str(x) for x in ladder),
        precedence=_parse_precedence(doc.get("precedence")),
    )


@cache
def _load_cached(path_str: str) -> Org:
    path = Path(path_str)
    if not path.is_file():
        raise OrgConfigError(f"org config not found: {path}")
    return parse_org(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)


def load_org(path: Path | str | None = None) -> Org:
    return _load_cached(str(path or ORG_CONFIG_PATH))


def roles(path: Path | str | None = None) -> tuple[Role, ...]:
    return load_org(path).roles


def role(key: str, path: Path | str | None = None) -> Role:
    return load_org(path).role(key)


def dept(key: str, path: Path | str | None = None) -> Department:
    return load_org(path).dept(key)


def departments(path: Path | str | None = None) -> tuple[Department, ...]:
    return load_org(path).departments


def model_for(key: str, path: Path | str | None = None) -> Model:
    return load_org(path).model_for(key)


def effort_for(key: str, path: Path | str | None = None) -> Effort | None:
    return load_org(path).effort_for(key)


def known_role_keys(path: Path | str | None = None) -> frozenset[str]:
    return load_org(path).role_keys()


def routing_for(key: str, path: Path | str | None = None) -> Routing:
    return load_org(path).routing_for(key)


def routing_table(path: Path | str | None = None) -> tuple[Routing, ...]:
    return load_org(path).routing_table()


def precedence(path: Path | str | None = None) -> tuple[PrecedenceLevel, ...]:
    return load_org(path).precedence


def tool_allowlist(path: Path | str | None = None) -> dict[str, list[str]]:
    return load_org(path).tool_allowlist()
