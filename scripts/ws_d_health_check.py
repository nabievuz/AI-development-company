#!/usr/bin/env python3
"""ws_d_health_check.py — WS-D LENS Maintenance health/eval (GATE-6, DAS-1577).

AADL Stage 6 — Maintenance recurring health/eval for the observability lens
(the self-host Langfuse exporter, ADR-0036) and the eval-tool admission edge
(promptfoo/AgentShield/Presidio, ADR-0033). Three checks, all READ-ONLY (never
mutates a config file, the compiled allow-list, or any tenant boundary entry):

  1. Redaction-on-export drift — feeds a battery of known secret-shaped span
     attributes through the ADR-0012 scrubber path the exporter itself uses
     (``tools/observability/otlp_exporter.py: redact_span``, which wraps
     ``tools/mcp_bridges/redaction.py``, no fork) and asserts every Tier-B
     attribute comes back redacted while the Tier-M ids (``span_id`` /
     ``trace_id``) survive untouched. A miss here means a secret could reach
     the wire.
  2. In-tenant target drift — reuses ``scripts/check_in_tenant.py`` (via the
     exporter's own ``assert_in_tenant``, no parallel boundary logic) to
     confirm the ``langfuse_observability`` endpoint in
     ``config/tenant_boundary.yaml`` still resolves in-tenant. A hosted
     Langfuse Cloud / LangSmith URL slipping in is a finding.
  3. Eval-tool allow-list drift — recompiles ``board/.tool-allowlist.json``
     in-memory via ``scripts/gen_subagents.py: compile_tool_allowlist()`` (the
     exact SSOT compiler WS-A's DAS-1551 check already reuses, no duplicate
     mechanism) and diffs it against the tracked file, then asserts the
     promptfoo/AgentShield/Presidio grants are present and that NO compiled
     entry ever carries a literal ``"*"`` role.

Exit codes: 0 = healthy (no drift, all probes correct), 1 = a finding — the
caller (Maintenance cadence) treats a non-zero exit as an ALERT, never a
silent skip. This script never opens a ticket or files itself; routing a
finding into a board ticket and into the ``daslab-learn`` Founder-review
cadence is a human/orchestrator step documented in
``docs/06-maintenance/ws-d-lens-health.md`` — no autonomous self-modification
(ADR-0029 G5).

Usage::

    python3 scripts/ws_d_health_check.py [--json]
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

import gen_subagents  # noqa: E402  (reused compiler — no parallel allow-list logic)

TOOL_ALLOWLIST_PATH = ROOT / "board" / ".tool-allowlist.json"
OTLP_EXPORTER_PATH = ROOT / "tools" / "observability" / "otlp_exporter.py"
TENANT_BOUNDARY_PATH = ROOT / "config" / "tenant_boundary.yaml"

# The eval-tool grants this ticket is scoped to (ADR-0033 admission edge).
_EVAL_TOOL_ROLE_KEYS = (
    "mcp__promptfoo",
    "mcp__agentshield",
    "mcp__presidio",
)

# Known secret-shaped span attribute probes: (label, key, value, must_be_redacted).
# Tier-M keys (span_id/trace_id) must survive AS-IS — no over-redaction. Tier-B
# keys carrying secret-shaped content must come back scrubbed.
# NOTE: secret-shaped values below are assembled from fragments on purpose — a
# literal `AKIA…` / `sk-ant-…40+` in a tracked file trips diagnostics.py's
# no-committed-secrets scanner. Do not "simplify" these back to one literal.
_REDACTION_PROBES: list[tuple[str, str, str, bool]] = [
    ("bearer_in_attr", "gen_ai.tool.input", "Authorization: Bearer sk_" + "live_abcdefghijklmnop0123456789", True),
    ("dsn_in_attr", "gen_ai.tool.output", "postgres://user:hunter2@db.internal.example.com:5432/prod", True),
    ("anthropic_key_in_attr", "gen_ai.tool.input", "sk-ant-" + "api03-" + "a" * 40, True),
    ("aws_key_in_attr", "gen_ai.tool.output", "AKIA" + "ABCDEFGHIJKLMNOP", True),
    ("span_id_tier_m_control", "span_id", "a1b2c3d4e5f60718", False),
    ("trace_id_tier_m_control", "trace_id", "a1b2c3d4e5f60718293a4b5c6d7e8f90", False),
]


def _load_otlp_exporter_module():
    name = "_ws_d_health_otlp_exporter"
    spec = importlib.util.spec_from_file_location(name, OTLP_EXPORTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so the module's own @dataclass definitions can
    # resolve cls.__module__ via sys.modules (same fix test loaders use).
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def check_redaction_probe() -> dict:
    """Run known secret-shaped span attributes through the exporter's own
    ``redact_span`` (ADR-0012 scrubber path) and assert Tier-B is scrubbed while
    Tier-M ids survive untouched."""
    mod = _load_otlp_exporter_module()
    misses: list[str] = []
    for label, key, value, must_redact in _REDACTION_PROBES:
        span = {"event_type": "span", "span_id": "deadbeefcafef00d", key: value}
        redacted = mod.redact_span(span)
        if redacted is None:
            misses.append(f"{label}: span dropped unexpectedly (scrubber raised)")
            continue
        out_value = redacted.get(key)
        was_redacted = out_value != value and isinstance(out_value, str) and "[REDACTED" in out_value
        if must_redact and not was_redacted:
            misses.append(f"{label}: expected {key!r} redaction, got raw/unredacted output")
        if not must_redact and was_redacted:
            misses.append(f"{label}: Tier-M key {key!r} was over-redacted")
    if misses:
        return {"ok": False, "detail": "; ".join(misses)}
    return {"ok": True, "detail": f"{len(_REDACTION_PROBES)} probe(s) redacted correctly on the exporter path"}


def check_in_tenant_target() -> dict:
    """Confirm the ``langfuse_observability`` endpoint still resolves in-tenant,
    reusing the exporter's own ``assert_in_tenant`` (which itself reuses
    ``scripts/check_in_tenant.py`` verbatim — no parallel boundary logic)."""
    mod = _load_otlp_exporter_module()
    try:
        target = mod.assert_in_tenant(TENANT_BOUNDARY_PATH)
    except mod.BoundaryError as exc:
        return {"ok": False, "detail": str(exc)}
    return {"ok": True, "detail": f"langfuse_observability resolves in-tenant (target: {target})"}


def check_allowlist_drift() -> dict:
    """Recompile the allow-list in-memory and diff against the tracked file;
    assert the eval-tool grants are present and no entry carries a literal '*'."""
    recompiled = gen_subagents.compile_tool_allowlist()
    recompiled_text = json.dumps(recompiled, indent=2, sort_keys=True) + "\n"
    if not TOOL_ALLOWLIST_PATH.exists():
        return {"ok": False, "detail": f"{TOOL_ALLOWLIST_PATH} is missing (expected a compiled artifact)"}
    on_disk_text = TOOL_ALLOWLIST_PATH.read_text(encoding="utf-8")
    if on_disk_text != recompiled_text:
        return {"ok": False, "detail": "board/.tool-allowlist.json diverges from the compiled overlays (drift)"}

    problems: list[str] = []
    eval_entries = {
        key: roles
        for key, roles in recompiled.items()
        if any(key.startswith(prefix) for prefix in _EVAL_TOOL_ROLE_KEYS)
    }
    if not eval_entries:
        problems.append("no promptfoo/AgentShield/Presidio grant found in the compiled overlays")
    for key, roles in recompiled.items():
        if any(str(r).strip() == "*" for r in roles):
            problems.append(f"{key}: compiled grant carries a literal '*' role (must be explicit)")
    if problems:
        return {"ok": False, "detail": "; ".join(problems)}
    return {
        "ok": True,
        "detail": (
            f"{len(recompiled)} tool grant(s) match compiled overlays; "
            f"{len(eval_entries)} eval-tool entr(y/ies) present, no '*' roles"
        ),
    }


def run() -> dict:
    redaction = check_redaction_probe()
    in_tenant = check_in_tenant_target()
    allowlist = check_allowlist_drift()
    healthy = redaction["ok"] and in_tenant["ok"] and allowlist["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "redaction_probe": redaction,
            "in_tenant_target": in_tenant,
            "allowlist_drift": allowlist,
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
        print("WS-D LENS health check (GATE-6 Maintenance, DAS-1577)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
