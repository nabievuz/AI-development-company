#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from _paths import ROOT

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import board_lint
import gateway_compile as gc
import run_workspace
import stage_gate as sg

DEFAULT_RUNS_DIR: Path = ROOT / "board" / "runs"
GATEWAY_SCRIPT: Path = _HERE / "gateway_compile.py"


STAGES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)


_DONE = "done"


EVIDENCE_CLASS = "simulation"


CHECKS_GREEN = "checks-green"
CHECKS_RED = "checks-red"


GATE_WALK_PROVES = (
    "stage_gate.gate_order_violations and stage_gate.production_deploy_violations stay "
    "empty while ticket status fields are rewritten to 'done' in stage order, and the "
    "same checker fires on a forced out-of-order state"
)


GATE_WALK_DOES_NOT_PROVE = (
    "no agent ran, no code was written, no PR was merged and no CI executed: the walk "
    "rewrites a 'status:' line in a scratch copy of the board, so it is NOT delivery "
    "evidence and must never be counted as one"
)


_STATUS_LINE_RE = re.compile(r"(?m)^status:[^\n]*$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _slug_of(pack_dir: Path) -> str:
    data = yaml.safe_load((pack_dir / gc.MANIFEST_NAME).read_text(encoding="utf-8"))
    return str(data["name"])


def _display_path(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def _simulate_status_done(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    new = _STATUS_LINE_RE.sub(f"status: {_DONE}", text, count=1)
    path.write_text(new, encoding="utf-8")


def _compile_pack(scratch_pack: Path) -> gc.PipelineResult:
    res = gc.run_pipeline(scratch_pack)
    if not res.ok:
        detail = "; ".join(str(e) for e in res.errors) or "(no error detail)"
        raise RuntimeError(f"compile rejected at stage '{res.rejected_stage}': {detail}")
    return res


def _simulate_gate_walk(board: Path) -> dict:
    walk_violations: list[str] = []
    per_stage: list[dict] = []
    rewritten = 0
    for n in STAGES:
        advanced = 0
        for path, fm in board_lint.load_tickets(board):
            if sg.stage_of(fm) == n and fm.get("status") != _DONE:
                _simulate_status_done(path)
                advanced += 1
                rewritten += 1
        tickets = board_lint.load_tickets(board)
        order_v = sg.gate_order_violations(tickets)
        deploy_v = sg.production_deploy_violations(tickets)
        walk_violations.extend(order_v)
        walk_violations.extend(deploy_v)
        per_stage.append({
            "stage": n,
            "gate": f"GATE-{n}",
            "tickets_advanced": advanced,
            "order_violations": order_v,
            "deploy_violations": deploy_v,
        })


    for path, fm in board_lint.load_tickets(board):
        if sg.stage_of(fm) is None and fm.get("status") != _DONE:
            _simulate_status_done(path)
            rewritten += 1

    tickets = board_lint.load_tickets(board)
    gate_states = sg.gate_status(tickets)
    all_done = bool(gate_states) and all(
        all(stages.get(n) == _DONE for n in STAGES) for stages in gate_states.values()
    )
    return {
        "gates_walked": list(STAGES),
        "per_stage": per_stage,
        "gate_states": {g: {str(n): s for n, s in st.items()} for g, st in gate_states.items()},
        "all_goals_all_gates_done": all_done,
        "violations": walk_violations,
        "simulated_status_rewrites": rewritten,
        "proves": GATE_WALK_PROVES,
        "does_not_prove": GATE_WALK_DOES_NOT_PROVE,
    }


def _negative_gate_probe(board: Path) -> dict:
    tickets = board_lint.load_tickets(board)
    for path, fm in tickets:
        stage = sg.stage_of(fm)
        if stage is not None and stage >= 2:
            mutated = [
                (p, {**f, "status": _DONE} if p == path else f) for p, f in tickets
            ]
            violations = sg.gate_order_violations(mutated)
            return {
                "fired": bool(violations),
                "forced_ticket": fm.get("id"),
                "forced_stage": stage,
                "sample_violation": violations[0] if violations else None,
                "verifies": "gate_order_violations flags a stage>=2 ticket advanced "
                            "while its predecessor gate is still open",
            }
    return {"fired": False, "forced_ticket": None,
            "note": "no stage>=2 ticket available to probe"}


def _detect_and_run_pack_tests(scratch_pack: Path) -> dict:
    candidates = [
        p for p in (*scratch_pack.rglob("test_*.py"), *scratch_pack.rglob("*_test.py"))
        if "board-tickets" not in p.parts
    ]
    if not candidates:
        return {
            "present": False,
            "passed": None,
            "returncode": None,
            "detail": "pack ships no runnable test suite (docs-only PROJECT-OS pack)",
        }
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(scratch_pack)],
        cwd=str(scratch_pack),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "present": True,
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "detail": f"{len(candidates)} pack test file(s) run via pytest",
    }


def _health_check(
    *,
    board: Path,
    scratch_pack: Path,
    run_id: str,
    runs_dir: Path,
    walk_evidence: dict,
) -> dict:

    known_roles = board_lint.load_known_roles()
    tickets = board_lint.load_tickets(board)
    lint_violations = board_lint.lint_tickets(tickets, known_roles)
    lint_clean = lint_violations == []


    negative_probe = walk_evidence.get("negative_probe", {})
    gate_walk_clean = (
        walk_evidence["all_goals_all_gates_done"]
        and not walk_evidence["violations"]
        and bool(negative_probe.get("fired"))
    )


    workspace = run_workspace.create_workspace(run_id, runs_dir)
    workspace_created = workspace.is_dir()
    artifact = workspace / "delivered-board"
    if artifact.exists():
        shutil.rmtree(artifact)
    shutil.copytree(board, artifact)


    probe_argv = [sys.executable, str(GATEWAY_SCRIPT), str(scratch_pack), "--gate-walk"]
    probe = subprocess.run(
        probe_argv,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DASLAB_ROOT": str(ROOT)},
    )
    probe_ok = probe.returncode == 0


    pack_tests = _detect_and_run_pack_tests(scratch_pack)
    tests_ok = (not pack_tests["present"]) or bool(pack_tests["passed"])


    checklist = [
        {"ok": lint_clean,
         "label": f"board_lint on the delivered board: {len(tickets)} tickets, "
                  f"{len(lint_violations)} violation(s)"},
        {"ok": (walk_evidence["all_goals_all_gates_done"] and not walk_evidence["violations"]),
         "label": "simulated gate walk (status fields rewritten to done in stage order, "
                  "no agent and no CI involved) raised "
                  f"{len(walk_evidence['violations'])} gate-order/deploy violation(s)"},
        {"ok": bool(negative_probe.get("fired")),
         "label": "gate-order checker proven to fire (negative probe): a forced "
                  f"out-of-order state (a stage-{negative_probe.get('forced_stage')} "
                  "ticket advanced while its predecessor gate is open) is flagged"},
        {"ok": workspace_created,
         "label": f"run workspace created and the compiled board copied into it "
                  f"({run_id}/workspace/delivered-board — scratch, gitignored; a file "
                  "copy, not a deployment)"},
        {"ok": probe_ok,
         "label": f"probe `gateway_compile --gate-walk` over the delivered board exited "
                  f"{probe.returncode} (0 = board may advance)"},
        {"ok": (pack_tests["passed"] if pack_tests["present"] else None),
         "label": f"pack-shipped tests: {pack_tests['detail']}"
                  + (f" (exit {pack_tests['returncode']})" if pack_tests["present"] else "")},
    ]

    passed = bool(lint_clean and gate_walk_clean and workspace_created and probe_ok and tests_ok)
    return {
        "passed": passed,
        "evidence_class": EVIDENCE_CLASS,
        "delivery_evidence": False,
        "board_lint": {
            "tickets": len(tickets),
            "violations": lint_violations,
            "clean": lint_clean,
        },
        "gate_walk_clean": gate_walk_clean,
        "workspace_created": workspace_created,
        "workspace_path": _display_path(workspace),
        "local_artifact": _display_path(artifact),
        "probe": {
            "command": ["python3", "scripts/gateway_compile.py",
                        f"<ephemeral-scratch>/{scratch_pack.name}", "--gate-walk"],
            "ephemeral": True,
            "note": "the pack arg was an ephemeral scratch copy (gc'd after the run; the "
                    "literal path is machine-specific and intentionally elided); "
                    "reproduce via `python3 scripts/e2e_run.py <pack_dir>`",
            "returncode": probe.returncode,
            "exit_ok": probe_ok,
            "verifies": "gate-walk CLI over the delivered board: 0 => board may advance",
        },
        "negative_probe": negative_probe,
        "pack_tests": pack_tests,
        "checklist": checklist,
    }


def _write_run_summary(runs_dir: Path, run_id: str, evidence: dict) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run-summary.md"
    document = {
        "kind": "e2e-gate-checker-simulation",
        "evidence_class": EVIDENCE_CLASS,
        "delivery_evidence": False,
        "claims": {
            "proves": GATE_WALK_PROVES,
            "does_not_prove": GATE_WALK_DOES_NOT_PROVE,
        },
        "evidence": evidence,
    }
    path.write_text(
        "```json\n" + json.dumps(document, indent=2, sort_keys=True) + "\n```\n",
        encoding="utf-8",
    )
    return path


def e2e_run(
    pack_dir: Path | str,
    *,
    run_id: str | None = None,
    runs_dir: Path | str | None = None,
) -> dict:
    pack_dir = Path(pack_dir).resolve()
    if not (pack_dir / gc.MANIFEST_NAME).is_file():
        raise FileNotFoundError(f"not a PROJECT-OS pack (no {gc.MANIFEST_NAME}): {pack_dir}")
    runs_dir = Path(runs_dir).resolve() if runs_dir else DEFAULT_RUNS_DIR
    slug = _slug_of(pack_dir)
    run_id = run_id or f"e2e-{slug}-{_utc_stamp()}"

    scratch_root = Path(tempfile.mkdtemp(prefix=f"e2e-{slug}-"))
    try:

        scratch_pack = scratch_root / slug
        shutil.copytree(pack_dir, scratch_pack)
        res = _compile_pack(scratch_pack)
        board = scratch_pack / "board-tickets"


        on_disk = {p.resolve() for p in board.glob("DAS-*.md")}
        produced = {p.resolve() for p in res.tickets}
        hand_written = sorted(p.name for p in on_disk - produced)


        negative_probe = _negative_gate_probe(board)
        walk_evidence = _simulate_gate_walk(board)
        walk_evidence["negative_probe"] = negative_probe


        health = _health_check(
            board=board,
            scratch_pack=scratch_pack,
            run_id=run_id,
            runs_dir=runs_dir,
            walk_evidence=walk_evidence,
        )

        checks = CHECKS_GREEN if (not hand_written and health["passed"]) else CHECKS_RED
        evidence = {
            "run_id": run_id,
            "pack": slug,
            "pack_dir": _display_path(pack_dir),
            "kind": "e2e-gate-checker-simulation",
            "evidence_class": EVIDENCE_CLASS,
            "delivery_evidence": False,
            "generated_utc": _utc_now(),
            "compiled": {
                "ticket_count": len(res.tickets),
                "goals": sorted(walk_evidence["gate_states"].keys()),
                "hand_written_tickets": hand_written,
                "zero_hand_written": not hand_written,
            },
            "gate_walk": walk_evidence,
            "health_check": health,
            "checks": checks,
        }


        summary_path = _write_run_summary(runs_dir, run_id, evidence)
    finally:


        run_workspace.gc_workspace(run_id, runs_dir)
        shutil.rmtree(scratch_root, ignore_errors=True)

    return {
        "run_id": run_id,
        "pack": slug,
        "ticket_count": evidence["compiled"]["ticket_count"],
        "gates_walked": walk_evidence["gates_walked"],
        "violations": walk_evidence["violations"],
        "health_check": health["passed"],
        "run_summary_path": str(summary_path),
        "evidence_class": EVIDENCE_CLASS,
        "delivery_evidence": False,
        "checks": checks,
    }


def _render(summary: dict) -> str:
    out = [
        f"gate-checker simulation — pack '{summary['pack']}' (run {summary['run_id']})",
        "=" * 60,
        f"  compiled tickets      : {summary['ticket_count']}",
        f"  stages simulated      : {', '.join(f'GATE-{n}' for n in summary['gates_walked'])}",
        f"  violations            : {len(summary['violations'])}",
        f"  health-check          : {'green' if summary['health_check'] else 'red'}",
        f"  run-summary           : {summary['run_summary_path']}",
        "",
        f"CHECKS: {summary['checks']}",
        "NOT DELIVERY EVIDENCE: " + GATE_WALK_DOES_NOT_PROVE,
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "e2e_run.py — drives ONE PROJECT-OS pack through gateway_compile and then "
            "SIMULATES an AADL gate walk over the compiled tickets by rewriting their "
            "'status:' fields in a scratch copy. What it proves: " + GATE_WALK_PROVES
            + ". What it does NOT prove: " + GATE_WALK_DOES_NOT_PROVE
            + ". Exit codes: 0 = every check green, "
            "1 = a check failed, 2 = usage / IO error."
        )
    )
    ap.add_argument("pack_dir", help="the PROJECT-OS pack directory (e.g. evals/e2e/sample-pack)")
    ap.add_argument("--run-id", default=None, help="run id (default: e2e-<slug>-<utc-stamp>)")
    ap.add_argument("--runs-dir", default=None,
                    help="the board/runs/ root (default: board/runs) — run-summary.md lands here")
    ap.add_argument("--json", action="store_true", help="machine-readable summary on stdout")
    args = ap.parse_args(argv)

    pack_dir = Path(args.pack_dir)
    if not pack_dir.is_dir():
        print(f"ERROR: pack dir not found: {pack_dir}", file=sys.stderr)
        return 2

    runs_dir = Path(args.runs_dir) if args.runs_dir else None
    try:
        summary = e2e_run(pack_dir, run_id=args.run_id, runs_dir=runs_dir)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(_render(summary))
    return 0 if summary["checks"] == CHECKS_GREEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
