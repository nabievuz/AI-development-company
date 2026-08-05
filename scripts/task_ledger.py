
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pulse_checkpoint as _pc


DEFAULT_RUNS_DIR: Path = _pc.DEFAULT_RUNS_DIR
generate_ulid = _pc.generate_ulid

_LEDGER_FILENAME = "task-ledger.md"
_NONE_PLACEHOLDER = "_(none)_"


_FACT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("given", "Given"),
    ("known", "Known"),
    ("to_look_up", "To look up"),
    ("educated_guesses", "Educated guesses"),
)


@dataclass
class Facts:

    given: list[str] = field(default_factory=list)
    known: list[str] = field(default_factory=list)
    to_look_up: list[str] = field(default_factory=list)
    educated_guesses: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "given": list(self.given),
            "known": list(self.known),
            "to_look_up": list(self.to_look_up),
            "educated_guesses": list(self.educated_guesses),
        }


def _coerce_facts(facts: Facts | dict[str, list[str]]) -> Facts:
    if isinstance(facts, Facts):
        return facts
    if isinstance(facts, dict):
        return Facts(
            given=list(facts.get("given", [])),
            known=list(facts.get("known", [])),
            to_look_up=list(facts.get("to_look_up", [])),
            educated_guesses=list(facts.get("educated_guesses", [])),
        )
    raise TypeError(f"facts must be Facts or dict, got {type(facts).__name__}")


def _runs_dir(runs_dir: Path | None) -> Path:
    return runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR


def ledger_path(run_id: str, runs_dir: Path | None = None) -> Path:
    return _runs_dir(runs_dir) / run_id / _LEDGER_FILENAME


def _render_list(items: list[str]) -> str:
    if not items:
        return f"- {_NONE_PLACEHOLDER}"
    return "\n".join(f"- {item}" for item in items)


def _render_plan(plan: list[str]) -> str:
    if not plan:
        return f"1. {_NONE_PLACEHOLDER}"
    return "\n".join(f"{i}. {step}" for i, step in enumerate(plan, start=1))


def render_task_ledger(
    *,
    run_id: str,
    facts: Facts | dict[str, list[str]],
    plan: list[str],
    created_at: str,
    updated_at: str,
    revision: int,
    goal: str | None = None,
    wave: int | None = None,
) -> str:
    f = _coerce_facts(facts)
    lines: list[str] = [
        f"# Task Ledger — {run_id}",
        "",
        "<!-- ORGANISM WS2 LOOM · P7 outer loop · task-ledger "
        "(ADR-0023 sibling artifact).",
        "     Runtime state — gitignored under board/runs/ (ADR-0023 §5).",
        "     Regenerated on replan; NOT append-only. Do not hand-edit — "
        "regenerate via scripts/task_ledger.py. -->",
        "",
        f"- run_id: {run_id}",
        f"- goal: {goal if goal is not None else ''}",
        f"- revision: {revision}",
        f"- wave: {wave if wave is not None else ''}",
        f"- created_at: {created_at}",
        f"- updated_at: {updated_at}",
        "",
        "## Facts",
        "",
    ]
    fact_map = f.as_dict()
    for attr, heading in _FACT_SECTIONS:
        lines.append(f"### {heading}")
        lines.append("")
        lines.append(_render_list(fact_map[attr]))
        lines.append("")
    lines.append("## Plan")
    lines.append("")
    lines.append(_render_plan(plan))
    lines.append("")
    return "\n".join(lines)


def _parse_list_block(block_lines: list[str]) -> list[str]:
    items: list[str] = []
    for raw in block_lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("- "):
            item = line[2:].strip()
        elif line[:1].isdigit() and ". " in line:
            item = line.split(". ", 1)[1].strip()
        else:
            continue
        if item == _NONE_PLACEHOLDER:
            continue
        items.append(item)
    return items


def _parse_ledger(text: str) -> dict[str, Any]:
    heading_to_attr = {heading: attr for attr, heading in _FACT_SECTIONS}
    meta: dict[str, str] = {}
    facts_buckets: dict[str, list[str]] = {attr: [] for attr, _ in _FACT_SECTIONS}
    plan: list[str] = []


    section: Any = None
    buffer: list[str] = []

    def _flush() -> None:
        nonlocal buffer, plan
        if section is None:
            buffer = []
            return
        parsed = _parse_list_block(buffer)
        if section == "plan":
            plan.extend(parsed)
        else:
            facts_buckets[section[1]].extend(parsed)
        buffer = []

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("### "):
            _flush()
            heading = stripped[4:].strip()
            attr = heading_to_attr.get(heading)
            section = ("fact", attr) if attr is not None else None
            continue
        if stripped.startswith("## "):
            _flush()
            section = "plan" if stripped[3:].strip() == "Plan" else None
            continue
        if section is None and stripped.startswith("- ") and ": " in stripped:

            key, _, value = stripped[2:].partition(": ")
            meta[key.strip()] = value.strip()
            continue
        if section is not None:
            buffer.append(line)
    _flush()

    return {"meta": meta, "facts": facts_buckets, "plan": plan}


def read_task_ledger(run_id: str, runs_dir: Path | None = None) -> dict[str, Any]:
    path = ledger_path(run_id, runs_dir)
    if not path.exists():
        raise FileNotFoundError(f"no task-ledger for run_id {run_id!r} at {path}")
    parsed = _parse_ledger(path.read_text(encoding="utf-8"))
    meta = parsed["meta"]
    facts = Facts(
        given=parsed["facts"]["given"],
        known=parsed["facts"]["known"],
        to_look_up=parsed["facts"]["to_look_up"],
        educated_guesses=parsed["facts"]["educated_guesses"],
    )

    def _int_or_none(v: str | None) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except ValueError:
            return None

    return {
        "run_id": meta.get("run_id", run_id),
        "goal": (meta.get("goal") or None),
        "revision": _int_or_none(meta.get("revision")) or 1,
        "wave": _int_or_none(meta.get("wave")),
        "created_at": meta.get("created_at", ""),
        "updated_at": meta.get("updated_at", ""),
        "facts": facts,
        "plan": parsed["plan"],
    }


def build_task_ledger(
    *,
    run_id: str,
    facts: Facts | dict[str, list[str]],
    plan: list[str],
    created_at: str,
    goal: str | None = None,
    wave: int | None = None,
    runs_dir: Path | None = None,
) -> Path:
    path = ledger_path(run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_task_ledger(
        run_id=run_id,
        facts=facts,
        plan=plan,
        created_at=created_at,
        updated_at=created_at,
        revision=1,
        goal=goal,
        wave=wave,
    )
    path.write_text(content, encoding="utf-8")
    return path


def update_task_ledger(
    *,
    run_id: str,
    created_at: str,
    facts: Facts | dict[str, list[str]] | None = None,
    plan: list[str] | None = None,
    goal: str | None = None,
    wave: int | None = None,
    runs_dir: Path | None = None,
) -> Path:
    existing = read_task_ledger(run_id, runs_dir)

    new_facts = _coerce_facts(facts) if facts is not None else existing["facts"]
    new_plan = plan if plan is not None else existing["plan"]
    new_goal = goal if goal is not None else existing["goal"]
    new_wave = wave if wave is not None else existing["wave"]

    path = ledger_path(run_id, runs_dir)
    content = render_task_ledger(
        run_id=run_id,
        facts=new_facts,
        plan=new_plan,
        created_at=existing["created_at"],
        updated_at=created_at,
        revision=existing["revision"] + 1,
        goal=new_goal,
        wave=new_wave,
    )
    path.write_text(content, encoding="utf-8")
    return path
