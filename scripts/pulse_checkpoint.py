
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


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

DEFAULT_STORE_PATH: Path = _ROOT / "board" / ".events.jsonl"
DEFAULT_TICKETS_DIR: Path = _ROOT / "board" / "tickets"
DEFAULT_RUNS_DIR: Path = _ROOT / "board" / "runs"


_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms << 80) | rand
    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def compute_board_hash(tickets_dir: Path | None = None) -> str:
    tdir = tickets_dir if tickets_dir is not None else DEFAULT_TICKETS_DIR
    h = hashlib.sha256()
    if tdir.exists():
        for p in sorted(tdir.glob("*.md")):
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return f"sha256:{h.hexdigest()}"


def get_event_offset(store_path: Path | None = None) -> int:
    p = store_path if store_path is not None else DEFAULT_STORE_PATH
    if not p.exists():
        return 0
    return p.stat().st_size


def compute_delta(
    prev_states: dict[str, str],
    curr_states: dict[str, str],
) -> dict[str, str]:
    return {
        tid: status
        for tid, status in curr_states.items()
        if prev_states.get(tid) != status
    }


def _canonical_bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def compute_ledger_hash(checkpoint: dict[str, Any]) -> str:
    preimage = dict(checkpoint)
    lh = dict(preimage.get("ledger_hashes", {}))
    lh.pop("self", None)
    preimage["ledger_hashes"] = lh
    return f"sha256:{hashlib.sha256(_canonical_bytes(preimage)).hexdigest()}"


def _reconstruct_from_chain(
    runs_dir: Path,
    run_id: str,
    up_to_wave: int,
) -> dict[str, str]:
    states: dict[str, str] = {}
    for w in range(1, up_to_wave + 1):
        cp_path = runs_dir / run_id / f"wave-{w:03d}.checkpoint.json"
        if cp_path.exists():
            cp = json.loads(cp_path.read_text(encoding="utf-8"))
            states.update(cp.get("ticket_states", {}))
    return states


def reconstruct_ticket_states(
    run_id: str,
    up_to_wave: int,
    runs_dir: Path | None = None,
) -> dict[str, str]:
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    return _reconstruct_from_chain(rd, run_id, up_to_wave)


def write_wave_checkpoint(
    *,
    run_id: str,
    wave: int,
    ticket_id: str,
    curr_ticket_states: dict[str, str],
    pending_interrupts: list[str] | None = None,
    created_at: str,
    store_path: Path | None = None,
    tickets_dir: Path | None = None,
    runs_dir: Path | None = None,
    emit_event: bool = True,
) -> dict[str, Any]:
    from dgox.events import EventStore, build_checkpoint

    sp = store_path if store_path is not None else DEFAULT_STORE_PATH
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR


    prev_cp_path = rd / run_id / f"wave-{wave - 1:03d}.checkpoint.json"
    prev_cp: dict[str, Any] | None = None
    if wave > 1 and prev_cp_path.exists():
        prev_cp = json.loads(prev_cp_path.read_text(encoding="utf-8"))


    prev_states = _reconstruct_from_chain(rd, run_id, wave - 1) if wave > 1 else {}


    delta = compute_delta(prev_states, curr_ticket_states)


    board_hash = compute_board_hash(tickets_dir)
    event_offset = get_event_offset(sp)


    prev_hash: str = (
        compute_ledger_hash(prev_cp) if prev_cp is not None else _GENESIS_PREV_HASH
    )


    pi = list(pending_interrupts) if pending_interrupts is not None else []
    cp: dict[str, Any] = {
        "run_id": run_id,
        "wave": wave,
        "created_at": created_at,
        "board_hash": board_hash,
        "event_offset": event_offset,
        "ticket_states": delta,
        "pending_interrupts": pi,
        "ledger_hashes": {"prev": prev_hash, "self": ""},
    }
    self_hash = compute_ledger_hash(cp)
    cp["ledger_hashes"]["self"] = self_hash


    run_dir = rd / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cp_path = run_dir / f"wave-{wave:03d}.checkpoint.json"
    cp_path.write_text(
        json.dumps(cp, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


    if emit_event:
        ev = build_checkpoint(
            ticket_id=ticket_id,
            run_id=run_id,
            wave=wave,
            board_hash=board_hash,
            event_offset=event_offset,
            ticket_states=delta,
            ledger_hashes={"prev": prev_hash, "self": self_hash},
            created_at=created_at,
            pending_interrupts=pi,
        )
        EventStore(sp).append(ev)

    return cp


def _durable_append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError):
                fcntl.flock(fh, fcntl.LOCK_UN)


def append_ticket_completion(
    *,
    run_id: str,
    ticket_id: str,
    status: str,
    wave: int,
    created_at: str,
    runs_dir: Path | None = None,
) -> None:
    from dgox.events import build_ticket_completion

    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    completions_path = rd / run_id / "completions.jsonl"

    record = build_ticket_completion(
        ticket_id=ticket_id,
        run_id=run_id,
        status=status,
        wave=wave,
        created_at=created_at,
    )
    _durable_append_jsonl(completions_path, record)


def get_completed_tickets(
    run_id: str,
    runs_dir: Path | None = None,
) -> set[str]:
    rd = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    completions_path = rd / run_id / "completions.jsonl"
    if not completions_path.exists():
        return set()

    completed: set[str] = set()
    try:
        with open(completions_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if (
                    ev.get("event_type") == "ticket_completion"
                    and ev.get("run_id") == run_id
                ):
                    tid = ev.get("ticket_id")
                    if tid:
                        completed.add(str(tid))
    except FileNotFoundError:
        pass
    return completed
