#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from _paths import ROOT

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

SANDBOX_DIR = ROOT / "tools" / "sandbox"
IMPORT_BAN_PATH = _HERE / "check_import_ban.py"
LANGGRAPH_LOOP_PATH = _HERE / "dgox" / "langgraph_loop.py"


_EXPECTED_SANCTIONED_PATHS = [("langgraph", "scripts/dgox/")]
_OTHER_BANNED_LIBS = ("agent-framework", "crewai", "agency-swarm", "superagi")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_langgraph_loop():


    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    return _load_module(LANGGRAPH_LOOP_PATH, "_ws_c_health_langgraph_loop")


def _load_sandbox_stub():
    if str(SANDBOX_DIR) not in sys.path:
        sys.path.insert(0, str(SANDBOX_DIR))
    import contract
    import local_stub

    return contract, local_stub


def _load_import_ban():
    return _load_module(IMPORT_BAN_PATH, "_ws_c_health_check_import_ban")


def check_board_canonical_drift() -> dict:
    ll = _load_langgraph_loop()

    board_state = ll.GraphState(ticket_id="DAS-0000", dept="engineering", goal="ws-c-loop-health")
    projected = ll.project(board_state)


    projected.channels["identity"]["dept"] = "product"

    reconciliation = ll.reconcile(projected, board_state)

    if not reconciliation.diverged:
        return {
            "ok": False,
            "detail": "reconcile() did not detect the injected divergence at all — "
            "board_state.dept mismatch went unnoticed (LG-1/§1.3 regression)",
        }
    if reconciliation.board_state.dept != "engineering":
        return {
            "ok": False,
            "detail": f"reconcile() returned board_state.dept={reconciliation.board_state.dept!r}, "
            "expected the ORIGINAL board value 'engineering' — the projection/checkpoint value "
            "won instead of the board (checkpoint used as a tiebreaker, LG-1/FR-002/C2 regression)",
        }
    if reconciliation.event is None or reconciliation.event.get("rule") != "board_wins_reconciliation":
        return {
            "ok": False,
            "detail": f"reconcile() event on a real divergence was {reconciliation.event!r}, "
            "expected rule='board_wins_reconciliation'",
        }
    return {
        "ok": True,
        "detail": "reconcile() detected the injected divergence and the board value "
        "('engineering') won; checkpoint/projection was NOT consulted as a tiebreaker",
    }


def check_sandbox_wall_drift() -> dict:
    contract, local_stub = _load_sandbox_stub()

    findings: list[str] = []
    sandbox = local_stub.LocalStubSandbox()
    scope = contract.SandboxScope(
        task_id="ws-c-health-probe",
        workdir_mounts=[contract.Mount(host_path="/tmp/ws-c-health-probe-mount")],
    )
    handle = sandbox.open(task_id="ws-c-health-probe", scope=scope)


    for rel, label in ((r"../../etc/passwd", "'..' traversal"), ("/etc/passwd", "absolute path"), ("a\x00b", "embedded NUL byte")):
        result = sandbox.exec(handle, ["read", rel])
        if result.ok:
            findings.append(f"host-escape wall: {label} probe {rel!r} was ALLOWED (expected deny)")


    foreign_handle = contract.SandboxHandle(task_id="ws-c-health-other-task", backend="local-stub", token="not-a-real-token")
    cross_result = sandbox.exec(foreign_handle, ["read", "x"])
    if cross_result.ok:
        findings.append("cross-task wall: a handle for an unregistered task_id was ALLOWED (expected deny)")


    bad_scope = contract.SandboxScope(
        task_id="ws-c-health-probe-2",
        credentials=[contract.ScopedSecret(name="probe-cred", value="unused", scope="some-other-task", ttl_seconds=60)],
    )
    try:
        sandbox.open(task_id="ws-c-health-probe-2", scope=bad_scope)
        findings.append("unscoped-credential wall: open() with a mis-scoped credential was ALLOWED (expected SandboxEscapeError)")
    except contract.SandboxEscapeError:
        pass


    egress_result = sandbox.exec(handle, ["net", "http://not-allow-listed.example.com"])
    if egress_result.ok:
        findings.append("egress wall: a non-allow-listed host was ALLOWED (expected deny)")

    sandbox.close(handle)

    if findings:
        return {"ok": False, "detail": "; ".join(findings)}
    return {
        "ok": True,
        "detail": "all four fail-closed walls still deny: host escape ('..'/absolute/NUL), "
        "cross-task, unscoped credential, non-allow-listed egress",
    }


def check_import_ban_carveout_drift() -> dict:
    cib = _load_import_ban()

    findings: list[str] = []

    if list(cib.SANCTIONED_IMPORT_PATHS) != _EXPECTED_SANCTIONED_PATHS:
        findings.append(
            f"SANCTIONED_IMPORT_PATHS is {cib.SANCTIONED_IMPORT_PATHS!r}, expected exactly "
            f"{_EXPECTED_SANCTIONED_PATHS!r} — the ADR-0035 carve-out widened"
        )


    if not cib._is_sanctioned_import("langgraph", "scripts/dgox/langgraph_loop.py"):
        findings.append("langgraph import under scripts/dgox/ is no longer sanctioned (carve-out narrowed unexpectedly)")

    for rel in ("scripts/wave_runner.py", "scripts/agent_eval.py", "tests/test_ws_c_langgraph_substrate.py", "requirements.txt"):
        if cib._is_sanctioned_import("langgraph", rel):
            findings.append(f"langgraph import at {rel!r} is sanctioned — the carve-out widened outside scripts/dgox/")


    for lib in _OTHER_BANNED_LIBS:
        if cib._is_sanctioned_import(lib, "scripts/dgox/anything.py"):
            findings.append(f"{lib!r} is sanctioned under scripts/dgox/ — no donor lib besides langgraph may carve out")


    banned_names = {name for name, _ in cib.BANNED}
    expected_names = {"langgraph", "agent-framework", "crewai", "agency-swarm", "superagi"}
    if banned_names != expected_names:
        findings.append(f"BANNED lib set is {sorted(banned_names)}, expected {sorted(expected_names)}")


    live_hits = cib.check(ROOT)
    if live_hits:
        findings.append(f"live check_import_ban.check() found {len(live_hits)} violation(s): {'; '.join(live_hits[:5])}")

    if findings:
        return {"ok": False, "detail": "; ".join(findings)}
    return {
        "ok": True,
        "detail": "langgraph carve-out is exactly scripts/dgox/ (no other lib, no other path, "
        "core requirements clean); live check_import_ban scan is clean",
    }


def run() -> dict:
    board_canonical = check_board_canonical_drift()
    sandbox_walls = check_sandbox_wall_drift()
    import_ban = check_import_ban_carveout_drift()
    healthy = board_canonical["ok"] and sandbox_walls["ok"] and import_ban["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "board_canonical_drift": board_canonical,
            "sandbox_wall_drift": sandbox_walls,
            "import_ban_carveout_drift": import_ban,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ws_c_loop_health_check.py — WS-C loop/sandbox Maintenance health/eval (GATE-6, DAS-1569)')
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("WS-C loop/sandbox health check (GATE-6 Maintenance, DAS-1569)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
