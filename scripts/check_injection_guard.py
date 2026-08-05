#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT
from check_permissions import is_unbounded_tool

RAW_STATE_KEYS = {"raw_full_state", "full_org_state", "all_state", "raw_org_state"}
DATA_POLICIES = {"data", "data_only", "information"}


def violations(invocations: list[dict]) -> list[str]:
    probs: list[str] = []
    for ev in invocations:
        ref = str(ev.get("ticket_id") or ev.get("run_id") or "?")
        cc = ev.get("context_contract")
        if not isinstance(cc, dict):
            probs.append(f"{ref}: missing context_contract (minimal task context required)")
        else:
            if any(cc.get(k) for k in RAW_STATE_KEYS):
                probs.append(f"{ref}: context_contract exposes raw/full org state (injection surface)")
            policy = str(cc.get("external_content_policy", "data")).strip().lower()
            if policy not in DATA_POLICIES:
                probs.append(
                    f"{ref}: external_content_policy {policy!r} must treat external content as data, not command"
                )
        tools = ev.get("allowed_tools")
        if not isinstance(tools, list) or not tools:
            probs.append(f"{ref}: no tool-call allowlist (external content could trigger arbitrary tools)")
        elif any(is_unbounded_tool(t) for t in tools):
            probs.append(f"{ref}: tool allowlist grants a wildcard/family (external content could trigger a tool family)")
    return probs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_injection_guard.py — prompt-injection guard (R-6 / ADR-006).')
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    args = ap.parse_args(argv)

    invocations = [e for e in wave_kpi.read_events(str(args.events)) if e.get("event_type") == "agent_invocation"]
    if not invocations:
        print("Injection guard: unmeasured — no agent_invocation events yet. Gate inert (loop off).")
        return 0

    probs = violations(invocations)
    if probs:
        sys.stderr.write("FAIL: prompt-injection guard (R-6 / ADR-006):\n")
        for p in probs:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: {len(invocations)} agent invocation(s), external content treated as data + tool-allowlisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
