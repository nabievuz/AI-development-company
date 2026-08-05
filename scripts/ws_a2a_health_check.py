#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from _paths import ROOT

FEATURES_PATH = ROOT / "config" / "features.yaml"
TENANT_BOUNDARY_PATH = ROOT / "config" / "tenant_boundary.yaml"
EVENTS_PATH = ROOT / "board" / ".events.jsonl"
CHECK_IN_TENANT_PATH = ROOT / "scripts" / "check_in_tenant.py"
FEATURE_FLAGS_PATH = ROOT / "scripts" / "feature_flags.py"
TEST_PATHS = (
    ROOT / "tests" / "test_a2a_outbound_endpoint.py",
    ROOT / "tests" / "test_a2a_intake.py",
)

FLAG = "a2a_outbound"
PUBLISH_EVENT_TYPE = "a2a_publish"


def _load_module(path: Path, name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _check_in_tenant_mod() -> ModuleType:
    return _load_module(CHECK_IN_TENANT_PATH, "_ws_a2a_health_check_in_tenant")


def _feature_flags_mod() -> ModuleType:
    return _load_module(FEATURE_FLAGS_PATH, "_ws_a2a_health_feature_flags")


def check_in_tenant_drift() -> dict:
    cit = _check_in_tenant_mod()
    try:
        import yaml
    except ImportError as exc:
        return {"ok": False, "detail": f"pyyaml unavailable — cannot evaluate boundary: {exc}"}
    if not TENANT_BOUNDARY_PATH.is_file():
        return {"ok": False, "detail": f"{TENANT_BOUNDARY_PATH} is missing (expected the TN-1 SSOT)"}
    data = yaml.safe_load(TENANT_BOUNDARY_PATH.read_text(encoding="utf-8")) or {}
    violations = cit.evaluate(data)
    if violations:
        return {"ok": False, "detail": "; ".join(violations)}
    n = sum(1 for e in (data.get("endpoints") or []) if isinstance(e, dict))
    return {"ok": True, "detail": f"TN-1 holds: all {n} declared endpoint(s) in-tenant (model call excepted)"}


def _newest_publish_event(events_path: Path) -> dict | None:
    if not events_path.is_file():
        return None
    newest: dict | None = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("event_type") == PUBLISH_EVENT_TYPE:
            newest = record
    return newest


def check_flag_publish_drift() -> dict:
    ff = _feature_flags_mod()
    live_flag = ff.enabled(FLAG, FEATURES_PATH)
    event = _newest_publish_event(EVENTS_PATH)

    if event is None:
        if live_flag:
            return {
                "ok": False,
                "detail": (
                    f"{FLAG!r} reads true in {FEATURES_PATH} but zero {PUBLISH_EVENT_TYPE!r} "
                    "events are logged in board/.events.jsonl — a flag flip with no "
                    "corresponding Founder-attributed publish event"
                ),
            }
        return {
            "ok": True,
            "detail": f"{FLAG!r} is false and zero {PUBLISH_EVENT_TYPE!r} events are logged "
            "— honest baseline (armed, never published), no drift",
        }

    expected_flag = event.get("decision") == "allow" and bool(event.get("flag_state"))
    if expected_flag != live_flag:
        return {
            "ok": False,
            "detail": (
                f"newest {PUBLISH_EVENT_TYPE!r} event (decision={event.get('decision')!r}, "
                f"flag_state={event.get('flag_state')!r}) implies {FLAG!r} should read "
                f"{expected_flag} but the live config reads {live_flag}"
            ),
        }
    return {
        "ok": True,
        "detail": f"{FLAG!r}={live_flag} agrees with the newest logged {PUBLISH_EVENT_TYPE!r} "
        f"event (decision={event.get('decision')!r})",
    }


def check_negative_test_drift() -> dict:
    missing = [str(p) for p in TEST_PATHS if not p.is_file()]
    if missing:
        return {"ok": False, "detail": f"expected test file(s) missing: {missing}"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *[str(p) for p in TEST_PATHS], "-q"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-15:])
        return {
            "ok": False,
            "detail": f"negative-test suite failed (exit={proc.returncode}): {tail}",
        }
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "no output"
    return {"ok": True, "detail": f"negative-test suite green: {summary}"}


def run() -> dict:
    in_tenant_drift = check_in_tenant_drift()
    flag_publish_drift = check_flag_publish_drift()
    negative_test_drift = check_negative_test_drift()
    healthy = in_tenant_drift["ok"] and flag_publish_drift["ok"] and negative_test_drift["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "in_tenant_drift": in_tenant_drift,
            "flag_publish_drift": flag_publish_drift,
            "negative_test_drift": negative_test_drift,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ws_a2a_health_check.py — A2A OUTBOUND Maintenance health/eval (GATE-6, DAS-1614/DAS-1624).\n\nAADL Stage 6 — Maintenance recurring health/eval for the A2A OUTBOUND surface\n(ADR-0040, ``docs/design/a2a-outbound.md``,\n``docs/06-maintenance/ws-a2a-outbound-health.md``). Three checks, all\nREAD-ONLY (never mutates ``config/features.yaml``, ``config/tenant_boundary.yaml``,\nor ``board/.events.jsonl``):\n\n  1. **In-tenant boundary drift (SC-003)** — reuses\n     ``scripts/check_in_tenant.py: evaluate()`` (no fork) over the tracked\n     ``config/tenant_boundary.yaml`` to assert the declared ``a2a_outbound``\n     endpoint (and every other code/IP endpoint) still resolves in-tenant.\n  2. **Flag/publish-state drift** — compares the live ``a2a_outbound`` value\n     in ``config/features.yaml`` (via ``scripts/feature_flags.py: enabled()``,\n     no second reader) against the newest ``event_type == "a2a_publish"``\n     record in ``board/.events.jsonl`` (event shape verbatim from\n     ``tools/a2a/publish.py: build_publish_event`` — read, not restated from\n     memory). Today\'s honest baseline is flag OFF with zero publish events,\n     which this check reports as OK-with-zero-events, never as an error. A\n     finding is either leg moving without the other: a live flag ON with no\n     logged Founder ``allow`` event (or vice versa: the newest logged event\n     says ``allow``/``flag_state: true`` but the live config still reads\n     ``false``).\n  3. **Negative-test drift (SC-005 "stays green" over time)** — re-runs\n     DAS-1612\'s suite (``tests/test_a2a_outbound_endpoint.py``,\n     ``tests/test_a2a_intake.py``) via a plain ``pytest`` subprocess (no new\n     test runner) and asserts it still passes clean.\n\nExit codes: 0 = healthy (no drift, all probes correct), 1 = a finding — the\ncaller (Maintenance cadence) treats a non-zero exit as an ALERT, never a\nsilent skip / auto-fix / auto-retry. This script never opens a ticket or\nflips ``a2a_outbound`` itself; routing a finding into a board ticket is a\nhuman/orchestrator step documented in\n``docs/06-maintenance/ws-a2a-outbound-health.md`` — no autonomous\nself-modification (ADR-0029 G5). Publishing stays a Founder-only act\n(QONUN-5, FR-003); this check never touches that decision.\n\nUsage::\n\n    python3 scripts/ws_a2a_health_check.py [--json]')
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("A2A OUTBOUND health check (GATE-6 Maintenance, DAS-1614/DAS-1624)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
