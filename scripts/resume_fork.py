#!/usr/bin/env python3


from __future__ import annotations

import os
from pathlib import Path


def _resolve_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess

        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass

    return Path(__file__).resolve().parent.parent


_ROOT = _resolve_root()


TERMINAL_STATUSES: frozenset[str] = frozenset({"done", "blocked"})


def _run_events(run_id: str, events_path: Path) -> list[dict]:
    import replay_qa
    import wave_kpi

    all_events = wave_kpi.read_events(str(events_path))
    runs = replay_qa.group_runs(all_events)
    return runs.get(run_id, [])


def _per_ticket_events(run_events: list[dict]) -> dict[str, list[dict]]:
    per_ticket: dict[str, list[dict]] = {}
    for ev in run_events:
        tid = str(ev.get("ticket_id") or "")
        if tid:
            per_ticket.setdefault(tid, []).append(ev)
    return per_ticket


def get_unfinished_tickets(
    run_id: str,
    events_path: Path | None = None,
) -> dict[str, str]:
    import replay_qa

    ep = events_path if events_path is not None else (_ROOT / "board" / ".events.jsonl")
    run_evs = _run_events(run_id, ep)


    unfinished: dict[str, str] = {}
    for ticket_id, ticket_events in _per_ticket_events(run_evs).items():
        result = replay_qa.replay_run(ticket_events)
        if result["corrupted"]:
            raise ValueError(
                f"Corrupted transition chain for ticket {ticket_id!r} in run "
                f"{run_id!r}: {result['reason']} (T5 zero-corrupted guardrail — "
                f"resume refuses to re-dispatch off a corrupted replay)"
            )
        final = result.get("final_status")
        if final and final not in TERMINAL_STATUSES:
            unfinished[ticket_id] = final

    return unfinished


def resume_run(
    run_id: str,
    events_path: Path | None = None,
    runs_dir: Path | None = None,
) -> dict[str, str]:
    import pulse_checkpoint as pc

    ep = events_path if events_path is not None else (_ROOT / "board" / ".events.jsonl")
    rd = runs_dir if runs_dir is not None else (_ROOT / "board" / "runs")


    unfinished = get_unfinished_tickets(run_id, ep)


    completed = pc.get_completed_tickets(run_id, rd)
    return {tid: status for tid, status in unfinished.items() if tid not in completed}


def fork_run(
    source_run_id: str,
    wave_num: int,
    events_path: Path | None = None,
    runs_dir: Path | None = None,
) -> tuple[str, dict[str, str]]:
    import pulse_checkpoint as pc

    if wave_num < 1:
        raise ValueError(f"wave_num must be a positive (1-based) integer; got {wave_num!r}")

    rd = runs_dir if runs_dir is not None else (_ROOT / "board" / "runs")


    ticket_states = pc.reconstruct_ticket_states(source_run_id, wave_num, rd)


    new_run_id = pc.generate_ulid()


    return new_run_id, ticket_states


def parse_fork_arg(arg: str) -> tuple[str, int]:
    separator = "@wave-"
    if separator not in arg:
        raise ValueError(
            f"--fork argument must be '<run_id>@wave-NNN'; got {arg!r}. "
            f"Example: --fork 01J9Z8QK3M7Q0W9E4R5T6Y7U8I@wave-003"
        )
    run_id_part, wave_part = arg.rsplit(separator, 1)
    if not run_id_part:
        raise ValueError(f"run_id part is empty in --fork argument {arg!r}")
    try:
        wave_num = int(wave_part)
    except ValueError:
        raise ValueError(
            f"Wave number in --fork argument must be digits; got {wave_part!r} "
            f"(full arg: {arg!r})"
        ) from None
    if wave_num < 1:
        raise ValueError(
            f"Wave number must be >= 1 (1-based); got {wave_num!r} (full arg: {arg!r})"
        )
    return run_id_part, wave_num
