from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

_GUARDRAILS_DIR = Path(__file__).resolve().parent
_GOVERNANCE_DIR = _GUARDRAILS_DIR.parent
if str(_GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(_GOVERNANCE_DIR))

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
)

DEFAULT_GUARDRAILS_DIR = _GUARDRAILS_DIR


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(m.group(1)):
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


def strip_frontmatter(text: str) -> str:
    return _FM_RE.sub("", text, count=1)


def _parse_list(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    raw = raw.removeprefix("[").removesuffix("]")
    return [item.strip().strip('"').strip("'") for item in raw.split(",") if item.strip()]


_ROUTING_ROW_RE = re.compile(
    r"^\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def load_role_table(routing_path: Path | None = None) -> dict[str, dict[str, str]]:
    if routing_path is not None and Path(routing_path).is_file():
        return _parse_legacy_routing_markdown(Path(routing_path))
    return _role_table_from_org_model()


def _parse_legacy_routing_markdown(routing_path: Path) -> dict[str, dict[str, str]]:
    text = routing_path.read_text(encoding="utf-8")
    table: dict[str, dict[str, str]] = {}
    for key, display, dept, reports_to in _ROUTING_ROW_RE.findall(text):
        table[key] = {
            "display": display.strip(),
            "dept": dept.strip(),
            "reports_to": reports_to.strip(),
        }
    return table


def _role_table_from_org_model() -> dict[str, dict[str, str]]:
    scripts_dir = _GOVERNANCE_DIR.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import org_model

    return {
        routing.role: {
            "display": routing.title,
            "dept": routing.dept,
            "reports_to": routing.reviewer_title or "",
        }
        for routing in org_model.routing_table()
    }


def load_guardrail_module(
    role: str, guardrails_dir: Path = DEFAULT_GUARDRAILS_DIR
) -> ModuleType | None:
    module_path = Path(guardrails_dir) / f"{role}.py"
    if not module_path.is_file():
        return None
    safe_name = "guardrails._role_" + re.sub(r"[^0-9a-zA-Z]+", "_", role)
    spec = importlib.util.spec_from_file_location(safe_name, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve(role: str, kind: str, guardrails_dir: Path):
    module = load_guardrail_module(role, guardrails_dir)
    attr = f"{kind}_guardrail"
    if module is not None and hasattr(module, attr):
        return getattr(module, attr)
    return default_input_guardrail if kind == "input" else default_output_guardrail


def run_input(
    role: str, ctx: GuardrailContext, guardrails_dir: Path = DEFAULT_GUARDRAILS_DIR
) -> GuardrailResult:
    return _resolve(role, "input", guardrails_dir)(ctx)


def run_output(
    role: str, ctx: GuardrailContext, guardrails_dir: Path = DEFAULT_GUARDRAILS_DIR
) -> GuardrailResult:
    return _resolve(role, "output", guardrails_dir)(ctx)


def _dep_statuses(board_dir: Path, dep_ids: list[str]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    board_dir = Path(board_dir)
    for dep in dep_ids:
        matches = sorted(board_dir.glob(f"{dep}-*.md"))
        if not matches:
            statuses[dep] = "missing"
            continue
        fm = parse_frontmatter(matches[0].read_text(encoding="utf-8"))
        statuses[dep] = (fm.get("status", "") or "missing").strip()
    return statuses


def build_context(
    ticket_path: Path,
    *,
    routing_path: Path | None = None,
    board_dir: Path,
    role: str | None = None,
    output: str | None = None,
    gate_open: bool = False,
) -> GuardrailContext:
    ticket_path = Path(ticket_path)
    text = ticket_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    body = strip_frontmatter(text)

    role_key = role or fm.get("assignee", "").strip()
    role_table = load_role_table(routing_path)
    role_dept = role_table.get(role_key, {}).get("dept", "")

    depends_on = _parse_list(fm.get("depends_on", ""))
    consumes = _parse_list(fm.get("consumes", ""))
    deps_status = _dep_statuses(board_dir, depends_on)

    return GuardrailContext(
        role=role_key,
        role_dept=role_dept,
        ticket_id=fm.get("id", "").strip() or ticket_path.stem,
        ticket_dept=fm.get("dept", "").strip(),
        status=fm.get("status", "").strip(),
        consumes=consumes,
        depends_on=depends_on,
        deps_status=deps_status,
        gate_open=gate_open,
        body=body,
        output=output,
        frontmatter=fm,
    )
