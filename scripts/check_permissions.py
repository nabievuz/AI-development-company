#!/usr/bin/env python3
"""check_permissions.py — least-privilege per agent (R-6 / ADR-006).

Validates agent_invocation events in the DGO-X event store: each agent must run
with a BOUNDED tool allowlist (no wildcard), a no-secrets secrets policy (unless a
gate-approved scoped-creds policy), and an isolated workspace (worktree per
ticket — prevents lateral movement). Inert when there are no agent_invocation events.

Exit codes: 0 = least-privilege OR unmeasured, 1 = over-privileged agent, 2 = usage.

Usage:
    python3 scripts/check_permissions.py [--events board/.events.jsonl]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import wave_kpi
from _paths import ROOT

WILDCARD_TOOLS = {"*", "all", "any", "everything"}
_GLOB_RE = re.compile(r"[*?]")  # family-grant globs: mcp__*, Bash(*), read-*, ...
SAFE_SECRETS_POLICIES = {"no_secrets", "scoped_creds_gate_approved"}


def is_unbounded_tool(tool) -> bool:
    """True if a tool entry grants a wildcard or a whole tool family (not least-privilege)."""
    s = str(tool).strip().lower()
    return s in WILDCARD_TOOLS or _GLOB_RE.search(str(tool)) is not None


def violations(invocations: list[dict]) -> list[str]:
    probs: list[str] = []
    for ev in invocations:
        ref = str(ev.get("ticket_id") or ev.get("run_id") or "?")
        tools = ev.get("allowed_tools")
        if not isinstance(tools, list) or not tools:
            probs.append(f"{ref}: no bounded tool allowlist (least-privilege)")
        elif any(is_unbounded_tool(t) for t in tools):
            probs.append(f"{ref}: tool allowlist grants a wildcard/family (not least-privilege)")
        policy = str(ev.get("secrets_policy", "")).strip().lower()
        if policy not in SAFE_SECRETS_POLICIES:
            probs.append(f"{ref}: secrets_policy {policy!r} is not no_secrets / gate-approved")
        if not ev.get("workspace_id"):
            probs.append(f"{ref}: no isolated workspace_id (worktree isolation)")
    return probs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", type=Path, default=ROOT / "board" / ".events.jsonl")
    args = ap.parse_args(argv)

    invocations = [e for e in wave_kpi.read_events(str(args.events)) if e.get("event_type") == "agent_invocation"]
    if not invocations:
        print("Permissions: unmeasured — no agent_invocation events yet. Gate inert (loop off).")
        return 0

    probs = violations(invocations)
    if probs:
        sys.stderr.write("FAIL: least-privilege (R-6 / ADR-006):\n")
        for p in probs:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"OK: {len(invocations)} agent invocation(s), all least-privilege + isolated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
