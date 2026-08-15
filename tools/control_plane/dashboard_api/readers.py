from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from . import capabilities, engine

NO_DATA = "no data yet — appears once live waves run; the loop is in shadow mode"


def panel(available: bool, reason: str = "", **payload: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"available": available, "reason": reason}
    body.update(payload)
    return body


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _read_jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return rows
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    if limit > 0:
        return rows[-limit:]
    return rows


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def org_directory() -> dict[str, Any]:
    yaml_mod, error = engine.try_load("yaml")
    if yaml_mod is None:
        return panel(False, error)
    path = engine.config_dir() / "org.yaml"
    if not path.is_file():
        return panel(False, f"missing {engine.rel(path)}")
    try:
        doc = yaml_mod.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return panel(False, f"unreadable org model: {exc}")
    departments = doc.get("departments") if isinstance(doc.get("departments"), list) else []
    raw_roles = doc.get("roles") if isinstance(doc.get("roles"), list) else []
    tiers = capabilities.role_tiers()
    templates = engine.agent_templates_dir()
    reports: dict[str, list[str]] = {}
    roles: list[dict[str, Any]] = []
    for entry in raw_roles:
        if not isinstance(entry, dict) or not entry.get("key"):
            continue
        key = str(entry["key"])
        manager = entry.get("reports_to")
        manager_key = str(manager) if manager else ""
        if manager_key:
            reports.setdefault(manager_key, []).append(key)
        charter = entry.get("charter") if isinstance(entry.get("charter"), dict) else {}
        roles.append(
            {
                "key": key,
                "title": str(entry.get("title") or key),
                "department": str(entry.get("dept") or ""),
                "model": str(entry.get("model") or ""),
                "effort": str(entry.get("effort") or ""),
                "reports_to": manager_key,
                "tier": tiers.get(key, capabilities.TIER_IC),
                "mission": engine.scrub(charter.get("mission") or "", 400),
                "has_template": (templates / f"{key}.md").is_file(),
                "tool_grants": len(entry.get("tool_grants") or []),
            }
        )
    for role in roles:
        role["direct_reports"] = sorted(reports.get(role["key"], []))
    by_department: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_model: dict[str, int] = {}
    for role in roles:
        by_department[role["department"]] = by_department.get(role["department"], 0) + 1
        by_tier[role["tier"]] = by_tier.get(role["tier"], 0) + 1
        model = role["model"] or "(unset)"
        by_model[model] = by_model.get(model, 0) + 1
    dept_rows = [
        {
            "key": str(d.get("key") or ""),
            "title": str(d.get("title") or ""),
            "manager_role": str(d.get("manager_role") or ""),
            "headcount": by_department.get(str(d.get("key") or ""), 0),
        }
        for d in departments
        if isinstance(d, dict)
    ]
    return panel(
        bool(roles),
        "" if roles else "org model defines no roles",
        departments=dept_rows,
        roles=roles,
        totals={
            "roles": len(roles),
            "departments": len(dept_rows),
            "by_department": by_department,
            "by_tier": by_tier,
            "by_model": by_model,
            "templated": sum(1 for r in roles if r["has_template"]),
        },
        ladder=list(capabilities.ladder()),
    )


def org_overview() -> dict[str, Any]:
    full = org_directory()
    if not full.get("available"):
        return full
    return panel(
        True,
        "",
        departments=full.get("departments", []),
        totals=full.get("totals", {}),
        ladder=full.get("ladder", []),
    )


def feature_flags() -> dict[str, Any]:
    flags_mod, error = engine.try_load("feature_flags")
    if flags_mod is None:
        return panel(False, error)
    try:
        loaded = flags_mod.load(engine.config_dir() / "features.yaml")
    except Exception as exc:
        return panel(False, f"flag load failed: {exc}")
    rows = [{"flag": str(k), "enabled": bool(v)} for k, v in sorted(loaded.items())]
    return panel(
        bool(rows),
        "" if rows else "no feature flags declared",
        flags=rows,
        enabled=sum(1 for r in rows if r["enabled"]),
        total=len(rows),
    )


def rbac_catalogue() -> dict[str, Any]:
    yaml_mod, error = engine.try_load("yaml")
    if yaml_mod is None:
        return panel(False, error)
    path = engine.config_dir() / "rbac.yaml"
    if not path.is_file():
        return panel(False, f"missing {engine.rel(path)}")
    try:
        doc = yaml_mod.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return panel(False, f"unreadable rbac config: {exc}")
    rbac_mod, _ = engine.try_load("rbac")
    founder_only = sorted(getattr(rbac_mod, "FOUNDER_ONLY", ())) if rbac_mod else []
    grants = doc.get("grants") if isinstance(doc.get("grants"), dict) else {}
    kinds = doc.get("principal_kinds") if isinstance(doc.get("principal_kinds"), dict) else {}
    permissions = sorted({p for perms in grants.values() if isinstance(perms, dict) for p in perms})
    kind_rows = []
    for name, meta in kinds.items():
        info = meta if isinstance(meta, dict) else {}
        kind_rows.append(
            {
                "kind": str(name),
                "human": bool(info.get("human")),
                "description": engine.scrub(info.get("description") or "", 600),
                "grants": {str(k): str(v) for k, v in (grants.get(name) or {}).items()},
            }
        )
    authority = doc.get("gate_approval_authority")
    return panel(
        bool(kind_rows),
        "" if kind_rows else "no principal kinds declared",
        principal_kinds=kind_rows,
        permissions=permissions,
        founder_only=founder_only,
        gate_approval_authority=(
            {str(k): str(v) for k, v in authority.items()} if isinstance(authority, dict) else {}
        ),
        modules=capabilities.module_catalogue(),
    )


def _schema_requirements() -> tuple[list[str], bool, set[str]]:
    path = engine.interrupts_dir() / "schema.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], False, set()
    required = doc.get("required") if isinstance(doc.get("required"), list) else []
    props = doc.get("properties") if isinstance(doc.get("properties"), dict) else {}
    closed = doc.get("additionalProperties") is False
    return [str(r) for r in required], closed, {str(k) for k in props}


def interrupt_cards(now: datetime | None = None) -> dict[str, Any]:
    directory = engine.interrupts_dir()
    if not directory.is_dir():
        return panel(False, "no interrupt directory — nothing awaits a Founder answer")
    required, closed, known = _schema_requirements()
    moment = now or datetime.now(UTC)
    cards: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "schema.json":
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError) as exc:
            cards.append(
                {
                    "id": path.stem,
                    "readable": False,
                    "schema_valid": False,
                    "violations": [f"unreadable card: {exc}"],
                }
            )
            continue
        if not isinstance(doc, dict):
            cards.append(
                {
                    "id": path.stem,
                    "readable": False,
                    "schema_valid": False,
                    "violations": ["card is not a JSON object"],
                }
            )
            continue
        missing = [key for key in required if key not in doc]
        unknown = sorted(set(doc) - known) if closed and known else []
        violations = [f"missing required field {key!r}" for key in missing]
        violations += [f"undeclared field {key!r}" for key in unknown]
        options = doc.get("options")
        options = [str(o) for o in options] if isinstance(options, list) else []
        expires = str(doc.get("expires") or "")
        expired = False
        if expires:
            try:
                expired = datetime.fromisoformat(expires).replace(tzinfo=UTC) < moment
            except ValueError:
                violations.append(f"unparseable expires value {expires!r}")
        cards.append(
            {
                "id": str(doc.get("id") or path.stem),
                "readable": True,
                "ticket": str(doc.get("ticket") or ""),
                "question": engine.scrub(doc.get("question") or "", 600),
                "decision": engine.scrub(doc.get("decision") or "", 300),
                "resume": engine.scrub(doc.get("resume") or "", 300),
                "options": options,
                "conditions": [engine.scrub(c, 300) for c in (doc.get("conditions") or [])],
                "type": str(doc.get("type") or ""),
                "created_by": str(doc.get("created_by") or doc.get("authorized_by") or ""),
                "source": str(doc.get("source") or ""),
                "expires": expires,
                "expired": expired,
                "answerable": bool(options),
                "schema_valid": not violations,
                "violations": violations,
            }
        )
    divergent = sum(1 for c in cards if not c.get("schema_valid"))
    return panel(
        bool(cards),
        "" if cards else "no pending interrupt-cards — nothing awaits a Founder answer",
        cards=cards,
        total=len(cards),
        expired=sum(1 for c in cards if c.get("expired")),
        answerable=sum(1 for c in cards if c.get("answerable")),
        schema_divergent=divergent,
    )


def board_tickets(limit: int = 50) -> dict[str, Any]:
    directory = engine.tickets_dir()
    if not directory.is_dir():
        return panel(False, "no board/tickets directory")
    rows: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for path in sorted(directory.glob("*.md")):
        try:
            meta = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        status = meta.get("status", "?")
        priority = meta.get("priority", "?")
        by_status[status] = by_status.get(status, 0) + 1
        by_priority[priority] = by_priority.get(priority, 0) + 1
        rows.append(
            {
                "id": meta.get("id", path.stem),
                "title": engine.scrub(meta.get("title", ""), 200),
                "status": status,
                "priority": priority,
                "assignee": meta.get("assignee", ""),
                "updated": meta.get("updated", ""),
            }
        )
    rows.sort(key=lambda r: str(r.get("updated") or ""), reverse=True)
    return panel(
        bool(rows),
        "" if rows else "no tickets on the board yet",
        tickets=rows[:limit],
        total=len(rows),
        by_status=by_status,
        by_priority=by_priority,
        blocked=by_status.get("blocked", 0),
        in_review=by_status.get("in_review", 0),
    )


def waves(limit: int = 40) -> dict[str, Any]:
    metrics, error = engine.try_load("metrics_lib")
    if metrics is None:
        return panel(False, error)
    try:
        parsed = metrics.read_waves(str(engine.wave_log_path()))
    except Exception as exc:
        return panel(False, f"wave log unreadable: {exc}")
    if not parsed:
        return panel(False, NO_DATA)
    rows = []
    for wave in parsed:
        dispatched = wave.get("disp") or []
        mix: dict[str, int] = {}
        for model in dispatched:
            mix[str(model)] = mix.get(str(model), 0) + 1
        rows.append(
            {
                "start": _jsonable(wave.get("start")),
                "dispatched": len(dispatched),
                "model_mix": mix,
                "idle": not dispatched,
            }
        )
    return panel(
        True,
        "",
        waves=rows[-limit:],
        total=len(rows),
        dispatched_total=sum(r["dispatched"] for r in rows),
        idle_waves=sum(1 for r in rows if r["idle"]),
    )


def runs(limit: int = 40) -> dict[str, Any]:
    directory = engine.runs_dir()
    if not directory.is_dir():
        return panel(False, "no board/runs directory")
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        rows.append(
            {
                "file": engine.rel(path),
                "run": path.stem,
                "group": path.parent.name,
                "keys": sorted(str(k) for k in doc)[:24],
                "record": _jsonable(dict(list(doc.items())[:24])),
            }
        )
    return panel(
        bool(rows),
        "" if rows else "no run checkpoints recorded yet",
        runs=rows[:limit],
        total=len(rows),
    )


def audit_tail(limit: int = 100) -> dict[str, Any]:
    path = engine.board() / ".control-plane-audit.jsonl"
    rows = _read_jsonl(path, limit)
    if not rows:
        return panel(False, "no control-plane audit entries yet")
    decisions: dict[str, int] = {}
    actions: dict[str, int] = {}
    for row in rows:
        decision = str(row.get("decision") or "?")
        action = str(row.get("action") or "?")
        decisions[decision] = decisions.get(decision, 0) + 1
        actions[action] = actions.get(action, 0) + 1
    return panel(
        True,
        "",
        entries=[_jsonable(r) for r in reversed(rows)],
        total=len(rows),
        by_decision=decisions,
        by_action=actions,
        denials=decisions.get("deny", 0),
    )


def events_tail(limit: int = 100) -> dict[str, Any]:
    rows = _read_jsonl(engine.events_path(), limit)
    if not rows:
        return panel(False, NO_DATA)
    by_type: dict[str, int] = {}
    for row in rows:
        key = str(row.get("event_type") or "?")
        by_type[key] = by_type.get(key, 0) + 1
    return panel(
        True,
        "",
        events=[_jsonable(r) for r in reversed(rows)],
        total=len(rows),
        by_type=by_type,
    )


def agent_templates() -> dict[str, Any]:
    directory = engine.agent_templates_dir()
    if not directory.is_dir():
        return panel(False, "no governance/agent-templates directory")
    rows = [
        {"role": path.stem, "bytes": path.stat().st_size}
        for path in sorted(directory.glob("*.md"))
    ]
    return panel(bool(rows), "" if rows else "no agent templates", templates=rows, total=len(rows))
