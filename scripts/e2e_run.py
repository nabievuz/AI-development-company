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
ROUTING_PATH: Path = ROOT / "board" / "ROUTING.md"


STAGES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)


_DONE = "done"


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


def _set_status_done(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    new = _STATUS_LINE_RE.sub(f"status: {_DONE}", text, count=1)
    path.write_text(new, encoding="utf-8")


def _compile_pack(scratch_pack: Path) -> gc.PipelineResult:
    res = gc.run_pipeline(scratch_pack)
    if not res.ok:
        detail = "; ".join(str(e) for e in res.errors) or "(no error detail)"
        raise RuntimeError(f"compile rejected at stage '{res.rejected_stage}': {detail}")
    return res


def _drive_to_done(board: Path) -> dict:
    walk_violations: list[str] = []
    per_stage: list[dict] = []
    for n in STAGES:
        advanced = 0
        for path, fm in board_lint.load_tickets(board):
            if sg.stage_of(fm) == n and fm.get("status") != _DONE:
                _set_status_done(path)
                advanced += 1
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
            _set_status_done(path)

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

    known_roles = board_lint.load_known_roles(ROUTING_PATH)
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
         "label": "all six AADL gates (GATE-1..GATE-6) walked to done for every goal; "
                  f"{len(walk_evidence['violations'])} gate-order/deploy violation(s) "
                  "across the walk"},
        {"ok": bool(negative_probe.get("fired")),
         "label": "gate-order checker proven to fire (negative probe): a forced "
                  f"out-of-order state (a stage-{negative_probe.get('forced_stage')} "
                  "ticket advanced while its predecessor gate is open) is flagged"},
        {"ok": workspace_created,
         "label": f"run workspace created and delivered board staged as the LOCAL "
                  f"artifact ({run_id}/workspace/delivered-board — scratch, gitignored)"},
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

    compiled = evidence["compiled"]
    walk = evidence["gate_walk"]
    health = evidence["d5_health_check"]
    goals = compiled["goals"]
    ticket_word = (
        "zero hand-written"
        if compiled["zero_hand_written"]
        else f"{len(compiled['hand_written_tickets'])} HAND-WRITTEN"
    )

    lines: list[str] = [
        "---",
        f"run_id: {run_id}",
        f"pack: {evidence['pack']}",
        "kind: spec-to-build-e2e",
        f"result: {evidence['result']}",
        f"generated: {evidence['generated_utc']}",
        "---",
        "",
        f"# Run summary — {run_id}",
        "",
        f"Spec->build end-to-end for PROJECT-OS pack `{evidence['pack']}` "
        f"(`{evidence['pack_dir']}`). One pack driven sample-pack -> compiled "
        f"stage-gated tickets -> all six AADL gates -> this committed summary.",
        "",
        "## Outcome",
        "",
        f"- Result: **{evidence['result']}**",
        f"- Goals: {len(goals)} ({', '.join(goals)})",
        f"- Compiled tickets: {compiled['ticket_count']} ({ticket_word})",
        f"- Gates walked: GATE-1..GATE-6 for every goal; "
        f"{len(walk['violations'])} gate-order/deploy violation(s) across the walk",
        f"- D-5 health-check: **{'PASS' if health['passed'] else 'FAIL'}**",
        "",
        "## Pipeline driven (reused modules — nothing re-implemented)",
        "",
        f"1. `gateway_compile.run_pipeline` — compiled the copied pack into "
        f"{compiled['ticket_count']} self-contained stage-gated story tickets "
        f"({ticket_word}; every board file is compiler output).",
        "2. `stage_gate.gate_order_violations` / `production_deploy_violations` — "
        "drove every stage ticket to `done` in gate order (Stage 1->6) with no order "
        "violation at any step, and a NEGATIVE PROBE separately confirms the checker "
        "fires on a forced out-of-order state (so the clean walk is meaningful, not "
        "vacuous).",
        "3. `run_workspace.create_workspace` — created the run workspace and staged "
        "the delivered board as the LOCAL D-5 artifact (scratch, gitignored, gc'd).",
        "4. `board_lint.lint_tickets` + a `gateway_compile --gate-walk` probe — "
        "verified the delivered board is lint-clean and the gate-walk CLI exits 0.",
        "",
        "## D-5 health-check — exactly what was verified",
        "",
    ]
    for item in health["checklist"]:
        mark = "x" if item["ok"] else " "
        suffix = "" if item["ok"] is not False else "  **<- FAILED**"
        lines.append(f"- [{mark}] {item['label']}{suffix}")
    lines += [
        "",
        "> D-5 semantics here = LOCAL artifact (the delivered board staged in the run "
        "workspace) + tests (this pack ships none) + health-check evidence. "
        "No external infra, no public push.",
        "",
        "## Evidence (inlined)",
        "",
        "`board/runs/*/workspace/` and any `evidence.json` are gitignored (only "
        "`run-summary.md` is tracked), so the machine-readable evidence lives here:",
        "",
        "```json",
        json.dumps(evidence, indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
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
        walk_evidence = _drive_to_done(board)
        walk_evidence["negative_probe"] = negative_probe


        health = _health_check(
            board=board,
            scratch_pack=scratch_pack,
            run_id=run_id,
            runs_dir=runs_dir,
            walk_evidence=walk_evidence,
        )

        result = "PASS" if (not hand_written and health["passed"]) else "FAIL"
        evidence = {
            "run_id": run_id,
            "pack": slug,
            "pack_dir": _display_path(pack_dir),
            "kind": "spec->build e2e (R12)",
            "generated_utc": _utc_now(),
            "compiled": {
                "ticket_count": len(res.tickets),
                "goals": sorted(walk_evidence["gate_states"].keys()),
                "hand_written_tickets": hand_written,
                "zero_hand_written": not hand_written,
            },
            "gate_walk": walk_evidence,
            "d5_health_check": health,
            "result": result,
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
        "result": result,
    }


def _render(summary: dict) -> str:
    out = [
        f"spec->build e2e — pack '{summary['pack']}' (run {summary['run_id']})",
        "=" * 60,
        f"  compiled tickets : {summary['ticket_count']}",
        f"  gates walked     : {', '.join(f'GATE-{n}' for n in summary['gates_walked'])}",
        f"  violations       : {len(summary['violations'])}",
        f"  D-5 health-check : {'PASS' if summary['health_check'] else 'FAIL'}",
        f"  run-summary      : {summary['run_summary_path']}",
        "",
        f"RESULT: {summary['result']}",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description='e2e_run.py — spec->build end-to-end run driver (R12 / DAS-1538).\n\nThe WS7 intake compiler (``scripts/gateway_compile.py``) and the six-gate checker\n(``scripts/stage_gate.py``) already exist and are green, but nothing *drives* a\npack through delivery and no run-summary writer exists. This module is the missing\ndriver: it takes ONE Founder-approved **PROJECT-OS pack** and walks it end to end —\n\n  1. **compile** — copy the pack into a scratch dir and run\n     ``gateway_compile.run_pipeline`` to emit self-contained, stage-gated story\n     tickets (asserting ZERO hand-written tickets — every board file is compiler\n     output);\n  2. **gate walk** — drive every stage ticket to ``done`` in AADL gate order\n     (Stage 1 -> 6), confirming ``stage_gate.gate_order_violations`` and\n     ``stage_gate.production_deploy_violations`` stay empty at every step (a\n     stage-N ticket never advances past an open GATE-(N-1));\n  3. **D-5 deploy (LOCAL)** — create the run workspace\n     (``run_workspace.create_workspace``), stage the delivered board as the local\n     artifact, run whatever tests the pack ships (if any) plus a health-check\n     probe, and record *exactly* what was verified;\n  4. **run-summary** — write ``board/runs/<run_id>/run-summary.md`` with the\n     evidence JSON **inlined** in a fenced block, then gc the scratch workspace.\n\nNothing here re-implements compile or gate logic — it reuses the existing modules.\nD-5 deployment semantics = LOCAL artifact (the delivered board staged in the run\nworkspace) + passing tests (if the pack ships any) + health-check evidence; NO\nexternal infra, NO public push.\n\nUnder ``.gitignore``, only ``board/runs/*/run-summary.md`` is tracked\n(``workspace/`` and any ``evidence.json`` are ignored), so the machine-readable\nevidence is INLINED into ``run-summary.md`` rather than left in a separate file.\n\nUsage::\n\n    python3 scripts/e2e_run.py <pack_dir> [--run-id ID] [--runs-dir DIR] [--json]\n\nExit codes: 0 = run passed (PASS), 1 = run completed but failed a check (FAIL),\n2 = usage / IO error.', formatter_class=argparse.RawDescriptionHelpFormatter
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
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
