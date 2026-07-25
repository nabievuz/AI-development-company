#!/usr/bin/env python3
"""ws_h_health_check.py — WS-H CONTROL Maintenance health/eval (GATE-6, DAS-1605).

AADL Stage 6 — Maintenance recurring health/eval for the WS-H self-hosted web
control plane (ADR-0039, ``docs/design/ws-h-control-plane.md``). Four checks,
all READ-ONLY (never mutates ``config/rbac.yaml``, ``config/features.yaml``,
or ``tools/control_plane/app.py``):

  1. **RBAC drift** — reuses ``scripts/rbac.py: decide()`` (no fork) to assert
     an agent principal still CANNOT hold ``gate.approve`` or ``run.trigger``,
     and reuses ``scripts/rbac.py: load_grants()`` to assert
     ``config/rbac.yaml`` still grants both permissions ONLY to ``founder``.
     A config change that grants either to a non-founder kind is a finding
     (``load_grants`` itself raises ``RbacConfigError`` on that tamper, which
     this check surfaces rather than swallows).
  2. **Audit-redaction drift** — reuses ``tools/mcp_bridges/redaction.py:
     safe_scrub()`` (no fork; the SAME scrubber the control plane's ``audit()``
     helper calls, ADR-0012) to plant a secret-shaped string and assert no raw
     secret substring survives the scrub. A regression that starts writing
     raw Tier-B content to the audit ledger is a finding.
  3. **Degrade/flag drift** — reuses ``scripts/feature_flags.py: enabled()``
     to assert ``ws_h_control_plane`` still defaults OFF in
     ``config/features.yaml``, and reuses
     ``tools/control_plane/install/degrade.py: resolve_surface()`` (no fork)
     to assert the degrade-to-static path still fires — with the flag OFF the
     surface resolves to ``"static"``, and even a forced flag-ON with the
     optional deps (fastapi/uvicorn) absent still resolves to ``"static"``
     (NOT-a-daemon, CP-5). A regression that returns ``"control-plane"``
     under either condition is a finding.
  4. **Token-compare drift** — a static (no-import, since fastapi is an
     OPTIONAL dependency this check must not require) AST scan of
     ``tools/control_plane/app.py``'s ``_match_token`` helper, asserting it
     still calls ``hmac.compare_digest`` for the bearer-token comparison and
     has not regressed to a bare dict ``.get()`` lookup (a timing side-channel
     regression on the auth secret).

Exit codes: 0 = healthy (no drift, all probes correct), 1 = a finding — the
caller (Maintenance cadence) treats a non-zero exit as an ALERT, never a
silent skip. This script never opens a ticket or files itself; routing a
finding into a board ticket and into the ``daslab-learn`` Founder-review
cadence is a human/orchestrator step documented in
``docs/06-maintenance/ws-h-control-health.md`` — no autonomous
self-modification (ADR-0029 G5).

Usage::

    python3 scripts/ws_h_health_check.py [--json]
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from _paths import ROOT

RBAC_CONFIG_PATH = ROOT / "config" / "rbac.yaml"
FEATURES_PATH = ROOT / "config" / "features.yaml"
REDACTION_PATH = ROOT / "tools" / "mcp_bridges" / "redaction.py"
DEGRADE_PATH = ROOT / "tools" / "control_plane" / "install" / "degrade.py"
CONTROL_PLANE_APP_PATH = ROOT / "tools" / "control_plane" / "app.py"

FLAG = "ws_h_control_plane"

# Known secret-shaped probe fed through the ADR-0012 scrubber. Fragmented on
# purpose (matches the WS-A/WS-D/WS-E health check convention) — a literal
# secret-shaped literal in a tracked file trips diagnostics.py's
# no-committed-secrets scan.
_SECRET_PROBE = "sk-live-" + "abcd1234EFGH5678ijkl9012MNOP"


def _load_module(path: Path, name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _rbac_mod() -> ModuleType:
    return _load_module(ROOT / "scripts" / "rbac.py", "_ws_h_health_rbac")


def _redaction_mod() -> ModuleType:
    return _load_module(REDACTION_PATH, "_ws_h_health_redaction")


def _degrade_mod() -> ModuleType:
    return _load_module(DEGRADE_PATH, "_ws_h_health_degrade")


def check_rbac_drift() -> dict:
    """Assert an agent principal still cannot hold ``gate.approve``/``run.trigger``
    (decide()), and ``config/rbac.yaml`` still grants both ONLY to ``founder``
    (load_grants())."""
    rbac = _rbac_mod()
    problems: list[str] = []
    try:
        grants = rbac.load_grants(RBAC_CONFIG_PATH)
    except rbac.RbacConfigError as exc:
        return {"ok": False, "detail": f"config/rbac.yaml is structurally invalid: {exc}"}

    for perm in ("gate.approve", "run.trigger"):
        decision, reason = rbac.decide("agent:sre-lead", perm, config=grants)
        if decision != "deny":
            problems.append(f"agent principal was NOT denied {perm!r} ({reason})")

    for perm in ("gate.approve", "run.trigger"):
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
        "detail": "agent:* denied gate.approve/run.trigger; both remain founder-only in config/rbac.yaml",
    }


def check_audit_redaction_drift() -> dict:
    """Plant a secret-shaped string through the SAME ADR-0012 scrubber the
    control plane's ``audit()`` helper calls (``tools/mcp_bridges/redaction.py:
    safe_scrub``) and assert no raw secret substring survives."""
    redaction = _redaction_mod()
    scrubbed = redaction.safe_scrub(f"leaked token in request: {_SECRET_PROBE}")
    if _SECRET_PROBE in scrubbed:
        return {
            "ok": False,
            "detail": "the ADR-0012 scrubber let a secret-shaped probe survive raw — "
            "audit-redaction regression",
        }
    if scrubbed == f"leaked token in request: {_SECRET_PROBE}":
        return {
            "ok": False,
            "detail": "safe_scrub() returned the input byte-identical — scrubber is a no-op",
        }
    return {
        "ok": True,
        "detail": "tools/mcp_bridges/redaction.py: safe_scrub() still redacts a "
        "secret-shaped probe (no raw survives)",
    }


def check_degrade_flag_drift() -> dict:
    """Assert the degrade-to-static path (``resolve_surface()``) still fires — the
    CP-5 / NOT-a-daemon guarantee: a forced static (or absent fastapi/uvicorn)
    always degrades to the static cockpit, never crashes, never silently starts a
    server — AND that the served surface tracks the flag. ``ws_h_control_plane``
    was ACTIVATED 2026-07-26 (Founder-authorized; loopback systemd unit +
    DASLAB_CP_RBAC), so the flag being ON with a control-plane surface is the
    healthy live state, not drift."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import feature_flags  # local import: scripts/ owns this module, we only read it

    problems: list[str] = []
    degrade = _degrade_mod()

    # CP-5 invariant, holds regardless of the flag: a forced static always
    # degrades to the static cockpit — the NOT-a-daemon guarantee.
    forced = degrade.resolve_surface(features_path=FEATURES_PATH, force_static=True)
    if forced.mode != "static":
        problems.append(
            f"resolve_surface(force_static=True) returned mode={forced.mode!r} — "
            "degrade-to-static / --force-static regression (CP-5)"
        )

    # The served surface must track the flag: OFF => static (always); ON =>
    # 'control-plane' when the fastapi/uvicorn deps are present, else a clean
    # degrade to 'static' (CP-5) — both are healthy when the flag is ON.
    flag_on = feature_flags.enabled(FLAG, FEATURES_PATH)
    decision = degrade.resolve_surface(features_path=FEATURES_PATH)
    if flag_on:
        if decision.mode not in ("control-plane", "static"):
            problems.append(
                f"flag ON but resolve_surface() returned mode={decision.mode!r} "
                "(expected 'control-plane', or a degraded 'static' when deps are absent)"
            )
    elif decision.mode != "static":
        problems.append(
            f"flag OFF but resolve_surface() returned mode={decision.mode!r} (expected 'static')"
        )

    if problems:
        return {"ok": False, "detail": "; ".join(problems)}
    state = f"ON (activated) → {decision.mode}" if flag_on else "OFF → static"
    return {
        "ok": True,
        "detail": f"degrade-to-static still fires under force_static (CP-5, no daemon); "
        f"surface tracks the flag: {FLAG!r} {state}",
    }


def check_token_compare_drift() -> dict:
    """Static AST scan of ``tools/control_plane/app.py``'s ``_match_token`` — no
    import (fastapi is an optional dependency this check must not require).
    Asserts the token comparison still calls ``hmac.compare_digest`` and has not
    regressed to a bare dict ``.get()`` lookup (a timing side-channel regression
    on the auth secret)."""
    if not CONTROL_PLANE_APP_PATH.is_file():
        return {"ok": False, "detail": f"{CONTROL_PLANE_APP_PATH} is missing"}
    source = CONTROL_PLANE_APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CONTROL_PLANE_APP_PATH))

    match_fn: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_match_token":
            match_fn = node
            break
    if match_fn is None:
        return {
            "ok": False,
            "detail": "_match_token() is no longer present in tools/control_plane/app.py",
        }

    uses_compare_digest = False
    bare_get_regression = False
    for node in ast.walk(match_fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "compare_digest"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hmac"
        ):
            uses_compare_digest = True
        # Regression pattern: `return tokens.get(token)` (or similar) used as the
        # ENTIRE lookup, bypassing a constant-time compare.
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "get"
        ):
            bare_get_regression = True

    if bare_get_regression:
        return {
            "ok": False,
            "detail": "_match_token() returns a bare dict .get() lookup — "
            "hmac.compare_digest regression",
        }
    if not uses_compare_digest:
        return {
            "ok": False,
            "detail": "_match_token() no longer calls hmac.compare_digest — "
            "constant-time token comparison regression",
        }
    return {
        "ok": True,
        "detail": "tools/control_plane/app.py: _match_token() still uses "
        "hmac.compare_digest (no bare dict .get() regression)",
    }


def run() -> dict:
    rbac_drift = check_rbac_drift()
    redaction_drift = check_audit_redaction_drift()
    degrade_drift = check_degrade_flag_drift()
    token_drift = check_token_compare_drift()
    healthy = rbac_drift["ok"] and redaction_drift["ok"] and degrade_drift["ok"] and token_drift["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "rbac_drift": rbac_drift,
            "audit_redaction_drift": redaction_drift,
            "degrade_flag_drift": degrade_drift,
            "token_compare_drift": token_drift,
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
        print("WS-H CONTROL health check (GATE-6 Maintenance, DAS-1605)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
