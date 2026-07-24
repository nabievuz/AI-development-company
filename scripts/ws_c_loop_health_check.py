#!/usr/bin/env python3
"""ws_c_loop_health_check.py — WS-C loop/sandbox Maintenance health/eval (GATE-6, DAS-1569).

AADL Stage 6 — Maintenance recurring health/eval for the WS-C durable LangGraph
loop substrate (``scripts/dgox/langgraph_loop.py``, ADR-0035) and its per-task
sandbox edge (``tools/sandbox/local_stub.py``, ADR-0035 LG-5). Three checks, all
READ-ONLY (never mutates any source, config, or the ledger) and all REUSE the
existing modules' own logic — no parallel reconciliation, wall, or ban logic is
re-implemented here:

  1. Board-canonical drift — builds a real ``GraphState``, projects it through
     ``langgraph_loop.project``, injects a divergence into the projected
     channels (simulating a stale/forked checkpoint), then calls
     ``langgraph_loop.reconcile`` (the real function, unmodified) and asserts
     the board value still wins: the divergence is detected, the returned
     ``board_state`` still carries the ORIGINAL board value (never the
     projected/checkpoint value), and the emitted reconciliation event still
     carries ``rule: board_wins_reconciliation``. A change that makes the
     checkpoint/projection win over the board — silently or otherwise — is a
     finding (LG-1/FR-002/C2 regression).
  2. Sandbox-wall drift — drives ``LocalStubSandbox`` (the real class,
     unmodified) through its four fail-closed walls with a live probe each:
     host escape (``..`` traversal, an absolute path, and an embedded NUL
     byte — three sub-probes), cross-task (a handle for a task_id with no live
     registration), unscoped credential (a ``ScopedSecret`` whose ``scope``
     does not match the opening ``task_id``), and unscoped/non-allow-listed
     egress (a ``net`` call with no ``egress_profile``/allow-list grant). Each
     probe must still be DENIED (``ok is False`` / ``SandboxEscapeError``). A
     wall that stops denying is a finding.
  3. Import-ban carve-out drift — reuses ``scripts/check_import_ban.py``'s own
     ``SANCTIONED_IMPORT_PATHS`` table and ``_is_sanctioned_import`` helper
     (never re-implemented) to assert the ADR-0035 carve-out has not widened:
     langgraph is allowed ONLY under ``scripts/dgox/``; it (and the other four
     banned donor libs) are still denied everywhere else, including the core
     ``requirements*.txt`` manifests; a live ``check()`` run over the repo is
     still clean. A carve-out that grows to a new path, a new lib, or the core
     manifest is a finding.

Exit codes: 0 = healthy (no drift found), 1 = a finding — the caller (the
Maintenance cadence) treats a non-zero exit as an ALERT, never a silent skip.
This script never opens a ticket or files itself; it only reports. Routing a
finding into a board ticket and into the ``daslab-learn`` Founder-review
cadence is a human/orchestrator step documented in
``docs/06-maintenance/ws-c-loop-health.md`` — this script does not self-modify
anything (no autonomous write-back), matching ADR-0029 G5's governed-
compounding discipline.

Usage::

    python3 scripts/ws_c_loop_health_check.py [--json]
"""
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

#: The exact, narrow carve-out ADR-0035 ratified — a finding if this widens.
_EXPECTED_SANCTIONED_PATHS = [("langgraph", "scripts/dgox/")]
_OTHER_BANNED_LIBS = ("agent-framework", "crewai", "agency-swarm", "superagi")


def _load_module(path: Path, name: str):
    """Load a sibling module by file path (self-locating import pattern).

    Mirrors ``ws_b_health_check.py:_load_wave_runner`` — reuses the SSOT module
    verbatim rather than re-implementing any of its logic.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses in these modules need self in sys.modules
    spec.loader.exec_module(mod)
    return mod


def _load_langgraph_loop():
    # scripts/dgox/langgraph_loop.py self-inserts scripts/ onto sys.path for its
    # own `from dgox.state import ...`; loading it by file path (not `import
    # scripts.dgox...`) matches how the substrate's own tests load it.
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    return _load_module(LANGGRAPH_LOOP_PATH, "_ws_c_health_langgraph_loop")


def _load_sandbox_stub():
    """Import the real ``contract``/``local_stub`` modules (not aliased copies).

    ``local_stub.py`` itself does ``from contract import (...)`` under the
    plain top-level name ``contract`` (see its own sys.path-insert docstring
    note); importing both under their real names here — instead of the
    self-locating alias trick used elsewhere in this file — keeps
    ``SandboxEscapeError`` (and friends) a SINGLE class object, so an
    ``except contract.SandboxEscapeError`` below actually matches what
    ``local_stub.open()`` raises.
    """
    if str(SANDBOX_DIR) not in sys.path:
        sys.path.insert(0, str(SANDBOX_DIR))
    import contract  # noqa: PLC0415 — intentional lazy/path-scoped import
    import local_stub  # noqa: PLC0415

    return contract, local_stub


def _load_import_ban():
    return _load_module(IMPORT_BAN_PATH, "_ws_c_health_check_import_ban")


# --------------------------------------------------------------------------- #
# 1. Board-canonical drift — checkpoint never a tiebreaker
# --------------------------------------------------------------------------- #


def check_board_canonical_drift() -> dict:
    """Board wins on an injected projection/checkpoint divergence (LG-1/§1.3)."""
    ll = _load_langgraph_loop()

    board_state = ll.GraphState(ticket_id="DAS-0000", dept="engineering", goal="ws-c-loop-health")
    projected = ll.project(board_state)

    # Inject a divergence — as if the checkpoint/projection held a stale or
    # forked value for a board-owned field.
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


# --------------------------------------------------------------------------- #
# 2. Sandbox-wall drift — the four fail-closed walls still deny
# --------------------------------------------------------------------------- #


def check_sandbox_wall_drift() -> dict:
    """Drive ``LocalStubSandbox``'s four fail-closed walls; each must still deny."""
    contract, local_stub = _load_sandbox_stub()

    findings: list[str] = []
    sandbox = local_stub.LocalStubSandbox()
    scope = contract.SandboxScope(
        task_id="ws-c-health-probe",
        workdir_mounts=[contract.Mount(host_path="/tmp/ws-c-health-probe-mount")],
    )
    handle = sandbox.open(task_id="ws-c-health-probe", scope=scope)

    # Wall 1 — host escape: '..' traversal, absolute path, embedded NUL byte.
    for rel, label in ((r"../../etc/passwd", "'..' traversal"), ("/etc/passwd", "absolute path"), ("a\x00b", "embedded NUL byte")):
        result = sandbox.exec(handle, ["read", rel])
        if result.ok:
            findings.append(f"host-escape wall: {label} probe {rel!r} was ALLOWED (expected deny)")

    # Wall 2 — cross-task: a handle for a task_id with no live registration.
    foreign_handle = contract.SandboxHandle(task_id="ws-c-health-other-task", backend="local-stub", token="not-a-real-token")
    cross_result = sandbox.exec(foreign_handle, ["read", "x"])
    if cross_result.ok:
        findings.append("cross-task wall: a handle for an unregistered task_id was ALLOWED (expected deny)")

    # Wall 3 — unscoped credential: scope.task_id != credential.scope must raise.
    bad_scope = contract.SandboxScope(
        task_id="ws-c-health-probe-2",
        credentials=[contract.ScopedSecret(name="probe-cred", value="unused", scope="some-other-task", ttl_seconds=60)],
    )
    try:
        sandbox.open(task_id="ws-c-health-probe-2", scope=bad_scope)
        findings.append("unscoped-credential wall: open() with a mis-scoped credential was ALLOWED (expected SandboxEscapeError)")
    except contract.SandboxEscapeError:
        pass

    # Wall 4 — unscoped/non-allow-listed egress: no egress_profile/allow-list grant.
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


# --------------------------------------------------------------------------- #
# 3. Import-ban carve-out drift — the ADR-0035 carve-out hasn't widened
# --------------------------------------------------------------------------- #


def check_import_ban_carveout_drift() -> dict:
    """``check_import_ban.py`` still narrowly allows langgraph only under scripts/dgox/."""
    cib = _load_import_ban()

    findings: list[str] = []

    if list(cib.SANCTIONED_IMPORT_PATHS) != _EXPECTED_SANCTIONED_PATHS:
        findings.append(
            f"SANCTIONED_IMPORT_PATHS is {cib.SANCTIONED_IMPORT_PATHS!r}, expected exactly "
            f"{_EXPECTED_SANCTIONED_PATHS!r} — the ADR-0035 carve-out widened"
        )

    # langgraph is allowed inside scripts/dgox/ ...
    if not cib._is_sanctioned_import("langgraph", "scripts/dgox/langgraph_loop.py"):
        findings.append("langgraph import under scripts/dgox/ is no longer sanctioned (carve-out narrowed unexpectedly)")
    # ... but denied everywhere else, including core requirements manifests.
    for rel in ("scripts/wave_runner.py", "scripts/agent_eval.py", "tests/test_ws_c_langgraph_substrate.py", "requirements.txt"):
        if cib._is_sanctioned_import("langgraph", rel):
            findings.append(f"langgraph import at {rel!r} is sanctioned — the carve-out widened outside scripts/dgox/")

    # The other four donor libs have NO carve-out anywhere, including scripts/dgox/.
    for lib in _OTHER_BANNED_LIBS:
        if cib._is_sanctioned_import(lib, "scripts/dgox/anything.py"):
            findings.append(f"{lib!r} is sanctioned under scripts/dgox/ — no donor lib besides langgraph may carve out")

    # Every banned lib name is still present (a shrunk BANNED list is also a drift).
    banned_names = {name for name, _ in cib.BANNED}
    expected_names = {"langgraph", "agent-framework", "crewai", "agency-swarm", "superagi"}
    if banned_names != expected_names:
        findings.append(f"BANNED lib set is {sorted(banned_names)}, expected {sorted(expected_names)}")

    # Live scan of the actual repo must still be clean (no parallel scan logic —
    # this calls check_import_ban's own check()).
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
    parser = argparse.ArgumentParser(description=__doc__)
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
