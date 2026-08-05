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
    parser = argparse.ArgumentParser(description='ws_a_health_check.py — WS-A tool-edge Maintenance health/eval (GATE-6, DAS-1551)')
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
