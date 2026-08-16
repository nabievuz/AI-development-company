#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import filelock as _fl
import wave_planner as _wp
from _paths import ROOT
from dgox.created_at import CREATED_AT_FORMAT

DEFAULT_JOURNAL_PATH: Path = ROOT / "board" / ".dispatch-journal.jsonl"
DEFAULT_ORG_PATH: Path = ROOT / "config" / "org.yaml"
DEFAULT_BOARD_DIR: Path = ROOT / "board" / "tickets"

JOURNAL_SCHEMA = "daslab.dispatch.v1"


class DispatchStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentInvokerUnavailable(RuntimeError):
    pass


class DispatchTimeout(TimeoutError):
    pass


def utc_now() -> str:
    return datetime.now(tz=UTC).strftime(CREATED_AT_FORMAT)


@dataclass(frozen=True)
class DispatchRequest:
    ticket_id: str
    role: str
    model: str
    zone: str
    run_id: str
    attempt: int
    goal: str = ""
    board_dir: str = ""


@dataclass(frozen=True)
class AgentOutput:
    output: str
    merged_pr: bool = False
    ci_status: str = "unverified"
    t7_pass: bool = False
    t7_score: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


AgentInvoker = Callable[[DispatchRequest], "AgentOutput | str"]


def coerce_agent_output(value: AgentOutput | str) -> AgentOutput:
    if isinstance(value, AgentOutput):
        return value
    if isinstance(value, str):
        return AgentOutput(output=value)
    raise TypeError(
        f"agent invoker must return AgentOutput or str; got {type(value).__name__}"
    )


@dataclass(frozen=True)
class DispatchOutcome:
    ticket_id: str
    run_id: str
    role: str
    model: str
    status: DispatchStatus
    attempts: int
    started_at: str
    ended_at: str
    result: AgentOutput = field(default_factory=lambda: AgentOutput(output=""))
    error: str = ""
    resumed: bool = False

    @property
    def succeeded(self) -> bool:
        return self.status is DispatchStatus.OK

    def as_journal_entry(self) -> dict[str, object]:
        return {
            "schema": JOURNAL_SCHEMA,
            "ticket_id": self.ticket_id,
            "run_id": self.run_id,
            "role": self.role,
            "model": self.model,
            "status": self.status.value,
            "attempts": self.attempts,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "result": {
                "output": self.result.output,
                "merged_pr": self.result.merged_pr,
                "ci_status": self.result.ci_status,
                "t7_pass": self.result.t7_pass,
                "t7_score": self.result.t7_score,
                "input_tokens": self.result.input_tokens,
                "output_tokens": self.result.output_tokens,
                "cached_input_tokens": self.result.cached_input_tokens,
            },
        }

    @classmethod
    def from_journal_entry(cls, entry: dict[str, object]) -> DispatchOutcome:
        raw_result = entry.get("result")
        result_fields = raw_result if isinstance(raw_result, dict) else {}
        return cls(
            ticket_id=str(entry["ticket_id"]),
            run_id=str(entry["run_id"]),
            role=str(entry.get("role", "")),
            model=str(entry.get("model", "")),
            status=DispatchStatus(str(entry["status"])),
            attempts=int(entry.get("attempts", 0)),
            started_at=str(entry.get("started_at", "")),
            ended_at=str(entry.get("ended_at", "")),
            result=AgentOutput(
                output=str(result_fields.get("output", "")),
                merged_pr=bool(result_fields.get("merged_pr", False)),
                ci_status=str(result_fields.get("ci_status", "unverified")),
                t7_pass=bool(result_fields.get("t7_pass", False)),
                t7_score=float(result_fields.get("t7_score", 0.0)),
                input_tokens=int(result_fields.get("input_tokens", 0)),
                output_tokens=int(result_fields.get("output_tokens", 0)),
                cached_input_tokens=int(result_fields.get("cached_input_tokens", 0)),
            ),
            error=str(entry.get("error", "")),
        )


@dataclass(frozen=True)
class WaveRun:
    run_id: str
    outcomes: tuple[DispatchOutcome, ...] = ()

    def by_ticket(self) -> dict[str, DispatchOutcome]:
        return {o.ticket_id: o for o in self.outcomes}

    @property
    def failures(self) -> tuple[DispatchOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.succeeded)

    @property
    def all_succeeded(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class OrchestratorConfig:
    max_parallel: int = 4
    task_timeout_seconds: float = 900.0
    max_attempts: int = 2
    retry_backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_parallel < 1:
            raise ValueError(f"max_parallel must be >= 1; got {self.max_parallel}")
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1; got {self.max_attempts}")
        if self.task_timeout_seconds <= 0:
            raise ValueError(
                f"task_timeout_seconds must be > 0; got {self.task_timeout_seconds}"
            )
        if self.retry_backoff_seconds < 0:
            raise ValueError(
                f"retry_backoff_seconds must be >= 0; got {self.retry_backoff_seconds}"
            )


@dataclass(frozen=True)
class DispatchUnit:
    ticket_id: str
    role: str
    model: str
    zone: str = ""


class DispatchJournal:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def entries(self) -> list[DispatchOutcome]:
        if not self.path.exists():
            return []
        outcomes: list[DispatchOutcome] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"corrupt dispatch journal line in {self.path}: {exc}") from exc
            outcomes.append(DispatchOutcome.from_journal_entry(entry))
        return outcomes

    def succeeded(self) -> dict[tuple[str, str], DispatchOutcome]:
        done: dict[tuple[str, str], DispatchOutcome] = {}
        for outcome in self.entries():
            key = (outcome.ticket_id, outcome.run_id)
            if outcome.succeeded:
                done[key] = outcome
            else:
                done.pop(key, None)
        return done

    def record(self, outcome: DispatchOutcome) -> None:
        line = json.dumps(
            outcome.as_journal_entry(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        _fl.locked_append_text(self.path, line + "\n")


class Orchestrator:
    def __init__(
        self,
        invoke: AgentInvoker,
        *,
        config: OrchestratorConfig | None = None,
        journal_path: Path | str | None = None,
        clock: Callable[[], str] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not callable(invoke):
            raise TypeError(
                "Orchestrator needs a callable agent invoker "
                f"(DispatchRequest -> AgentOutput|str); got {type(invoke).__name__}"
            )
        self._invoke = invoke
        self.config = config or OrchestratorConfig()
        self.journal = DispatchJournal(
            journal_path if journal_path is not None else DEFAULT_JOURNAL_PATH
        )
        self._clock = clock
        self._sleep = sleep

    def run_id_for(self, wave_run_id: str, ticket_id: str) -> str:
        return f"{wave_run_id}-{ticket_id}"

    def dispatch(self, plan: _wp.WavePlan, *, run_id: str, board_dir: str = "") -> WaveRun:
        units = [
            DispatchUnit(pt.ticket_id, pt.role, pt.model, pt.zone) for pt in plan.dispatch
        ]
        return self.dispatch_units(units, run_id=run_id, goal=plan.goal, board_dir=board_dir)

    def dispatch_units(
        self, units: Sequence[DispatchUnit], *, run_id: str, goal: str = "", board_dir: str = ""
    ) -> WaveRun:
        if not run_id:
            raise ValueError("dispatch needs a non-empty wave run_id")
        already_done = self.journal.succeeded()
        outcomes: dict[str, DispatchOutcome] = {}
        pending: list[DispatchUnit] = []

        for unit in units:
            key = (unit.ticket_id, self.run_id_for(run_id, unit.ticket_id))
            prior = already_done.get(key)
            if prior is not None:
                outcomes[unit.ticket_id] = replace(prior, resumed=True)
            else:
                pending.append(unit)

        if pending:
            workers = min(self.config.max_parallel, len(pending))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wave") as pool:
                futures = [
                    pool.submit(self._run_unit, unit, run_id, goal, board_dir) for unit in pending
                ]
                for future in futures:
                    outcome = future.result()
                    outcomes[outcome.ticket_id] = outcome

        ordered = tuple(outcomes[unit.ticket_id] for unit in units if unit.ticket_id in outcomes)
        return WaveRun(run_id=run_id, outcomes=ordered)

    def _run_unit(
        self, unit: DispatchUnit, wave_run_id: str, goal: str, board_dir: str = ""
    ) -> DispatchOutcome:
        ticket_run_id = self.run_id_for(wave_run_id, unit.ticket_id)
        started_at = self._clock()
        status = DispatchStatus.FAILED
        last_error = ""
        attempts = 0

        for attempt in range(1, self.config.max_attempts + 1):
            attempts = attempt
            request = DispatchRequest(
                ticket_id=unit.ticket_id,
                role=unit.role,
                model=unit.model,
                zone=unit.zone,
                run_id=ticket_run_id,
                attempt=attempt,
                goal=goal,
                board_dir=board_dir,
            )
            try:
                result = coerce_agent_output(self._invoke_with_timeout(request))
            except DispatchTimeout as exc:
                status, last_error = DispatchStatus.TIMEOUT, str(exc)
            except Exception as exc:
                status, last_error = DispatchStatus.FAILED, f"{type(exc).__name__}: {exc}"
            else:
                outcome = DispatchOutcome(
                    ticket_id=unit.ticket_id,
                    run_id=ticket_run_id,
                    role=unit.role,
                    model=unit.model,
                    status=DispatchStatus.OK,
                    attempts=attempt,
                    started_at=started_at,
                    ended_at=self._clock(),
                    result=result,
                )
                self.journal.record(outcome)
                return outcome
            if attempt < self.config.max_attempts and self.config.retry_backoff_seconds:
                self._sleep(self.config.retry_backoff_seconds)

        outcome = DispatchOutcome(
            ticket_id=unit.ticket_id,
            run_id=ticket_run_id,
            role=unit.role,
            model=unit.model,
            status=status,
            attempts=attempts,
            started_at=started_at,
            ended_at=self._clock(),
            error=last_error,
        )
        self.journal.record(outcome)
        return outcome

    def _invoke_with_timeout(self, request: DispatchRequest) -> AgentOutput | str:
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"t-{request.ticket_id}")
        future = pool.submit(self._invoke, request)
        try:
            return future.result(timeout=self.config.task_timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise DispatchTimeout(
                f"ticket {request.ticket_id} attempt {request.attempt} exceeded "
                f"{self.config.task_timeout_seconds}s"
            ) from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)


def to_runner_plan(
    plan: _wp.WavePlan,
    *,
    run_id: str,
    wave: int,
    goal: str,
    engine_version: str,
):
    import wave_runner as _wr

    return _wr.WavePlan(
        run_id=run_id,
        wave=wave,
        goal=goal or plan.goal,
        engine_version=engine_version,
        tickets=[
            _wr.TicketPlan(ticket_id=pt.ticket_id, role=pt.role, model=pt.model)
            for pt in plan.dispatch
        ],
    )


def ticket_results_from_run(run: WaveRun) -> list[object]:
    import wave_runner as _wr

    results = []
    for outcome in run.outcomes:
        results.append(
            _wr.TicketResult(
                ticket_id=outcome.ticket_id,
                outcome="success" if outcome.succeeded else outcome.status.value,
                merged_pr=outcome.result.merged_pr,
                ci_status=outcome.result.ci_status,
                t7_pass=outcome.result.t7_pass,
                t7_score=outcome.result.t7_score,
                start=outcome.started_at,
                end=outcome.ended_at,
                final_status="done" if outcome.succeeded else "blocked",
                run_id=outcome.run_id,
                input_tokens=outcome.result.input_tokens,
                output_tokens=outcome.result.output_tokens,
                cached_input_tokens=outcome.result.cached_input_tokens,
                span_status="ok" if outcome.succeeded else "error",
                output=outcome.result.output,
            )
        )
    return results


def wave_executor(
    orchestrator: Orchestrator,
    *,
    goal: str = "",
    board_dir: str = "",
    zones: dict[str, str] | None = None,
    sink: list[WaveRun] | None = None,
) -> Callable[[object], list[object]]:
    zone_of = zones or {}

    def _execute(runner_plan) -> list[object]:
        units = [
            DispatchUnit(tp.ticket_id, tp.role, tp.model, zone_of.get(tp.ticket_id, ""))
            for tp in runner_plan.tickets
        ]
        run = orchestrator.dispatch_units(
            units,
            run_id=runner_plan.run_id,
            goal=goal or runner_plan.goal,
            board_dir=board_dir,
        )
        if sink is not None:
            sink.append(run)
        return ticket_results_from_run(run)

    return _execute


def recorded_waves(ledger_path: Path) -> list[int]:
    if not ledger_path.is_file():
        return []
    waves: list[int] = []
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrupt wave ledger line in {ledger_path}: {exc}") from exc
        wave = entry.get("wave")
        if isinstance(wave, int):
            waves.append(wave)
    return waves


def next_wave_number(ledger_path: Path) -> int:
    waves = recorded_waves(ledger_path)
    return max(waves) + 1 if waves else 1


def default_ledger_path() -> Path:
    import wave_runner as _wr

    return _wr.LEDGER_PATH


def engine_version(root: Path | None = None) -> str:
    version_file = (root or ROOT) / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def dispatch_with_evidence(
    plan: _wp.WavePlan,
    orchestrator: Orchestrator,
    *,
    run_id: str,
    wave: int,
    goal: str,
    board_dir: Path,
    created_at: str = "",
    evidence_paths: dict[str, Path] | None = None,
) -> tuple[WaveRun, object]:
    import wave_runner as _wr

    runs: list[WaveRun] = []
    execute_wave = wave_executor(
        orchestrator,
        goal=goal or plan.goal,
        board_dir=str(board_dir),
        zones={pt.ticket_id: pt.zone for pt in plan.dispatch},
        sink=runs,
    )
    attestation = _wr.run_wave(
        to_runner_plan(
            plan,
            run_id=run_id,
            wave=wave,
            goal=goal or plan.goal,
            engine_version=engine_version(),
        ),
        execute_wave,
        created_at=created_at or utc_now(),
        board_dir=board_dir,
        tickets_dir=board_dir,
        **(evidence_paths or {}),
    )
    run = runs[-1] if runs else WaveRun(run_id=run_id, outcomes=())
    return run, attestation


def resolve_invoker(spec: str) -> AgentInvoker:
    if ":" not in spec:
        raise AgentInvokerUnavailable(
            f"invoker spec must look like 'module:callable'; got {spec!r}"
        )
    module_name, _, attr = spec.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AgentInvokerUnavailable(
            f"cannot import invoker module {module_name!r}: {exc}"
        ) from exc
    invoker = getattr(module, attr, None)
    if invoker is None:
        raise AgentInvokerUnavailable(
            f"module {module_name!r} has no attribute {attr!r}"
        )
    if not callable(invoker):
        raise AgentInvokerUnavailable(f"{spec!r} is not callable")
    return invoker


def render_plan(plan: _wp.WavePlan) -> str:
    lines: list[str] = []
    lines.append(f"goal: {plan.goal or '(unset)'}")
    lines.append(f"occupied zones: {', '.join(sorted(plan.occupied_zones)) or '(none)'}")
    lines.append(f"dispatch: {len(plan.dispatch)} ticket(s)")
    for pt in plan.dispatch:
        lines.append(f"  DISPATCH {pt.ticket_id} role={pt.role} model={pt.model} zone={pt.zone}")
    lines.append(f"refused: {len(plan.refused)} ticket(s)")
    for refusal in plan.refused:
        lines.append(f"  REFUSE   {refusal.ticket_id} {refusal.reason.value}: {refusal.detail}")
    return "\n".join(lines)


def render_run(run: WaveRun) -> str:
    lines = [f"run_id: {run.run_id}"]
    for outcome in run.outcomes:
        marker = "RESUMED " if outcome.resumed else ""
        lines.append(
            f"  {marker}{outcome.status.value.upper()} {outcome.ticket_id} "
            f"attempts={outcome.attempts} {outcome.error}".rstrip()
        )
    lines.append(
        f"summary: {len(run.outcomes) - len(run.failures)} succeeded, "
        f"{len(run.failures)} failed"
    )
    return "\n".join(lines)


def build_plan_from_board(
    *,
    board_dir: Path,
    org_path: Path,
    goal: str,
    occupied_zones: Iterable[str],
    closed_gates: Iterable[str],
    max_wave_size: int | None,
) -> _wp.WavePlan:
    tickets = _wp.load_board_tickets(board_dir)
    org = _wp.load_org_model(org_path)
    return _wp.plan_wave(
        tickets,
        org,
        occupied_zones,
        goal=goal,
        closed_gates=closed_gates,
        max_wave_size=max_wave_size,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator.py",
        description=(
            "Plan a wave from the board and dispatch it. --dry-run prints the plan and "
            "writes nothing; --dispatch runs it through an injected agent invoker."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print the plan and touch nothing")
    mode.add_argument("--dispatch", action="store_true", help="execute the planned wave")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD_DIR)
    parser.add_argument("--org", type=Path, default=DEFAULT_ORG_PATH)
    parser.add_argument("--goal", default="")
    parser.add_argument("--run-id", default="", help="wave run id (required with --dispatch)")
    parser.add_argument(
        "--invoker",
        default="",
        help="'module:callable' seam that runs one ticket (required with --dispatch)",
    )
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument(
        "--wave",
        type=int,
        default=None,
        help="wave number recorded in the ledger (default: derived from the ledger, gap-free)",
    )
    parser.add_argument(
        "--no-evidence",
        action="store_true",
        help="dispatch without writing a wave ledger entry or attestation",
    )
    parser.add_argument("--occupied-zone", action="append", default=[])
    parser.add_argument("--closed-gate", action="append", default=[])
    parser.add_argument("--max-wave-size", type=int, default=None)
    parser.add_argument("--max-parallel", type=int, default=OrchestratorConfig.max_parallel)
    parser.add_argument(
        "--task-timeout", type=float, default=OrchestratorConfig.task_timeout_seconds
    )
    parser.add_argument("--max-attempts", type=int, default=OrchestratorConfig.max_attempts)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def _plan_as_dict(plan: _wp.WavePlan) -> dict[str, object]:
    return {
        "goal": plan.goal,
        "occupied_zones": sorted(plan.occupied_zones),
        "dispatch": [
            {"ticket_id": pt.ticket_id, "role": pt.role, "model": pt.model, "zone": pt.zone}
            for pt in plan.dispatch
        ],
        "refused": [
            {"ticket_id": r.ticket_id, "reason": r.reason.value, "detail": r.detail}
            for r in plan.refused
        ],
    }


def _run_as_dict(run: WaveRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "outcomes": [
            {
                "ticket_id": o.ticket_id,
                "run_id": o.run_id,
                "status": o.status.value,
                "attempts": o.attempts,
                "resumed": o.resumed,
                "error": o.error,
            }
            for o in run.outcomes
        ],
        "all_succeeded": run.all_succeeded,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        plan = build_plan_from_board(
            board_dir=args.board,
            org_path=args.org,
            goal=args.goal,
            occupied_zones=args.occupied_zone,
            closed_gates=args.closed_gate,
            max_wave_size=args.max_wave_size,
        )
    except (OSError, ValueError, _wp.DuplicateTicketError) as exc:
        print(f"orchestrator: cannot plan wave: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(_plan_as_dict(plan), indent=2) if args.json else render_plan(plan))
        return 0

    if not args.run_id:
        print("orchestrator: --dispatch requires --run-id", file=sys.stderr)
        return 2
    if not args.invoker:
        print(
            "orchestrator: --dispatch requires --invoker module:callable "
            "(no agent invoker is built in)",
            file=sys.stderr,
        )
        return 2
    try:
        invoker = resolve_invoker(args.invoker)
    except AgentInvokerUnavailable as exc:
        print(f"orchestrator: {exc}", file=sys.stderr)
        return 2

    if plan.is_empty:
        print("orchestrator: nothing actionable to dispatch", file=sys.stderr)
        return 0

    try:
        config = OrchestratorConfig(
            max_parallel=args.max_parallel,
            task_timeout_seconds=args.task_timeout,
            max_attempts=args.max_attempts,
        )
    except ValueError as exc:
        print(f"orchestrator: {exc}", file=sys.stderr)
        return 2

    orchestrator = Orchestrator(invoker, config=config, journal_path=args.journal)

    import feature_flags as _ff

    attestation = None
    evidence_on = not args.no_evidence and _ff.enabled("organism_emit")
    if evidence_on and not (args.goal or plan.goal):
        print(
            "orchestrator: --dispatch needs --goal to write wave evidence "
            "(a ledger entry for goal '' attests nothing); pass --goal or --no-evidence",
            file=sys.stderr,
        )
        return 2

    if not evidence_on:
        run = orchestrator.dispatch(plan, run_id=args.run_id, board_dir=str(args.board))
    else:
        try:
            wave = args.wave if args.wave is not None else next_wave_number(default_ledger_path())
            run, attestation = dispatch_with_evidence(
                plan,
                orchestrator,
                run_id=args.run_id,
                wave=wave,
                goal=args.goal,
                board_dir=args.board,
            )
        except (OSError, ValueError, KeyError) as exc:
            print(f"orchestrator: wave evidence failed: {exc}", file=sys.stderr)
            return 2

    if args.json:
        payload = _run_as_dict(run)
        payload["attestation"] = str(attestation.path) if attestation is not None else ""
        print(json.dumps(payload, indent=2))
    else:
        print(render_run(run))
        if attestation is None:
            print("attestation: none (organism_emit off or --no-evidence)")
        else:
            print(f"attestation: {attestation.path}")
    return 0 if run.all_succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
