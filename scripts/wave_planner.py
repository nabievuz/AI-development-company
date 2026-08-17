from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import check_clarifications as _cc

ACTIONABLE_TICKET_STATUSES = frozenset({"todo", "backlog"})
SATISFIED_DEPENDENCY_STATUSES = frozenset({"done", "closed", "merged", "shipped"})

DEFAULT_PRIORITY = "p3"
_PRIORITY_RANK: dict[str, int] = {"p0": 0, "p1": 1, "p2": 2, "p3": 3, "p4": 4}
_UNRANKED_PRIORITY = 99

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FRONTMATTER_KV_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE
)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_TRUE_TOKENS = frozenset({"true", "yes", "1"})

CLARIFICATION_MARKER_RE = _cc.MARKER_RE


class UnknownRoleError(KeyError):
    pass


class DuplicateTicketError(ValueError):
    pass


class RefusalReason(StrEnum):
    NOT_ACTIONABLE = "not_actionable"
    DEFERRED = "deferred"
    CLARIFY_BLOCKED = "clarify_blocked"
    UNMET_DEPENDENCY = "unmet_dependency"
    OPEN_PREDECESSOR_GATE = "open_predecessor_gate"
    ZONE_CONFLICT = "zone_conflict"
    NO_MODEL_FOR_ROLE = "no_model_for_role"
    WAVE_FULL = "wave_full"


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    role: str
    status: str
    zone: str = ""
    dept: str = ""
    depends_on: tuple[str, ...] = ()
    gate: str = ""
    priority: str = DEFAULT_PRIORITY
    declared_model: str = ""
    deferred: bool = False
    clarification_markers: int = 0
    author: str = ""


@dataclass(frozen=True)
class OrgModel:
    role_models: Mapping[str, str]
    gate_order: tuple[str, ...] = ()

    def model_for(self, role: str) -> str:
        model = self.role_models.get(role, "")
        if not model:
            raise UnknownRoleError(
                f"no model allocated for role {role!r}; known roles: "
                f"{sorted(self.role_models)}"
            )
        return model

    def predecessor_gates(self, gate: str) -> tuple[str, ...]:
        if gate not in self.gate_order:
            return ()
        return tuple(self.gate_order[: self.gate_order.index(gate)])


@dataclass(frozen=True)
class PlannedTicket:
    ticket_id: str
    role: str
    model: str
    zone: str
    priority_rank: int


@dataclass(frozen=True)
class RefusedTicket:
    ticket_id: str
    reason: RefusalReason
    detail: str = ""


@dataclass(frozen=True)
class WavePlan:
    goal: str
    dispatch: tuple[PlannedTicket, ...] = ()
    refused: tuple[RefusedTicket, ...] = ()
    occupied_zones: frozenset[str] = frozenset()

    @property
    def ticket_ids(self) -> tuple[str, ...]:
        return tuple(pt.ticket_id for pt in self.dispatch)

    @property
    def zones(self) -> frozenset[str]:
        return frozenset(pt.zone for pt in self.dispatch)

    @property
    def is_empty(self) -> bool:
        return not self.dispatch

    def refusal_for(self, ticket_id: str) -> RefusedTicket | None:
        for refusal in self.refused:
            if refusal.ticket_id == ticket_id:
                return refusal
        return None


def priority_rank(priority: str) -> int:
    return _PRIORITY_RANK.get(str(priority).strip().lower(), _UNRANKED_PRIORITY)


def normalized_status(status: str) -> str:
    return str(status).strip().lower()


def is_actionable_status(status: str) -> bool:
    return normalized_status(status) in ACTIONABLE_TICKET_STATUSES


def effective_zone(ticket: Ticket) -> str:
    return ticket.zone.strip() or ticket.dept.strip() or ticket.ticket_id


def unmet_dependencies(ticket: Ticket, statuses: Mapping[str, str]) -> tuple[str, ...]:
    unmet: list[str] = []
    for dependency in ticket.depends_on:
        dependency = dependency.strip()
        if not dependency:
            continue
        status = normalized_status(statuses.get(dependency, ""))
        if status not in SATISFIED_DEPENDENCY_STATUSES:
            unmet.append(dependency)
    return tuple(unmet)


def dependencies_satisfied(ticket: Ticket, statuses: Mapping[str, str]) -> bool:
    return not unmet_dependencies(ticket, statuses)


_GATE_ID_RE = re.compile(r"GATE-[1-6]", re.IGNORECASE)


def gate_of(fields: Mapping[str, str]) -> str:
    for key in ("stage", "gate"):
        match = _GATE_ID_RE.search(str(fields.get(key, "")))
        if match:
            return match.group(0).upper()
    return ""


def open_predecessor_gates(
    ticket: Ticket, org: OrgModel, closed_gates: Iterable[str]
) -> tuple[str, ...]:
    gate = ticket.gate.strip()
    if not gate:
        return ()
    closed = {str(g).strip() for g in closed_gates}
    return tuple(g for g in org.predecessor_gates(gate) if g not in closed)


def ordering_key(ticket: Ticket) -> tuple[int, str]:
    return (priority_rank(ticket.priority), ticket.ticket_id)


def _status_index(tickets: Sequence[Ticket]) -> dict[str, str]:
    index: dict[str, str] = {}
    for ticket in tickets:
        if ticket.ticket_id in index:
            raise DuplicateTicketError(
                f"ticket id {ticket.ticket_id!r} appears more than once on the board"
            )
        index[ticket.ticket_id] = normalized_status(ticket.status)
    return index


def plan_wave(
    tickets: Sequence[Ticket],
    org: OrgModel,
    occupied_zones: Iterable[str],
    *,
    goal: str = "",
    closed_gates: Iterable[str] = (),
    max_wave_size: int | None = None,
) -> WavePlan:
    if max_wave_size is not None and max_wave_size < 0:
        raise ValueError(f"max_wave_size must be non-negative; got {max_wave_size!r}")

    statuses = _status_index(tickets)
    occupied = frozenset(str(z).strip() for z in occupied_zones if str(z).strip())
    closed = frozenset(str(g).strip() for g in closed_gates if str(g).strip())

    taken_zones: set[str] = set(occupied)
    dispatch: list[PlannedTicket] = []
    refused: list[RefusedTicket] = []

    for ticket in sorted(tickets, key=ordering_key):
        if not is_actionable_status(ticket.status):
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.NOT_ACTIONABLE,
                    f"status {normalized_status(ticket.status)!r} is not one of "
                    f"{sorted(ACTIONABLE_TICKET_STATUSES)}",
                )
            )
            continue

        if ticket.deferred:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.DEFERRED,
                    "carries defer: true — a deferred ticket is never dispatched until "
                    "a human clears the flag",
                )
            )
            continue

        if ticket.clarification_markers:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.CLARIFY_BLOCKED,
                    f"carries {ticket.clarification_markers} unresolved "
                    f"[NEEDS CLARIFICATION] marker(s) — clarify-blocked work is not "
                    f"actionable and goes back to "
                    f"{ticket.author or 'its author'} for review, never to a code agent",
                )
            )
            continue

        unmet = unmet_dependencies(ticket, statuses)
        if unmet:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.UNMET_DEPENDENCY,
                    "unmet dependencies: " + ", ".join(unmet),
                )
            )
            continue

        open_gates = open_predecessor_gates(ticket, org, closed)
        if open_gates:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.OPEN_PREDECESSOR_GATE,
                    "open predecessor gates: " + ", ".join(open_gates),
                )
            )
            continue

        model = org.role_models.get(ticket.role, "")
        if not model:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.NO_MODEL_FOR_ROLE,
                    f"role {ticket.role!r} has no model allocation",
                )
            )
            continue

        zone = effective_zone(ticket)
        if zone in taken_zones:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.ZONE_CONFLICT,
                    f"zone {zone!r} is already claimed in this wave",
                )
            )
            continue

        if max_wave_size is not None and len(dispatch) >= max_wave_size:
            refused.append(
                RefusedTicket(
                    ticket.ticket_id,
                    RefusalReason.WAVE_FULL,
                    f"wave already holds the maximum of {max_wave_size} ticket(s)",
                )
            )
            continue

        taken_zones.add(zone)
        dispatch.append(
            PlannedTicket(
                ticket_id=ticket.ticket_id,
                role=ticket.role,
                model=model,
                zone=zone,
                priority_rank=priority_rank(ticket.priority),
            )
        )

    return WavePlan(
        goal=goal,
        dispatch=tuple(dispatch),
        refused=tuple(refused),
        occupied_zones=occupied,
    )


def parse_frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for key, value in _FRONTMATTER_KV_RE.findall(match.group(1)):
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def parse_id_list(raw: str) -> tuple[str, ...]:
    raw = (raw or "").strip()
    if not raw:
        return ()
    raw = raw.removeprefix("[").removesuffix("]")
    return tuple(
        item.strip().strip('"').strip("'")
        for item in raw.split(",")
        if item.strip().strip('"').strip("'")
    )


def is_deferred(raw: str) -> bool:
    return str(raw).strip().lower() in _TRUE_TOKENS


def count_clarification_markers(body: str) -> int:
    return len(CLARIFICATION_MARKER_RE.findall(strip_code_blocks(body)))


def strip_code_blocks(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text)


def frontmatter_body(text: str) -> str:
    match = _FRONTMATTER_RE.match(text)
    return text[match.end():] if match else text


def ticket_from_frontmatter(
    fields: Mapping[str, str],
    *,
    fallback_id: str,
    body: str = "",
) -> Ticket:
    return Ticket(
        ticket_id=(fields.get("id", "") or fallback_id).strip(),
        role=fields.get("assignee", "").strip(),
        status=fields.get("status", "").strip(),
        zone=fields.get("zone", "").strip(),
        dept=fields.get("dept", "").strip(),
        depends_on=parse_id_list(fields.get("depends_on", "")),
        gate=gate_of(fields),
        priority=(fields.get("priority", "") or DEFAULT_PRIORITY).strip(),
        declared_model=fields.get("model", "").strip(),
        deferred=is_deferred(fields.get("defer", "")),
        clarification_markers=count_clarification_markers(body),
        author=fields.get("author", "").strip(),
    )


def load_board_tickets(board_dir: Path | str, *, pattern: str = "DAS-*.md") -> tuple[Ticket, ...]:
    board_dir = Path(board_dir)
    if not board_dir.is_dir():
        raise NotADirectoryError(f"board directory not found: {board_dir}")
    tickets: list[Ticket] = []
    for path in sorted(board_dir.glob(pattern)):
        text = path.read_text(encoding="utf-8")
        fields = parse_frontmatter(text)
        tickets.append(
            ticket_from_frontmatter(
                fields,
                fallback_id=ticket_id_from_stem(path.stem),
                body=frontmatter_body(text),
            )
        )
    return tuple(tickets)


def ticket_id_from_stem(stem: str) -> str:
    parts = stem.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return stem


def org_model_from_mapping(data: Mapping[str, object]) -> OrgModel:
    role_models: dict[str, str] = {}
    roles = data.get("roles")
    if isinstance(roles, Mapping):
        for role, spec in roles.items():
            if isinstance(spec, Mapping):
                model = spec.get("model") or spec.get("model_cap") or ""
            else:
                model = spec or ""
            if str(model).strip():
                role_models[str(role)] = str(model).strip()
    elif isinstance(roles, Sequence) and not isinstance(roles, str):
        for spec in roles:
            if not isinstance(spec, Mapping):
                continue
            role = spec.get("key") or spec.get("role") or spec.get("name") or ""
            model = spec.get("model") or spec.get("model_cap") or ""
            if str(role).strip() and str(model).strip():
                role_models[str(role).strip()] = str(model).strip()
    allocation = data.get("model_allocation")
    if isinstance(allocation, Mapping):
        for role, model in allocation.items():
            if str(model).strip():
                role_models[str(role)] = str(model).strip()
    gates = data.get("gates")
    gate_order = (
        tuple(str(g) for g in gates)
        if isinstance(gates, Sequence) and not isinstance(gates, str)
        else schema_gate_order()
    )
    return OrgModel(role_models=role_models, gate_order=gate_order)


def schema_gate_order() -> tuple[str, ...]:
    try:
        import _org_generated
    except ImportError:
        return ()
    gates = getattr(_org_generated, "GATES", ())
    return tuple(str(g) for g in gates)


def load_org_model(path: Path | str) -> OrgModel:
    import yaml

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"org model not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"org model at {path} must be a mapping; got {type(data).__name__}")
    org = org_model_from_mapping(data)
    if not org.role_models:
        raise ValueError(f"org model at {path} allocates no models to any role")
    return org
