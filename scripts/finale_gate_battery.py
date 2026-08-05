#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from _paths import ROOT as REPO_ROOT

TAIL_LINES = 12


DEFAULT_GATE_TIMEOUT = 1800


@dataclass(frozen=True)
class Gate:

    name: str
    argv: list[str]
    informational: bool = False


@dataclass
class GateResult:

    name: str
    rc: int
    informational: bool
    status: str
    tail: str


def build_battery() -> list[Gate]:
    return [
        Gate("diagnostics", ["python3", "scripts/diagnostics.py"]),
        Gate("board_lint", ["python3", "scripts/board_lint.py"]),
        Gate("evals-enforce", ["python3", "scripts/agent_eval.py", "--all", "--enforce"]),
        Gate("evals-gaming", ["python3", "scripts/agent_eval.py", "--check-gaming"]),
        Gate("kpi-gaming", ["python3", "scripts/check_metric_gaming.py"]),
        Gate("spans", ["python3", "scripts/check_spans.py"]),
        Gate("commflows", ["python3", "scripts/check_comm_flows.py"]),
        Gate("commflows-shape", ["python3", "scripts/validate_commflows.py"]),
        Gate("import-ban", ["python3", "scripts/check_import_ban.py"]),
        Gate("attestation", ["python3", "scripts/check_attestation.py"]),
        Gate("gate6-attestation", ["python3", "scripts/check_gate6_attestation.py"]),
        Gate("wave-reconciliation", ["python3", "scripts/check_wave_reconciliation.py"]),
        Gate("kill-fork-drill", ["python3", "scripts/kill_drill.py", "--smoke"]),
        Gate("kill-switch-drill", ["python3", "scripts/kill_switch_drill.py", "--smoke"]),
        Gate("pytest", ["python3", "-m", "pytest", "-q"]),


        Gate(
            "readiness",
            ["python3", "scripts/check_heartbeat_readiness.py"],
            informational=True,
        ),
    ]


def _combine(stdout: str | None, stderr: str | None) -> str:
    out = stdout or ""
    err = stderr or ""
    if out and err:
        return f"{out}\n{err}"
    return out or err


def _tail(text: str, n: int = TAIL_LINES) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:])


def run_battery(
    gates: list[Gate],
    *,
    cwd: Path = REPO_ROOT,
    stream: bool = True,
    timeout: float = DEFAULT_GATE_TIMEOUT,
) -> tuple[list[GateResult], int]:
    results: list[GateResult] = []
    aggregate_rc = 0

    if stream:
        print(_render_header(len(gates)))

    for idx, gate in enumerate(gates, start=1):
        try:
            proc = subprocess.run(
                gate.argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            rc = proc.returncode
            tail = _tail(_combine(proc.stdout, proc.stderr))
        except subprocess.TimeoutExpired as exc:

            rc = 124
            partial = _combine(exc.stdout or "", exc.stderr or "")
            tail = _tail(f"{partial}\n[timed out after {timeout:g}s]")
        if rc == 0:
            status = "PASS"
        elif gate.informational:
            status = "INFO"
        else:
            status = "FAIL"
            aggregate_rc = 1
        result = GateResult(
            name=gate.name,
            rc=rc,
            informational=gate.informational,
            status=status,
            tail=tail,
        )
        results.append(result)
        if stream:
            print(_render_row(idx, result))

    if stream:
        print(_render_footer(results, aggregate_rc))

    return results, aggregate_rc


_WIDTH = 76


def _render_header(n: int) -> str:
    return (
        f"FINALE §4-P5 gate battery — running {n} gate(s) in order\n"
        + "=" * _WIDTH + "\n"
        + f"  {'#':>2}  {'STATUS':<6}  {'RC':>3}  GATE\n"
        + "-" * _WIDTH
    )


def _render_row(idx: int, result: GateResult) -> str:
    tag = "  (informational)" if result.informational else ""
    return f"  {idx:>2}  {result.status:<6}  {result.rc:>3}  {result.name}{tag}"


def _render_footer(results: list[GateResult], aggregate_rc: int) -> str:
    required = [r for r in results if not r.informational]
    green = [r for r in required if r.rc == 0]
    failed = [r for r in required if r.rc != 0]
    info = [r for r in results if r.informational]
    info_nonzero = [r for r in info if r.rc != 0]

    lines = ["-" * _WIDTH]
    verdict = "PASS" if aggregate_rc == 0 else "FAIL"
    summary = f"BATTERY: {verdict} — {len(green)}/{len(required)} required gate(s) green"
    if failed:
        summary += f", {len(failed)} FAILED"
    if info:
        summary += f"; {len(info)} informational ({len(info_nonzero)} non-zero, not fatal)"
    summary += f"  (aggregate rc {aggregate_rc})"
    lines.append(summary)

    for r in failed:
        lines.append(f"  FAIL  {r.name}  (rc {r.rc})")
        for ln in r.tail.splitlines():
            lines.append(f"        {ln}")
    return "\n".join(lines)


def _render_list(gates: list[Gate]) -> str:
    width = max((len(g.name) for g in gates), default=4)
    lines = [f"FINALE §4-P5 gate battery — {len(gates)} gate(s) (not run)", "=" * _WIDTH]
    for idx, g in enumerate(gates, start=1):
        tag = "  [INFO]" if g.informational else "        "
        lines.append(f"  {idx:>2}  {g.name:<{width}}{tag}  {' '.join(g.argv)}")
    return "\n".join(lines)


def _gate_to_dict(gate: Gate) -> dict:
    return {"name": gate.name, "argv": list(gate.argv), "informational": gate.informational}


def _result_to_dict(result: GateResult) -> dict:
    return {
        "name": result.name,
        "rc": result.rc,
        "informational": result.informational,
        "status": result.status,
        "tail": result.tail,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description='finale_gate_battery.py — the FINALE §4-P5 gate battery, a read-only aggregator.',
    )
    ap.add_argument("--json", action="store_true", help="emit results as JSON")
    ap.add_argument(
        "--list",
        dest="list_battery",
        action="store_true",
        help="print the battery in order and exit without running it",
    )
    args = ap.parse_args(argv)

    gates = build_battery()

    if args.list_battery:
        if args.json:
            print(json.dumps([_gate_to_dict(g) for g in gates], indent=2))
        else:
            print(_render_list(gates))
        return 0


    results, aggregate_rc = run_battery(gates, stream=not args.json)
    if args.json:
        print(
            json.dumps(
                {
                    "aggregate_rc": aggregate_rc,
                    "gates": len(results),
                    "results": [_result_to_dict(r) for r in results],
                },
                indent=2,
            )
        )
    return aggregate_rc


if __name__ == "__main__":
    raise SystemExit(main())
