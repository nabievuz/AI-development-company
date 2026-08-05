#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pulse_checkpoint as _pc
import task_ledger as _tl
from dgox.events import EventStore, build_replanned

DEFAULT_RUNS_DIR: Path = _pc.DEFAULT_RUNS_DIR
DEFAULT_STORE_PATH: Path = _pc.DEFAULT_STORE_PATH


DEFAULT_INTERRUPTS_DIR: Path = DEFAULT_RUNS_DIR.parent / "interrupts"

DEFAULT_WAVE_LEDGER_PATH: Path = DEFAULT_RUNS_DIR.parent / "wave-ledger.jsonl"

DEFAULT_TICKETS_DIR: Path = _pc.DEFAULT_TICKETS_DIR

_LEDGER_FILENAME = "progress-ledger.json"


FIXTURE_RUN_ID_PREFIX: str = "FIXTURE-"


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n(?:---|\.\.\.)\s*(?:\n|\Z)", re.DOTALL)

_ID_LINE_RE = re.compile(r"(?m)^id:[ \t]*(\S+)[ \t]*$")


def is_fixture_run_id(run_id: str) -> bool:
    return str(run_id).startswith(FIXTURE_RUN_ID_PREFIX)


def board_ticket_ids(tickets_dir: Path | str) -> set[str]:
    base = Path(tickets_dir)
    found: set[str] = set()
    if not base.is_dir():
        return found
    for path in sorted(base.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        block = _FRONTMATTER_RE.match(text)
        if block is None:
            continue
        match = _ID_LINE_RE.search(block.group(1))
        if match:
            found.add(match.group(1).strip().strip("'\""))
    return found


def read_wave_ledger(ledger_path: Path | str) -> tuple[list[dict[str, Any]], list[str]]:
    path = Path(ledger_path)
    entries: list[dict[str, Any]] = []
    problems: list[str] = []
    if not path.is_file():
        return entries, problems
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"wave-ledger line {lineno}: malformed JSON ({exc})")
            continue
        if not isinstance(entry, dict):
            problems.append(f"wave-ledger line {lineno}: entry is not a JSON object")
            continue
        entries.append(entry)
    return entries, problems


def verify_wave_ledger_evidence(
    ledger_path: Path | str,
    *,
    attest_dir: Path | str | None = None,
    tickets_dir: Path | str | None = None,
) -> list[str]:
    import wave_runner

    path = Path(ledger_path)
    problems: list[str] = list(
        wave_runner.verify_wave_ledger(path, attest_dir=attest_dir)
    )
    entries, parse_problems = read_wave_ledger(path)
    problems.extend(parse_problems)

    known_tickets = board_ticket_ids(
        tickets_dir if tickets_dir is not None else DEFAULT_TICKETS_DIR
    )
    board_label = str(tickets_dir if tickets_dir is not None else DEFAULT_TICKETS_DIR)

    for entry in entries:
        run_id = str(entry.get("run_id", ""))
        if is_fixture_run_id(run_id):
            problems.append(
                f"fixture entry in the committed wave-ledger: run_id {run_id!r} lives in "
                f"the reserved {FIXTURE_RUN_ID_PREFIX!r} namespace — a fixture is never evidence"
            )
        ticket_ids = entry.get("ticket_ids")
        if not isinstance(ticket_ids, list) or not ticket_ids:
            problems.append(
                f"wave-ledger entry run_id={run_id!r} carries no ticket_ids — "
                "an attestation of nothing is not evidence"
            )
            continue
        for ticket_id in ticket_ids:
            if str(ticket_id) not in known_tickets:
                problems.append(
                    f"wave-ledger entry run_id={run_id!r} references ticket "
                    f"{str(ticket_id)!r}, which does not exist on the board ({board_label}) "
                    "— an entry attesting a ticket that never existed is fiction"
                )

    return list(dict.fromkeys(problems))


LEDGER_FIELDS: dict[str, type] = {
    "request_satisfied": bool,
    "in_loop": bool,
    "progress_being_made": bool,
    "next_tickets": list,
    "instruction": str,
}


STALL_THRESHOLD: int = 3


DEFAULT_MAX_REPLANS: int = 2


_STALL_CARD_OPTIONS: tuple[str, ...] = (
    "replan-again",
    "accept-current-state",
    "abandon",
)


def validate_ledger(ledger: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(ledger, dict):
        return [f"ledger must be a JSON object; got {type(ledger).__name__}"]

    for name, typ in LEDGER_FIELDS.items():
        if name not in ledger:
            errors.append(f"missing required field: {name!r}")
            continue
        value = ledger[name]
        if typ is bool:

            if not isinstance(value, bool):
                errors.append(f"{name!r} must be a boolean; got {value!r}")
        elif typ is list:
            if not isinstance(value, list) or not all(
                isinstance(t, str) and t for t in value
            ):
                errors.append(f"{name!r} must be a list of non-empty strings; got {value!r}")
        elif typ is str and not isinstance(value, str):
            errors.append(f"{name!r} must be a string; got {value!r}")
    return errors


def _runs_dir(runs_dir: Path | None) -> Path:
    return runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR


def progress_ledger_path(run_id: str, runs_dir: Path | None = None) -> Path:
    return _runs_dir(runs_dir) / run_id / _LEDGER_FILENAME


def write_progress_ledger(
    *,
    run_id: str,
    request_satisfied: bool,
    in_loop: bool,
    progress_being_made: bool,
    next_tickets: list[str],
    instruction: str,
    runs_dir: Path | None = None,
) -> Path:
    ledger = {
        "request_satisfied": request_satisfied,
        "in_loop": in_loop,
        "progress_being_made": progress_being_made,
        "next_tickets": list(next_tickets),
        "instruction": instruction,
    }
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"cannot write invalid progress-ledger (errors: {errors})")
    path = progress_ledger_path(run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_progress_ledger(run_id: str, runs_dir: Path | None = None) -> dict[str, Any]:
    path = progress_ledger_path(run_id, runs_dir)
    if not path.exists():
        raise FileNotFoundError(f"no progress-ledger for run_id {run_id!r} at {path}")
    ledger = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"invalid progress-ledger at {path} (errors: {errors})")
    return ledger


def update_stall(stall: int, *, in_loop: bool, progress_being_made: bool) -> int:
    if in_loop or not progress_being_made:
        return stall + 1
    return max(0, stall - 1)


@dataclass
class LoopState:

    stall: int = 0
    max_replans: int = DEFAULT_MAX_REPLANS


@dataclass
class LoopDecision:

    action: str
    stall: int
    max_replans: int
    replanned: bool = False
    revision: int | None = None
    interrupt_card_path: Path | None = None
    ledger: dict[str, Any] = field(default_factory=dict, repr=False)


def _regenerate_task_ledger(
    *,
    run_id: str,
    ledger: dict[str, Any],
    wave: int,
    created_at: str,
    runs_dir: Path | None,
) -> int:
    existing = _tl.read_task_ledger(run_id, runs_dir)
    facts: _tl.Facts = existing["facts"]
    note = (
        f"Wave {wave}: replanned (stall > {STALL_THRESHOLD}); "
        f"steer: {ledger.get('instruction', '') or '(none)'}"
    )
    new_facts = _tl.Facts(
        given=list(facts.given),
        known=[*facts.known, note],
        to_look_up=list(facts.to_look_up),
        educated_guesses=list(facts.educated_guesses),
    )
    new_plan = list(ledger.get("next_tickets") or existing["plan"])
    _tl.update_task_ledger(
        run_id=run_id,
        created_at=created_at,
        facts=new_facts,
        plan=new_plan,
        wave=wave,
        runs_dir=runs_dir,
    )
    return existing["revision"] + 1


def _next_card_id(anchor_ticket: str, interrupts_dir: Path) -> str:
    n = 1
    if interrupts_dir.is_dir():
        prefix = f"{anchor_ticket}-stall-"
        existing = 0
        for p in interrupts_dir.glob(f"{prefix}*.json"):
            suffix = p.stem[len(prefix):]
            if suffix.isdigit():
                existing = max(existing, int(suffix))
        n = existing + 1
    return f"{anchor_ticket}-stall-{n}"


def raise_stall_interrupt_card(
    *,
    run_id: str,
    anchor_ticket: str,
    stall: int,
    wave: int,
    instruction: str,
    interrupts_dir: Path | None = None,
    created_by: str = "cto",
) -> Path:
    idir = interrupts_dir if interrupts_dir is not None else DEFAULT_INTERRUPTS_DIR
    idir.mkdir(parents=True, exist_ok=True)
    card_id = _next_card_id(anchor_ticket, idir)
    card = {
        "question": (
            f"The inner loop stalled (stall={stall} > {STALL_THRESHOLD}) and the "
            f"replan budget is exhausted at wave {wave}. How should the run proceed?"
        ),
        "options": list(_STALL_CARD_OPTIONS),
        "ticket": anchor_ticket,
        "payload": {
            "run_id": run_id,
            "wave": wave,
            "stall": stall,
            "instruction": instruction,
            "reason": "pause-on-stall: max_replans exhausted",
        },
        "created_by": created_by,
    }
    path = idir / f"{card_id}.json"
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def step_inner_loop(
    *,
    ledger: dict[str, Any],
    state: LoopState,
    run_id: str,
    anchor_ticket: str,
    wave: int,
    created_at: str,
    runs_dir: Path | None = None,
    store_path: Path | None = None,
    interrupts_dir: Path | None = None,
    emit_event: bool = True,
    created_by: str = "cto",
) -> LoopDecision:
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError(f"cannot step inner loop on invalid ledger (errors: {errors})")

    if ledger["request_satisfied"]:
        return LoopDecision(
            action="satisfied",
            stall=state.stall,
            max_replans=state.max_replans,
            ledger=ledger,
        )

    new_stall = update_stall(
        state.stall,
        in_loop=ledger["in_loop"],
        progress_being_made=ledger["progress_being_made"],
    )

    if new_stall <= STALL_THRESHOLD:
        state.stall = new_stall
        return LoopDecision(
            action="continue",
            stall=state.stall,
            max_replans=state.max_replans,
            ledger=ledger,
        )


    if state.max_replans > 0:
        revision = _regenerate_task_ledger(
            run_id=run_id,
            ledger=ledger,
            wave=wave,
            created_at=created_at,
            runs_dir=runs_dir,
        )
        state.max_replans -= 1
        state.stall = 0
        if emit_event:
            sp = store_path if store_path is not None else DEFAULT_STORE_PATH
            EventStore(sp).append(
                build_replanned(
                    ticket_id=anchor_ticket,
                    run_id=run_id,
                    wave=wave,
                    revision=revision,
                    stall=new_stall,
                    max_replans_remaining=state.max_replans,
                    reason=f"stall {new_stall} > {STALL_THRESHOLD}",
                    created_at=created_at,
                )
            )
        return LoopDecision(
            action="replanned",
            stall=state.stall,
            max_replans=state.max_replans,
            replanned=True,
            revision=revision,
            ledger=ledger,
        )


    card_path = raise_stall_interrupt_card(
        run_id=run_id,
        anchor_ticket=anchor_ticket,
        stall=new_stall,
        wave=wave,
        instruction=ledger.get("instruction", ""),
        interrupts_dir=interrupts_dir,
        created_by=created_by,
    )
    state.stall = new_stall
    return LoopDecision(
        action="paused",
        stall=state.stall,
        max_replans=state.max_replans,
        interrupt_card_path=card_path,
        ledger=ledger,
    )


def run_inner_loop(
    ledgers: list[dict[str, Any]],
    *,
    state: LoopState,
    run_id: str,
    anchor_ticket: str,
    created_at: str,
    first_wave: int = 1,
    runs_dir: Path | None = None,
    store_path: Path | None = None,
    interrupts_dir: Path | None = None,
    emit_event: bool = True,
    created_by: str = "cto",
) -> list[LoopDecision]:
    decisions: list[LoopDecision] = []
    for i, ledger in enumerate(ledgers):
        decision = step_inner_loop(
            ledger=ledger,
            state=state,
            run_id=run_id,
            anchor_ticket=anchor_ticket,
            wave=first_wave + i,
            created_at=created_at,
            runs_dir=runs_dir,
            store_path=store_path,
            interrupts_dir=interrupts_dir,
            emit_event=emit_event,
            created_by=created_by,
        )
        decisions.append(decision)
        if decision.action in ("satisfied", "paused"):
            break
    return decisions


def _verify_wave_ledger_cli(args: argparse.Namespace) -> int:
    path = Path(args.wave_ledger)
    if not path.is_file():
        sys.stderr.write(f"ERROR: wave-ledger not found: {path}\n")
        return 2

    attest_dir = args.attest_dir if args.attest_dir is not None else path.parent.parent / "metrics" / "attestations"
    tickets_dir = args.tickets_dir if args.tickets_dir is not None else DEFAULT_TICKETS_DIR

    problems = verify_wave_ledger_evidence(
        path, attest_dir=attest_dir, tickets_dir=tickets_dir
    )
    entries, _ = read_wave_ledger(path)
    if problems:
        sys.stderr.write(f"FAIL: wave-ledger is not verifiable evidence ({path}):\n")
        for problem in problems:
            sys.stderr.write(f"  - {problem}\n")
        return 1

    if not entries:
        print(
            f"OK (EMPTY): {path} holds ZERO attested waves. This repository contains NO "
            "wave evidence — nothing has been attested, so nothing is proven."
        )
        return 0

    print(
        f"OK: {len(entries)} wave-ledger entr(ies) verified link by link "
        f"({path}) — hash chain intact, attestations match, every referenced ticket "
        f"exists under {tickets_dir}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_ledger.py — progress-ledger validator + inner-loop stall rule + wave-ledger evidence verifier.')
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--path", type=Path, help="path to a progress-ledger.json file")
    src.add_argument("--run-id", type=str, help="run id (resolves to board/runs/<run_id>/)")
    src.add_argument(
        "--wave-ledger",
        type=Path,
        nargs="?",
        const=DEFAULT_WAVE_LEDGER_PATH,
        help="verify the wave-ledger hash chain, its attestations and its ticket "
        "references (default path: board/wave-ledger.jsonl)",
    )
    ap.add_argument("--runs-dir", type=Path, default=None, help="override board/runs/ location")
    ap.add_argument("--attest-dir", type=Path, default=None, help="metrics/attestations/ override")
    ap.add_argument("--tickets-dir", type=Path, default=None, help="board/tickets/ override")
    args = ap.parse_args(argv)

    if args.wave_ledger is not None:
        return _verify_wave_ledger_cli(args)

    path = args.path if args.path is not None else progress_ledger_path(args.run_id, args.runs_dir)

    if not path.is_file():
        sys.stderr.write(f"ERROR: progress-ledger not found: {path}\n")
        return 2
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ERROR: cannot read/parse {path}: {exc}\n")
        return 2

    problems = validate_ledger(ledger)
    if problems:
        sys.stderr.write(f"FAIL: invalid progress-ledger ({path}):\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: progress-ledger valid ({path}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
