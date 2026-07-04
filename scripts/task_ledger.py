"""task_ledger.py — Per-run task-ledger writer (DAS-1469 / ORGANISM WS2 LOOM).

The **task-ledger** is the GATE-3 outer-loop (P7) deliverable of ORGANISM WS2
"LOOM".  Where the WS1 run-model (ADR-0023, DAS-1443/1444) durably records
*what happened* (event log, wave checkpoints, per-ticket completions), the
task-ledger records *what the run believed and intended*:

  1. the **facts** the wave is operating on, structured as
     *given / known / to-look-up / educated-guesses*, and
  2. the **plan** — the wave's ordered work.

It is written per run to ``board/runs/<run_id>/task-ledger.md`` — a **new
sibling artifact** alongside ``manifest.json`` and ``wave-NNN.checkpoint.json``
in the run-artifact tree.  Per ADR-0023 §5 the whole ``board/runs/<run_id>/``
tree is gitignored runtime state EXCEPT ``run-summary.md``; the task-ledger is
runtime state and stays gitignored (the existing ``.gitignore`` rule
``board/runs/**`` + ``!board/runs/*/run-summary.md`` already covers it — no
un-ignore is added).

**Regenerated on replan (NOT append-only).** When the wave revises its facts or
its plan, :func:`update_task_ledger` regenerates the file so it always reflects
the current understanding — it replaces the affected section and bumps the
``revision`` counter; it never appends a stale second copy of a section.

Design invariants (EXTEND the WS1 run-model, do NOT fork it):
- The run-dir conventions come from ``scripts/pulse_checkpoint.py``: this module
  reuses ``pulse_checkpoint.DEFAULT_RUNS_DIR`` and ``generate_ulid()`` rather
  than re-deriving a second run-dir scheme or a second ULID source.
- ``created_at`` is always an *argument* (injectable for tests — never generated
  inside a pure helper), matching the WS1 ``created_at``-is-always-supplied
  discipline.
- No new third-party dependency; no event emission (the ledger is a standalone
  human-readable artifact, not an event — no ADR-0025 shadow concern applies).

Public API
----------
    Facts                         (dataclass: given/known/to_look_up/educated_guesses)
    build_task_ledger(*, run_id, facts, plan, created_at, ...)   -> Path
    update_task_ledger(*, run_id, created_at, facts=None, plan=None, ...) -> Path
    read_task_ledger(run_id, runs_dir=None)                      -> dict
    render_task_ledger(...)       -> str   (pure — no I/O)
    ledger_path(run_id, runs_dir=None)     -> Path
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Reuse the WS1 run-model conventions (EXTEND, do not fork) — DEFAULT_RUNS_DIR
# and generate_ulid come from pulse_checkpoint; we never re-derive them here.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pulse_checkpoint as _pc  # noqa: E402

# Re-export the shared run-dir default so callers bind to one source of truth.
DEFAULT_RUNS_DIR: Path = _pc.DEFAULT_RUNS_DIR
generate_ulid = _pc.generate_ulid  # single ULID source (ADR-0023 §1)

_LEDGER_FILENAME = "task-ledger.md"
_NONE_PLACEHOLDER = "_(none)_"

# The four fact buckets, in canonical render order.  The tuple is
# (dataclass-field-name, markdown-heading) so render and parse share one map.
_FACT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("given", "Given"),
    ("known", "Known"),
    ("to_look_up", "To look up"),
    ("educated_guesses", "Educated guesses"),
)


# ---------------------------------------------------------------------------
# Facts — the epistemic state the wave planned from
# ---------------------------------------------------------------------------


@dataclass
class Facts:
    """The wave's working facts, bucketed by epistemic status.

    - ``given``            — supplied by the operator / ticket (ground truth).
    - ``known``            — established from the repo / prior waves.
    - ``to_look_up``       — open questions the wave must resolve.
    - ``educated_guesses`` — working assumptions, explicitly flagged as such.
    """

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
    """Accept either a Facts instance or a plain dict of buckets."""
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


# ---------------------------------------------------------------------------
# Path resolution — reuse the pulse_checkpoint run-dir scheme
# ---------------------------------------------------------------------------


def _runs_dir(runs_dir: Path | None) -> Path:
    return runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR


def ledger_path(run_id: str, runs_dir: Path | None = None) -> Path:
    """Return ``board/runs/<run_id>/task-ledger.md`` (canonical run-dir scheme)."""
    return _runs_dir(runs_dir) / run_id / _LEDGER_FILENAME


# ---------------------------------------------------------------------------
# Render — pure markdown emission (no I/O)
# ---------------------------------------------------------------------------


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
    """Render the full task-ledger markdown (pure — no filesystem access).

    Kept separate from the writer so tests can assert on the exact text and so
    a caller can render without touching disk.  The output round-trips through
    :func:`read_task_ledger`.
    """
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


# ---------------------------------------------------------------------------
# Parse — read the ledger back into a structured dict (round-trips render)
# ---------------------------------------------------------------------------


def _parse_list_block(block_lines: list[str]) -> list[str]:
    items: list[str] = []
    for raw in block_lines:
        line = raw.strip()
        if not line:
            continue
        # Strip an unordered "- " or ordered "N. " marker.
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

    # section state machine: None | ("fact", attr) | "plan"
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
        else:  # ("fact", attr)
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
            # metadata line: "- key: value"
            key, _, value = stripped[2:].partition(": ")
            meta[key.strip()] = value.strip()
            continue
        if section is not None:
            buffer.append(line)
    _flush()

    return {"meta": meta, "facts": facts_buckets, "plan": plan}


def read_task_ledger(run_id: str, runs_dir: Path | None = None) -> dict[str, Any]:
    """Read and parse ``board/runs/<run_id>/task-ledger.md`` into a dict.

    Returns:
        A dict with keys:
        - ``run_id`` (str), ``goal`` (str | None), ``revision`` (int),
          ``wave`` (int | None), ``created_at`` (str), ``updated_at`` (str)
        - ``facts`` — a :class:`Facts` instance
        - ``plan`` — ``list[str]`` (ordered)

    Raises:
        FileNotFoundError: if no ledger exists for ``run_id``.
    """
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


# ---------------------------------------------------------------------------
# Build — write the initial ledger for a run
# ---------------------------------------------------------------------------


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
    """Write the initial ``board/runs/<run_id>/task-ledger.md`` for a run.

    ``revision`` starts at 1; ``created_at`` and ``updated_at`` are both set to
    the supplied ``created_at`` (injectable — never generated here, matching the
    WS1 discipline).  The run directory is created if absent, reusing the
    pulse_checkpoint run-dir scheme (``board/runs/<run_id>/``).

    Args:
        run_id:     ULID run join key (mint via :func:`generate_ulid`).
        facts:      A :class:`Facts` (or dict of the four buckets).
        plan:       Ordered list of plan steps.
        created_at: ISO-8601 UTC timestamp (caller-supplied — injectable).
        goal:       Optional run goal label.
        wave:       Optional 1-based wave index the ledger was cut at.
        runs_dir:   Path to ``board/runs/`` (default: canonical).

    Returns:
        The path written.
    """
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


# ---------------------------------------------------------------------------
# Update — regenerate on replan (NOT append)
# ---------------------------------------------------------------------------


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
    """Regenerate the task-ledger on replan — replace, never append.

    Reads the existing ledger, bumps ``revision``, sets ``updated_at`` to the
    supplied ``created_at`` (injectable), and writes a **fresh** file reflecting
    the current understanding.  The original ``created_at`` is preserved.  Either
    the facts or the plan (or both) may be revised in one call:

    - **facts-update path:** pass ``facts=`` (``plan`` omitted → carried forward).
    - **plan-update path:**  pass ``plan=``  (``facts`` omitted → carried forward).

    An omitted section is carried forward from the existing ledger unchanged, so
    a replan never drops the section it did not touch and never leaves a stale
    duplicate of the section it did touch.

    Args:
        run_id:     ULID run join key.
        created_at: ISO-8601 UTC timestamp of this regeneration (→ ``updated_at``;
                    injectable — never generated here).
        facts:      New facts, or ``None`` to carry the existing facts forward.
        plan:       New plan, or ``None`` to carry the existing plan forward.
        goal:       New goal, or ``None`` to carry the existing goal forward.
        wave:       New wave index, or ``None`` to carry the existing one forward.
        runs_dir:   Path to ``board/runs/`` (default: canonical).

    Returns:
        The path written.

    Raises:
        FileNotFoundError: if no ledger exists to regenerate (build one first).
    """
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
        created_at=existing["created_at"],  # preserve original creation time
        updated_at=created_at,  # this regeneration's timestamp
        revision=existing["revision"] + 1,
        goal=new_goal,
        wave=new_wave,
    )
    path.write_text(content, encoding="utf-8")
    return path
