#!/usr/bin/env python3
"""DasLab environment preflight doctor.

Splits checks into REQUIRED and OPTIONAL so a bare clone boots zero-touch:

REQUIRED (must pass — gate the exit code):
  1. Claude Code CLI on PATH (``claude``).
  2. Python >= 3.10.
  3. git on PATH.
  4. Repository root resolves at runtime (LAW A — ``_paths.ROOT``).
  5. ``projects/`` workspace exists (``bootstrap.py`` creates it).

OPTIONAL (memory layer — print WARN, never fail):
  6. ArcRift MCP reachable (.mcp.json names ArcRift and its server file exists).
  7. Ollama running with ``nomic-embed-text``.

Exit **0** when every REQUIRED check passes; OPTIONAL failures degrade the
persistent-memory layer (recall/store become best-effort) but the org still
boots and runs. See ``governance/policies/memory-modes.md``.

Usage::

    python3 scripts/doctor.py          # PASS/WARN/FAIL table
    python3 scripts/doctor.py --json   # machine-readable JSON
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from _paths import ROOT


@dataclass
class CheckResult:
    name: str
    passed: bool
    required: bool = True
    detail: str = ""

    @property
    def status(self) -> str:
        if self.passed:
            return "PASS"
        return "FAIL" if self.required else "WARN"


# --------------------------------------------------------------------------- #
# REQUIRED checks
# --------------------------------------------------------------------------- #

def _in_ci() -> bool:
    """True on a CI runner (GitHub/most CI set CI=true)."""
    return os.environ.get("CI", "").lower() in ("1", "true", "yes")


def check_claude_code() -> CheckResult:
    path = shutil.which("claude")
    # `claude` is required to RUN the org; CI only validates the repo (it never
    # launches a session), so the check is optional there — keeps doctor exit 0 on
    # a bare CI runner that has no Claude Code installed.
    return CheckResult("Claude Code CLI (claude on PATH)", bool(path),
                       required=not _in_ci(), detail=path or "not found on PATH")


def check_python_version() -> CheckResult:
    vi = sys.version_info
    ok = (vi.major, vi.minor) >= (3, 10)
    detail = f"Python {vi.major}.{vi.minor}.{vi.micro}" + ("" if ok else " — need >= 3.10")
    return CheckResult("Python >= 3.10", ok, True, detail)


def check_git() -> CheckResult:
    path = shutil.which("git")
    return CheckResult("git on PATH", bool(path), True, path or "not found on PATH")


def check_repo_root() -> CheckResult:
    markers = [ROOT / "AGENTS.md", ROOT / "board", ROOT / ".claude"]
    ok = ROOT.is_dir() and all(m.exists() for m in markers)
    detail = str(ROOT) if ok else f"{ROOT} (missing AGENTS.md/board/.claude)"
    return CheckResult("Repo root resolves (LAW A)", ok, True, detail)


def check_projects_dir() -> CheckResult:
    projects = ROOT / "projects"
    ok = projects.is_dir()
    return CheckResult("projects/ workspace exists", ok, True,
                       str(projects) if ok else "missing — run scripts/bootstrap.py")


# --------------------------------------------------------------------------- #
# OPTIONAL checks (memory layer)
# --------------------------------------------------------------------------- #

def check_arcrift_mcp() -> CheckResult:
    mcp_json = ROOT / ".mcp.json"
    if not mcp_json.exists():
        return CheckResult("ArcRift MCP reachable", False, False, ".mcp.json not found at repo root")
    try:
        config = json.loads(mcp_json.read_text())
    except json.JSONDecodeError as exc:
        return CheckResult("ArcRift MCP reachable", False, False, f".mcp.json parse error: {exc}")
    arcrift = config.get("mcpServers", {}).get("ArcRift")
    if arcrift is None:
        return CheckResult("ArcRift MCP reachable", False, False, ".mcp.json has no 'ArcRift' server")
    args: list[str] = arcrift.get("args", [])
    if not args:
        return CheckResult("ArcRift MCP reachable", False, False, "ArcRift entry has no args")
    # Expand ${HOME}/${VAR} so the portable path resolves on this machine.
    server_bin = Path(os.path.expandvars(args[0]))
    if server_bin.exists():
        return CheckResult("ArcRift MCP reachable", True, False, str(server_bin))
    return CheckResult("ArcRift MCP reachable", False, False, f"server file not found: {server_bin}")


def check_ollama_nomic() -> CheckResult:
    api = "http://localhost:11434/api/tags"
    try:
        with urllib.request.urlopen(api, timeout=5) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError) as exc:
        return CheckResult("Ollama + nomic-embed-text", False, False, f"Ollama not reachable: {exc}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("Ollama + nomic-embed-text", False, False, f"unexpected error: {exc}")
    models = [m.get("name", "") for m in data.get("models", [])]
    match = next((m for m in models if "nomic-embed-text" in m), None)
    if match:
        return CheckResult("Ollama + nomic-embed-text", True, False, match)
    return CheckResult("Ollama + nomic-embed-text", False, False, f"nomic-embed-text not installed: {models}")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

_COL = 34


def _render_table(results: list[CheckResult]) -> str:
    sep = f"+{'-' * (_COL + 2)}+----------+--------+{'-' * 46}+"
    lines = [sep, f"| {'Check':<{_COL}} | Tier     | Status | {'Detail':<44} |", sep]
    for r in results:
        tier = "REQUIRED" if r.required else "OPTIONAL"
        lines.append(f"| {r.name:<{_COL}} | {tier:<8} | {r.status:<6} | {r.detail[:44]:<44} |")
    lines.append(sep)
    req = [r for r in results if r.required]
    opt = [r for r in results if not r.required]
    req_ok = sum(1 for r in req if r.passed)
    opt_ok = sum(1 for r in opt if r.passed)
    lines.append(f"  REQUIRED {req_ok}/{len(req)} pass · OPTIONAL {opt_ok}/{len(opt)} pass")
    if req_ok == len(req) and opt_ok < len(opt):
        lines.append("  → boots in memory-optional mode (persistent memory degraded; see governance/policies/memory-modes.md)")
    return "\n".join(lines)


def _render_json(results: list[CheckResult]) -> str:
    return json.dumps({
        "checks": [{"name": r.name, "tier": "required" if r.required else "optional",
                    "passed": r.passed, "status": r.status, "detail": r.detail} for r in results],
        "required_passed": all(r.passed for r in results if r.required),
    }, indent=2)


def run_checks() -> list[CheckResult]:
    return [
        check_claude_code(), check_python_version(), check_git(),
        check_repo_root(), check_projects_dir(),
        check_arcrift_mcp(), check_ollama_nomic(),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor.py", description=__doc__.splitlines()[0])
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="emit JSON instead of the table")
    args = parser.parse_args(argv)
    results = run_checks()
    print(_render_json(results) if args.json_output else _render_table(results))
    # Exit code is gated ONLY by REQUIRED checks.
    return 0 if all(r.passed for r in results if r.required) else 1


if __name__ == "__main__":
    sys.exit(main())
