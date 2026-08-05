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

import gen_subagents

TOOL_ALLOWLIST_PATH = ROOT / "board" / ".tool-allowlist.json"
REDACTION_MODULE_PATH = ROOT / "tools" / "mcp_bridges" / "redaction.py"


_REDACTION_PROBES: list[tuple[str, str, bool]] = [
    ("jwt", "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYVsr8sMH9RA", True),
    ("bearer", "Authorization: Bearer sk_" + "live_abcdefghijklmnop0123456789", True),
    ("dsn", "postgres://user:hunter2@db.internal.example.com:5432/prod", True),


    ("anthropic_key", "sk-ant-" + "api03-" + "a" * 40, True),
    ("aws_key", "AKIA" + "ABCDEFGHIJKLMNOP", True),
    ("private_key", "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIBOgIBAAJBAK\n-----END RSA PRIVATE KEY-----", True),
    ("git_sha_tier_m_control", "a1b2c3d4e5f60718293a4b5c6d7e8f9021324354", False),
]


def _load_redaction_module():
    spec = importlib.util.spec_from_file_location("_ws_a_health_redaction", REDACTION_MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_allowlist_drift() -> dict:
    recompiled = gen_subagents.compile_tool_allowlist()
    recompiled_text = json.dumps(recompiled, indent=2, sort_keys=True) + "\n"
    if not TOOL_ALLOWLIST_PATH.exists():
        return {"ok": False, "detail": f"{TOOL_ALLOWLIST_PATH} is missing (expected a compiled artifact)"}
    on_disk_text = TOOL_ALLOWLIST_PATH.read_text(encoding="utf-8")
    if on_disk_text != recompiled_text:
        return {"ok": False, "detail": "board/.tool-allowlist.json diverges from the compiled overlays (drift)"}
    return {"ok": True, "detail": f"{len(recompiled)} tool grant(s), matches compiled overlays"}


def check_redaction_probe() -> dict:
    mod = _load_redaction_module()
    misses: list[str] = []
    for label, sample, must_redact in _REDACTION_PROBES:
        scrubbed = mod.safe_scrub(sample)
        was_redacted = scrubbed != sample and "[REDACTED" in scrubbed
        if must_redact and not was_redacted:
            misses.append(f"{label}: expected redaction, got raw/unredacted output")
        if not must_redact and was_redacted:
            misses.append(f"{label}: Tier-M control value was over-redacted")
    if misses:
        return {"ok": False, "detail": "; ".join(misses)}
    return {"ok": True, "detail": f"{len(_REDACTION_PROBES)} probe(s) redacted correctly"}


def run() -> dict:
    drift = check_allowlist_drift()
    redaction = check_redaction_probe()
    healthy = drift["ok"] and redaction["ok"]
    return {
        "healthy": healthy,
        "checks": {
            "allowlist_drift": drift,
            "redaction_probe": redaction,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ws_a_health_check.py — WS-A tool-edge Maintenance health/eval (GATE-6, DAS-1551).\n\nAADL Stage 6 — Maintenance recurring health/eval for the governed tool edge\n(ADR-0033). Two checks, both READ-ONLY (never mutates the compiled artifact or\nany config):\n\n  1. Allow-list drift  — recompiles ``board/.tool-allowlist.json`` in-memory\n     from the overlay ``## External tools`` grants (the exact SSOT\n     ``scripts/gen_subagents.py`` uses, C1) and diffs it against the tracked\n     file on disk. This is a *targeted* re-check of the same generate-and-diff\n     discipline CI already runs on every push (``ci.yml``: ``gen_subagents.py\n     && git diff --exit-code``) — this script lets the Maintenance cadence\n     (``scripts/stage_gate.py:maintenance_schedule()``) re-verify it on its own\n     schedule, independent of a push happening.\n  2. Redaction probe   — feeds a battery of known secret-shaped strings through\n     ``tools/mcp_bridges/redaction.py``'s ``scrub``/``safe_scrub`` (ADR-0012 §2,\n     C7) and asserts every one comes back redacted, never raw. Also asserts a\n     Tier-M value (git SHA) is NOT over-redacted (the ADR-0012 tuning note).\n\nExit codes: 0 = healthy (no drift, all probes redacted correctly), 1 = a\nfinding (drift and/or a probe miss) — the caller (maintenance cadence) treats\na non-zero exit as an ALERT, never a silent skip. This script never opens a\nticket or files itself; it only reports. Routing a finding into a board ticket\nand into the ``daslab-learn`` Founder-review cadence is a human/orchestrator\nstep documented in ``docs/06-maintenance/ws-a-tool-edge-health.md`` — this\nscript does not self-modify anything (no autonomous write-back), matching\nADR-0029 G5's governed-compounding discipline.\n\nUsage::\n\n    python3 scripts/ws_a_health_check.py [--json]")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("WS-A tool-edge health check (GATE-6 Maintenance, DAS-1551)")
        print("=" * 60)
        for name, check in result["checks"].items():
            status = "OK" if check["ok"] else "ALERT"
            print(f"[{status}] {name}: {check['detail']}")
        print("-" * 60)
        print("HEALTHY" if result["healthy"] else "UNHEALTHY — surface as alert / follow-up ticket, do not ignore")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
