
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import check_ledger as _cl
import dispatch_emitter as _de
import filelock as _fl
import guardrail_dispatch as _gd
import pulse_checkpoint as _pc
import snapshot_evidence as _se
import task_ledger as _tl
from _paths import ROOT
from guardrails import runner as _gr

__all__ = [
    "ATTESTATION_SCHEMA",
    "ATTEST_DIR",
    "LEDGER_FIELDS",
    "LEDGER_PATH",
    "TicketPlan",
    "TicketResult",
    "WaveAttestation",
    "WavePlan",
    "WaveResults",
    "append_wave_ledger_entry",
    "attestation_path",
    "load_attestation",
    "replay_executor",
    "run_wave",
    "verify_attestation",
    "verify_wave_ledger",
]


ATTESTATION_SCHEMA = "daslab.attestation.v1"


ATTEST_DIR: Path = ROOT / "metrics" / "attestations"


LEDGER_PATH: Path = ROOT / "board" / "wave-ledger.jsonl"


LEDGER_FIELDS: tuple[str, ...] = (
    "run_id",
    "wave",
    "ticket_ids",
    "attestation_path",
    "attestation_hash",
    "prev_hash",
    "self_hash",
    "created_at",
)


_GENESIS_PREV_HASH: str = "sha256:" + "0" * 64


@dataclass(frozen=True)
class TicketPlan:

    ticket_id: str
    role: str
    model: str
    from_status: str = "todo"
    to_status: str = "in_progress"


@dataclass(frozen=True)
class WavePlan:

    run_id: str
    wave: int
    goal: str
    engine_version: str
    tickets: list[TicketPlan]
    anchor_ticket: str | None = None
    pending_interrupts: list[str] = field(default_factory=list)

    def anchor(self) -> str:
        if self.anchor_ticket:
            return self.anchor_ticket
        if not self.tickets:
            raise ValueError("WavePlan has no tickets and no anchor_ticket")
        return self.tickets[0].ticket_id


@dataclass(frozen=True)
class TicketResult:

    ticket_id: str
    outcome: str
    merged_pr: Any
    ci_status: str
    t7_pass: Any
    t7_score: float
    start: str
    end: str
    final_status: str = "done"
    run_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    span_status: str = "ok"
    output: str = ""


SUCCESS_OUTCOMES: frozenset[str] = frozenset({"success", "ok", "passed"})
COMPLETED_STATUSES: frozenset[str] = frozenset({"done", "closed", "merged"})


def is_circuit_breaker_tripped(
    unfinished: Sequence[str],
    prior_next_tickets: Sequence[str],
) -> bool:
    if not unfinished or not prior_next_tickets:
        return False
    return set(unfinished) == set(prior_next_tickets)


@dataclass(frozen=True)
class WaveResults:

    tickets: list[TicketResult]
    request_satisfied: bool = True
    in_loop: bool = False
    progress_being_made: bool = True
    next_tickets: list[str] = field(default_factory=list)
    instruction: str = ""

    def by_id(self) -> dict[str, TicketResult]:
        return {r.ticket_id: r for r in self.tickets}

    @classmethod
    def from_ticket_results(
        cls,
        results: Sequence[TicketResult],
        *,
        prior_next_tickets: Sequence[str] = (),
    ) -> WaveResults:
        results = list(results)
        unfinished = sorted(
            r.ticket_id
            for r in results
            if r.outcome not in SUCCESS_OUTCOMES or r.final_status not in COMPLETED_STATUSES
        )
        completed_count = len(results) - len(unfinished)
        return cls(
            tickets=results,
            request_satisfied=bool(results) and not unfinished,
            in_loop=is_circuit_breaker_tripped(unfinished, prior_next_tickets),
            progress_being_made=completed_count > 0,
            next_tickets=unfinished,
            instruction=(
                ""
                if not unfinished
                else "re-plan: " + ", ".join(sorted(unfinished)) + " did not complete"
            ),
        )


WaveExecutor = Callable[["WavePlan"], Sequence[TicketResult]]


def replay_executor(results: Sequence[TicketResult]) -> WaveExecutor:
    recorded = list(results)

    def _replay(_plan: WavePlan) -> Sequence[TicketResult]:
        return recorded

    return _replay


@dataclass(frozen=True)
class WaveAttestation:

    run_id: str
    wave: int
    payload: dict[str, Any]
    path: Path

    @property
    def self_hash(self) -> str:
        return str(self.payload["attest_chain"]["self"])

    @property
    def prev_hash(self) -> str:
        return str(self.payload["attest_chain"]["prev"])


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _sha256(obj: Any) -> str:
    return _sha256_bytes(_canonical_bytes(obj))


def _attest_self_hash(payload: dict[str, Any]) -> str:
    preimage = dict(payload)
    chain = dict(preimage.get("attest_chain", {}))
    chain.pop("self", None)
    preimage["attest_chain"] = chain
    return _sha256(preimage)


def attestation_path(run_id: str, attest_dir: Path | str | None = None) -> Path:
    return Path(attest_dir if attest_dir is not None else ATTEST_DIR) / f"{run_id}.json"


def load_attestation(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_attestation(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != ATTESTATION_SCHEMA:
        errors.append(f"unexpected schema {payload.get('schema')!r}")
    chain = payload.get("attest_chain")
    if not isinstance(chain, dict) or "prev" not in chain or "self" not in chain:
        errors.append("attest_chain must carry 'prev' and 'self'")
        return errors
    recomputed = _attest_self_hash(payload)
    if recomputed != chain.get("self"):
        errors.append(
            f"attest_chain.self mismatch: stored {chain.get('self')!r} != recomputed {recomputed!r}"
        )
    return errors


def _chain_tip(attest_dir: Path, exclude_run_id: str) -> str:
    if not attest_dir.exists():
        return _GENESIS_PREV_HASH
    best_key: tuple[str, str] | None = None
    best_self: str | None = None
    for p in sorted(attest_dir.glob("*.json")):
        if p.stem == exclude_run_id:
            continue
        try:
            payload = load_attestation(p)
        except (OSError, json.JSONDecodeError):
            continue
        chain = payload.get("attest_chain")
        if not isinstance(chain, dict) or "self" not in chain:
            continue
        key = (str(payload.get("created_at", "")), str(payload.get("run_id", "")))
        if best_key is None or key > best_key:
            best_key, best_self = key, str(chain["self"])
    return best_self if best_self is not None else _GENESIS_PREV_HASH


def _ledger_self_hash(entry: dict[str, Any]) -> str:
    preimage = {k: v for k, v in entry.items() if k != "self_hash"}
    return _sha256(preimage)


def _ledger_chain_tip(ledger_path: Path) -> str:
    if not ledger_path.exists():
        return _GENESIS_PREV_HASH
    tip = _GENESIS_PREV_HASH
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        sh = entry.get("self_hash")
        if isinstance(sh, str) and sh:
            tip = sh
    return tip


def _attestation_repo_path(out_path: Path, ledger_path: Path) -> str:
    for base in (ROOT, ledger_path.resolve().parent.parent):
        try:
            return out_path.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return out_path.resolve().as_posix()


def append_wave_ledger_entry(
    *,
    ledger_path: Path,
    run_id: str,
    wave: int,
    ticket_ids: list[str],
    attestation_out_path: Path,
    attestation_bytes: bytes,
    created_at: str,
) -> dict[str, Any]:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with _fl.exclusive_lock(ledger_path):
        entry: dict[str, Any] = {
            "run_id": run_id,
            "wave": wave,
            "ticket_ids": sorted(ticket_ids),
            "attestation_path": _attestation_repo_path(attestation_out_path, ledger_path),
            "attestation_hash": _sha256_bytes(attestation_bytes),
            "prev_hash": _ledger_chain_tip(ledger_path),
            "self_hash": "",
            "created_at": created_at,
        }
        entry["self_hash"] = _ledger_self_hash(entry)
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        _fl.append_text_durably(ledger_path, line)
    return entry


def verify_wave_ledger(
    ledger_path: Path | str,
    *,
    attest_dir: Path | str | None = None,
    reconcile_attestations: bool = True,
) -> list[str]:
    ledger_path = Path(ledger_path)
    problems: list[str] = []
    if not ledger_path.exists():
        return problems

    entries: list[dict[str, Any]] = []
    for lineno, raw in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {lineno}: malformed JSON ({exc})")
            continue
        if set(entry) != set(LEDGER_FIELDS):
            problems.append(
                f"line {lineno}: fields {sorted(entry)} != required {sorted(LEDGER_FIELDS)}"
            )
            continue
        entries.append(entry)


    seen: set[tuple[str, Any]] = set()
    for entry in entries:
        key = (str(entry.get("run_id")), entry.get("wave"))
        if key in seen:
            problems.append(f"duplicate ledger entry for run_id={key[0]!r} wave={key[1]!r}")
        seen.add(key)


    expected_prev = _GENESIS_PREV_HASH
    for entry in entries:
        run_id = str(entry.get("run_id"))
        wave = entry.get("wave")
        if entry.get("prev_hash") != expected_prev:
            problems.append(
                f"broken chain at run_id={run_id!r} wave={wave!r}: "
                f"prev_hash {entry.get('prev_hash')!r} != expected {expected_prev!r} "
                "(a dropped or reordered wave-ledger line)"
            )
        recomputed = _ledger_self_hash(entry)
        if recomputed != entry.get("self_hash"):
            problems.append(
                f"tampered entry at run_id={run_id!r} wave={wave!r}: "
                f"self_hash {entry.get('self_hash')!r} != recomputed {recomputed!r}"
            )
        expected_prev = str(entry.get("self_hash"))


    if reconcile_attestations and attest_dir is not None:
        attest_dir = Path(attest_dir)
        ledger_run_ids: set[str] = set()
        for entry in entries:
            run_id = str(entry.get("run_id"))
            ledger_run_ids.add(run_id)
            att_path = attestation_path(run_id, attest_dir)
            if not att_path.exists():
                problems.append(f"ledger entry run_id={run_id!r} has no committed attestation")
                continue
            try:
                payload = load_attestation(att_path)
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"attestation for run_id={run_id!r} unreadable ({exc})")
                continue
            att_problems = verify_attestation(payload)
            if att_problems:
                problems.append(f"attestation for run_id={run_id!r} fails verify: {att_problems}")
            got_hash = _sha256_bytes(att_path.read_bytes())
            if got_hash != entry.get("attestation_hash"):
                problems.append(
                    f"attestation_hash mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('attestation_hash')!r} != file {got_hash!r} "
                    "(a swapped or reformatted receipt)"
                )
            if payload.get("tickets") != entry.get("ticket_ids"):
                problems.append(
                    f"ticket set mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('ticket_ids')!r} != attestation {payload.get('tickets')!r}"
                )
            if payload.get("wave") != entry.get("wave"):
                problems.append(
                    f"wave mismatch for run_id={run_id!r}: "
                    f"ledger {entry.get('wave')!r} != attestation {payload.get('wave')!r}"
                )
        if attest_dir.exists():
            for att_file in sorted(attest_dir.glob("*.json")):
                if att_file.stem not in ledger_run_ids:
                    problems.append(
                        f"orphan attestation {att_file.name}: committed receipt with no ledger entry"
                    )

    return problems


def _dispatch_run_id(plan: WavePlan, result: TicketResult) -> str:
    return result.run_id or f"{plan.run_id}-{result.ticket_id}"


def _build_records(plan: WavePlan, results: WaveResults) -> list[_de.DispatchRecord]:
    by_id = results.by_id()
    records: list[_de.DispatchRecord] = []
    for tp in plan.tickets:
        r = by_id.get(tp.ticket_id)
        if r is None:
            raise ValueError(f"no result collected for planned ticket {tp.ticket_id!r}")
        records.append(
            _de.DispatchRecord(
                ticket_id=tp.ticket_id,
                run_id=_dispatch_run_id(plan, r),
                goal=plan.goal,
                engine_version=plan.engine_version,
                model=tp.model,
                role_key=tp.role,
                start=r.start,
                end=r.end,
                outcome=r.outcome,
                merged_pr=r.merged_pr,
                ci_status=r.ci_status,
                t7_pass=r.t7_pass,
                t7_score=r.t7_score,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cached_input_tokens=r.cached_input_tokens,
                span_status=r.span_status,
            )
        )
    return records


def _with_run_id_frontmatter(text: str, run_id: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    header, rest = text[3:end], text[end:]
    out_lines: list[str] = []
    replaced = False
    for line in header.split("\n"):
        key = line.partition(":")[0].strip()
        if key == "run_id":
            out_lines.append(f"run_id: {run_id}")
            replaced = True
        else:
            out_lines.append(line)
    if not replaced:
        out_lines.append(f"run_id: {run_id}")
    return "---" + "\n".join(out_lines) + rest


def _stamp_run_id_frontmatter(ticket_path: Path, run_id: str) -> bool:
    ticket_path = Path(ticket_path)
    changed = False

    def _transform(text: str) -> str:
        nonlocal changed
        new_text = _with_run_id_frontmatter(text, run_id)
        changed = new_text != text
        return new_text

    _fl.locked_update_text(ticket_path, _transform, missing_ok=False)
    return changed


def _stamp_wave_run_ids(plan: WavePlan, board_dir: Path) -> None:
    for tp in plan.tickets:
        try:
            matches = sorted(Path(board_dir).glob(f"{tp.ticket_id}-*.md"))
            if not matches:
                sys.stderr.write(
                    f"wave_runner: no ticket file for {tp.ticket_id} in {board_dir} "
                    "— run_id not stamped (audit-trail gap logged, wave continues)\n"
                )
                continue
            _stamp_run_id_frontmatter(matches[0], plan.run_id)
        except Exception as exc:
            sys.stderr.write(
                f"wave_runner: failed to stamp run_id on {tp.ticket_id}: "
                f"{type(exc).__name__}: {exc}\n"
            )


def _run_guardrails(
    plan: WavePlan,
    results: WaveResults,
    *,
    board_dir: Path,
    routing_path: Path,
    guardrails_dir: Path,
    created_at: str,
) -> dict[str, str]:
    by_id = results.by_id()
    now = (lambda: created_at[:10]) if len(created_at) >= 10 else (lambda: created_at)
    verdicts: dict[str, str] = {}
    for tp in plan.tickets:
        matches = sorted(Path(board_dir).glob(f"{tp.ticket_id}-*.md"))
        if not matches:
            verdicts[tp.ticket_id] = "no_ticket_file"
            continue
        output = by_id[tp.ticket_id].output

        def _replay(_ctx: Any, _attempt: int, _out: str = output) -> str:
            return _out

        try:
            res = _gd.guardrail_dispatch(
                matches[0],
                _replay,
                routing_path=routing_path,
                board_dir=Path(board_dir),
                guardrails_dir=guardrails_dir,
                now=now,
            )
            verdicts[tp.ticket_id] = res.outcome
        except Exception as exc:
            verdicts[tp.ticket_id] = f"error:{type(exc).__name__}"
    return verdicts


def _collect_results(plan: WavePlan, execute_wave: WaveExecutor) -> WaveResults:
    if isinstance(execute_wave, WaveResults):
        raise TypeError(
            "run_wave no longer accepts pre-computed WaveResults: it must run the wave "
            "itself. Pass a WaveExecutor — a callable taking the WavePlan and returning "
            "the TicketResults it produced. A caller that legitimately replays already "
            "recorded results (a drill or a fixture) must say so explicitly with "
            "wave_runner.replay_executor(results)."
        )
    if not callable(execute_wave):
        raise TypeError(
            "run_wave needs a WaveExecutor callable (WavePlan -> Sequence[TicketResult]); "
            f"got {type(execute_wave).__name__}"
        )
    produced = execute_wave(plan)
    if isinstance(produced, WaveResults):
        return produced
    if not isinstance(produced, Sequence):
        raise TypeError(
            "the wave executor must return a sequence of TicketResult; "
            f"got {type(produced).__name__}"
        )
    return WaveResults.from_ticket_results(list(produced))


def run_wave(
    plan: WavePlan,
    execute_wave: WaveExecutor,
    *,
    created_at: str,
    store_path: Path | str | None = None,
    runs_dir: Path | None = None,
    attest_dir: Path | str | None = None,
    ledger_path: Path | str | None = None,
    evidence_dir: Path | str | None = None,
    tickets_dir: Path | None = None,
    board_dir: Path | None = None,
    routing_path: Path | None = None,
    guardrails_dir: Path | None = None,
    organism_emit: bool = True,
    run_guardrails: bool = True,
) -> WaveAttestation | None:
    if not organism_emit:
        return None

    attest_dir = Path(attest_dir) if attest_dir is not None else ATTEST_DIR
    evidence_dir = Path(evidence_dir) if evidence_dir is not None else _se.EVIDENCE_DIR
    board_dir = board_dir if board_dir is not None else (tickets_dir or _pc.DEFAULT_TICKETS_DIR)
    routing_path = routing_path if routing_path is not None else _gd.DEFAULT_ROUTING
    guardrails_dir = guardrails_dir if guardrails_dir is not None else _gr.DEFAULT_GUARDRAILS_DIR

    anchor = plan.anchor()
    open_states = {tp.ticket_id: tp.from_status for tp in plan.tickets}

    _pc.write_wave_checkpoint(
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_id=anchor,
        curr_ticket_states=open_states,
        pending_interrupts=plan.pending_interrupts,
        created_at=created_at,
        store_path=store_path,
        tickets_dir=tickets_dir,
        runs_dir=runs_dir,
        emit_event=False,
    )


    _stamp_wave_run_ids(plan, board_dir)


    results = _collect_results(plan, execute_wave)
    records = _build_records(plan, results)
    by_id = results.by_id()
    close_states = {tp.ticket_id: by_id[tp.ticket_id].final_status for tp in plan.tickets}


    events = _de.emit_wave(records, store_path=store_path)
    emitted_counts = {
        "run_start": sum(1 for e in events if e.get("event_type") == "run_start"),
        "run_end": sum(1 for e in events if e.get("event_type") == "run_end"),
        "span": sum(1 for e in events if e.get("event_type") == "span"),
    }


    guardrail_verdicts: dict[str, str] = {}
    if run_guardrails:
        guardrail_verdicts = _run_guardrails(
            plan,
            results,
            board_dir=board_dir,
            routing_path=routing_path,
            guardrails_dir=guardrails_dir,
            created_at=created_at,
        )


    for tp in plan.tickets:
        _pc.append_ticket_completion(
            run_id=plan.run_id,
            ticket_id=tp.ticket_id,
            status=by_id[tp.ticket_id].final_status,
            wave=plan.wave,
            created_at=created_at,
            runs_dir=runs_dir,
        )
    _tl.build_task_ledger(
        run_id=plan.run_id,
        facts={"given": [f"wave {plan.wave} of goal {plan.goal}"],
               "known": sorted(close_states)},
        plan=[f"{tp.ticket_id} -> {tp.role} ({tp.model})" for tp in plan.tickets],
        created_at=created_at,
        goal=plan.goal,
        wave=plan.wave,
        runs_dir=runs_dir,
    )
    progress_ledger_path = _cl.write_progress_ledger(
        run_id=plan.run_id,
        request_satisfied=results.request_satisfied,
        in_loop=results.in_loop,
        progress_being_made=results.progress_being_made,
        next_tickets=results.next_tickets,
        instruction=results.instruction,
        runs_dir=runs_dir,
    )
    close_cp = _pc.write_wave_checkpoint(
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_id=anchor,
        curr_ticket_states=close_states,
        pending_interrupts=plan.pending_interrupts,
        created_at=created_at,
        store_path=store_path,
        tickets_dir=tickets_dir,
        runs_dir=runs_dir,
        emit_event=False,
    )


    evidence_run_ids = sorted({_dispatch_run_id(plan, by_id[tp.ticket_id]) for tp in plan.tickets})
    for rid in evidence_run_ids:
        _se.write_run_evidence(events, rid, evidence_dir)


    counted = sum(1 for e in events if _se._is_counted_completion(e))
    ledger_digest = _sha256(json.loads(progress_ledger_path.read_text(encoding="utf-8")))
    evidence_digest = _sha256(
        {rid: json.loads(_se.evidence_path(evidence_dir, rid).read_text(encoding="utf-8"))
         for rid in evidence_run_ids}
    )
    payload: dict[str, Any] = {
        "schema": ATTESTATION_SCHEMA,
        "run_id": plan.run_id,
        "wave": plan.wave,
        "engine_version": plan.engine_version,
        "created_at": created_at,
        "tickets": sorted(tp.ticket_id for tp in plan.tickets),
        "mechanics": {
            "checkpoint_open": True,
            "guardrails_run": bool(run_guardrails),
            "events_emitted": emitted_counts,
            "ledger_written": True,
            "evidence_written": True,
            "checkpoint_close": True,
        },
        "guardrail_verdicts": guardrail_verdicts,
        "counts": {"dispatched": len(plan.tickets), "counted_completions": counted},
        "event_digest": _sha256(events),
        "evidence": {
            "dir": "metrics/evidence",
            "run_ids": evidence_run_ids,
            "digest": evidence_digest,
        },
        "ledger_digest": ledger_digest,
        "ledger_hashes": dict(close_cp["ledger_hashes"]),
        "attest_chain": {
            "prev": _chain_tip(attest_dir, exclude_run_id=plan.run_id),
            "self": "",
        },
    }
    payload["attest_chain"]["self"] = _attest_self_hash(payload)

    out_path = attestation_path(plan.run_id, attest_dir)
    _fl.atomic_write_text(out_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


    wave_ledger_path = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    append_wave_ledger_entry(
        ledger_path=wave_ledger_path,
        run_id=plan.run_id,
        wave=plan.wave,
        ticket_ids=[tp.ticket_id for tp in plan.tickets],
        attestation_out_path=out_path,
        attestation_bytes=out_path.read_bytes(),
        created_at=created_at,
    )

    return WaveAttestation(run_id=plan.run_id, wave=plan.wave, payload=payload, path=out_path)
