#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from _paths import ROOT

RBAC_CONFIG_PATH = ROOT / "config" / "rbac.yaml"
TENANT_BOUNDARY_PATH = ROOT / "config" / "tenant_boundary.yaml"
GATEWAY_PATH = ROOT / "tools" / "model_gateway" / "gateway.py"
CHECK_IN_TENANT_PATH = ROOT / "scripts" / "check_in_tenant.py"
GUARDRAIL_CHAIN_PATH = ROOT / "tools" / "guardrails" / "chain.py"
GOLDEN_RUNNER_PATH = ROOT / "evals" / "ws-e-guardrails" / "runner.py"
CLEAN_FIXTURE = ROOT / "evals" / "ws-e-guardrails" / "golden_set.json"
GAMING_FIXTURE = ROOT / "evals" / "ws-e-guardrails" / "golden_set_with_gaming_probe.json"


_GUARDRAIL_PROBE_TEXT = "contact me at jane.doe@example.com, card " + "4111 1111 1111 1111"
_GUARDRAIL_PROBE_ROLE = "security-lead"


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


def _rbac_mod() -> ModuleType:
    return _load_module(ROOT / "scripts" / "rbac.py", "_ws_e_health_rbac")


def _gateway_mod() -> ModuleType:
    return _load_module(GATEWAY_PATH, "_ws_e_health_gateway")


def _check_in_tenant_mod() -> ModuleType:
    return _load_module(CHECK_IN_TENANT_PATH, "_ws_e_health_check_in_tenant")


def _guardrail_chain_mod() -> ModuleType:
    return _load_module(GUARDRAIL_CHAIN_PATH, "_ws_e_health_guardrail_chain")


def _golden_runner_mod() -> ModuleType:
    return _load_module(GOLDEN_RUNNER_PATH, "_ws_e_health_golden_runner")


def check_rbac_drift() -> dict:
    rbac = _rbac_mod()
    problems: list[str] = []
    try:
        grants = rbac.load_grants(RBAC_CONFIG_PATH)
    except rbac.RbacConfigError as exc:
        return {"ok": False, "detail": f"config/rbac.yaml is structurally invalid: {exc}"}

    decision, reason = rbac.decide("agent:security-lead", "gate.approve", config=grants)
    if decision != "deny":
        problems.append(f"agent principal was NOT denied gate.approve ({reason})")

    for perm in sorted(rbac.FOUNDER_ONLY):
        founder_grant = grants.get("founder", {}).get(perm)
        if founder_grant not in {"allow", "own"}:
            problems.append(f"founder is not granted founder-only permission {perm!r}")
        for kind, perms in grants.items():
            if kind == "founder":
                continue
            if perm in perms:
                problems.append(f"non-founder kind {kind!r} carries founder-only permission {perm!r}")

    if problems:
        return {"ok": False, "detail": "; ".join(problems)}
    return {
        "ok": True,
        "detail": "agent:* denied gate.approve; gate.approve/config.edit.security remain founder-only",
    }


def check_gateway_host_pin_drift() -> dict:
    gw = _gateway_mod()
    rogue = gw.ModelRoute(
        name="rogue-model-route",
        url="https://evil-llm." + "example.com",
        role="model",
        auth="account",
        note="ws-e-health-check probe route — never a real backend",
    )
    try:
        gw.enforce_boundary(rogue)
    except gw.GatewayConfigError:
        pass
    else:
        return {
            "ok": False,
            "detail": "a rogue role=model route NOT pinned to the declared claude_model host "
            "was ACCEPTED by enforce_boundary — host-pin regression",
        }
    return {"ok": True, "detail": "rogue role=model host still refused by enforce_boundary (TN-1 host-pin holds)"}


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


def check_guardrail_eval_drift() -> dict:
    chain = _guardrail_chain_mod()
    problems: list[str] = []

    result = chain.guard(
        _GUARDRAIL_PROBE_TEXT,
        _GUARDRAIL_PROBE_ROLE,
        allowlist={chain.PRESIDIO_TOOL_NAME: [_GUARDRAIL_PROBE_ROLE]},
        flag_override=True,
    )
    if result.denied or result.action not in {"redact", "allow"}:
        problems.append(f"guardrail chain probe did not run cleanly (action={result.action!r}, reason={result.reason!r})")
    elif result.output_text == _GUARDRAIL_PROBE_TEXT:
        problems.append("guardrail chain did not alter a PII/secret-shaped probe (redaction miss)")

    runner = _golden_runner_mod()
    clean = runner.run_golden_set(CLEAN_FIXTURE)
    if not clean.judge_eligible:
        problems.append("clean golden-set fixture no longer passes (judge_eligible is False)")

    gaming = runner.run_golden_set(GAMING_FIXTURE)
    if gaming.judge_eligible:
        problems.append("anti-gaming fixture is judge_eligible — no-pass ⇒ RED gate has regressed to a false green")

    if problems:
        return {"ok": False, "detail": "; ".join(problems)}
    return {
        "ok": True,
        "detail": "guardrail chain redacts the probe; clean golden-set passes; anti-gaming fixture stays RED",
    }


def run() -> dict:
    rbac_drift = check_rbac_drift()
    gateway_drift = check_gateway_host_pin_drift()
    in_tenant_drift = check_in_tenant_drift()
    guardrail_drift = check_guardrail_eval_drift()
    healthy = rbac_drift["ok"] and gateway_drift["ok"] and in_tenant_drift["ok"] and guardrail_drift["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "rbac_drift": rbac_drift,
            "gateway_host_pin_drift": gateway_drift,
            "in_tenant_drift": in_tenant_drift,
            "guardrail_eval_drift": guardrail_drift,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ws_e_health_check.py — WS-E TENANT Maintenance health/eval (GATE-6, DAS-1587).\n\nAADL Stage 6 — Maintenance recurring health/eval for the WS-E tenant hardening\nsurface (RBAC / gateway boundary / in-tenant precondition / guardrail-eval\nchain, ``docs/design/ws-e-tenant-hardening.md``). Four checks, all READ-ONLY\n(never mutates ``config/rbac.yaml``, ``config/tenant_boundary.yaml``, the\nallow-list, or any ticket):\n\n  1. **RBAC drift** — reuses ``scripts/rbac.py: decide()`` (no fork) to assert\n     an agent principal still CANNOT hold ``gate.approve``, and reuses\n     ``scripts/rbac.py: load_grants()`` to assert ``config/rbac.yaml`` still\n     grants ``gate.approve`` / ``config.edit.security`` ONLY to ``founder``. A\n     config change that grants either to a non-founder kind is a finding\n     (``load_grants`` itself raises ``RbacConfigError`` on that tamper, which\n     this check surfaces rather than swallows).\n  2. **Gateway host-pin drift** — reuses\n     ``tools/model_gateway/gateway.py: enforce_boundary()`` (no fork) to\n     assert a rogue ``role="model"`` route pointing at a host OTHER than the\n     declared ``claude_model`` host in ``config/tenant_boundary.yaml`` is\n     still REFUSED (``GatewayConfigError``). A regression that stops pinning\n     (i.e. the rogue route is silently accepted) is a finding.\n  3. **In-tenant drift** — reuses ``scripts/check_in_tenant.py: evaluate()``\n     (no fork) over the tracked ``config/tenant_boundary.yaml`` to assert the\n     tenant boundary still holds (TN-1), the Claude model call remaining the\n     sole accepted external role.\n  4. **Guardrail/eval drift** — reuses ``tools/guardrails/chain.py: guard()``\n     (no fork) to assert the Presidio chain still redacts a planted\n     secret/PII probe when the flag is forced on, and reuses\n     ``evals/ws-e-guardrails/runner.py: run_golden_set()`` (no fork) to assert\n     the golden-set gate still passes clean and still gates RED (no\n     ``judge_eligible``) on the anti-gaming fixture — a no-pass MUST stay RED.\n\nExit codes: 0 = healthy (no drift, all probes correct), 1 = a finding — the\ncaller (Maintenance cadence) treats a non-zero exit as an ALERT, never a\nsilent skip. This script never opens a ticket or files itself; routing a\nfinding into a board ticket and into the ``daslab-learn`` Founder-review\ncadence is a human/orchestrator step documented in\n``docs/06-maintenance/ws-e-tenant-health.md`` — no autonomous\nself-modification (ADR-0029 G5).\n\nUsage::\n\n    python3 scripts/ws_e_health_check.py [--json]')
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("WS-E TENANT health check (GATE-6 Maintenance, DAS-1587)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
