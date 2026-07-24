#!/usr/bin/env python3
"""check_in_tenant.py — TN-1 in-tenant boundary precondition guard (DAS-1543).

MUSTAQIL is an internal self-host program (discovery Q10, ADR-0038). Every endpoint
that carries code or IP — sandbox, observability, audit, memory, embeddings — MUST
resolve to an in-tenant host. The ONE accepted proprietary exception is the Claude
model call (discovery Q9): on a Claude subscription the model call goes to Anthropic.

This guard reads ``config/tenant_boundary.yaml`` and FAILS a run if any endpoint
whose ``role`` carries code/IP resolves to a hosted/external service and is not
listed in ``accepted_external_roles``. It PASSES when every such endpoint is
in-tenant (the model call excepted).

"In-tenant" host = loopback, an RFC-1918 / ULA private address, a ``.local`` /
``.internal`` / bare-hostname name, or a unix-socket / file / stdio path. A public
hostname or public IP is EXTERNAL.

Exit codes: 0 = boundary intact (or config absent = inert), 1 = an external
code/IP endpoint outside the accepted exception, 2 = usage / IO error.

Usage:
    python3 scripts/check_in_tenant.py [--config config/tenant_boundary.yaml]
"""
from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path
from urllib.parse import urlsplit

from _paths import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a repo dependency
    yaml = None

DEFAULT_CONFIG = ROOT / "config" / "tenant_boundary.yaml"

# Schemes that never leave the machine (no network host at all).
_LOCAL_SCHEMES = {"file", "stdio", "unix", "sqlite"}
# Hostname suffixes / names that denote an in-tenant name.
_LOCAL_NAMES = {"localhost"}
_LOCAL_SUFFIXES = (".local", ".internal", ".lan", ".localdomain")


def _host_of(url: str) -> tuple[str, str]:
    """Return (scheme, host) for a declared endpoint URL."""
    parts = urlsplit(url if "://" in url else f"//{url}")
    return parts.scheme.lower(), (parts.hostname or "").lower()


def is_in_tenant(url: str) -> bool:
    """True if the endpoint URL resolves to an in-tenant target."""
    scheme, host = _host_of(url)
    if scheme in _LOCAL_SCHEMES:
        return True
    if not host:
        # No network host (e.g. a bare path) — treated as local.
        return True
    if host in _LOCAL_NAMES or host.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A dotted public name (has a dot and is not a *.local suffix) is external;
        # a bare single-label hostname is an in-tenant machine name.
        return "." not in host
    return ip.is_loopback or ip.is_private or ip.is_link_local


def evaluate(config: dict) -> list[str]:
    """Return a list of boundary-violation messages (empty = boundary intact)."""
    accepted = {str(r).lower() for r in (config.get("accepted_external_roles") or [])}
    violations: list[str] = []
    for ep in config.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        if not ep.get("carries_code_ip"):
            continue
        role = str(ep.get("role", "")).lower()
        url = str(ep.get("url", ""))
        name = ep.get("name", url or "<unnamed>")
        if role in accepted:
            continue  # accepted proprietary exception (e.g. the model call)
        if not is_in_tenant(url):
            violations.append(
                f"{name} (role={role or '?'}) resolves to an EXTERNAL host: {url}"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = ap.parse_args(argv)

    if not args.config.is_file():
        print(f"TN-1: no {args.config.name} — boundary check inert (nothing declared).")
        return 0
    if yaml is None:
        sys.stderr.write("TN-1: pyyaml unavailable — cannot evaluate boundary.\n")
        return 2

    try:
        data = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        sys.stderr.write(f"TN-1: cannot read {args.config}: {exc}\n")
        return 2
    if not isinstance(data, dict):
        sys.stderr.write(f"TN-1: {args.config} is not a mapping.\n")
        return 2

    violations = evaluate(data)
    if violations:
        sys.stderr.write(
            "TN-1 FAIL: code/IP endpoint(s) resolve outside the tenant "
            "(only the Claude model call is an accepted external exception):\n"
        )
        for v in violations:
            sys.stderr.write(f"  - {v}\n")
        return 1

    n = sum(1 for e in (data.get("endpoints") or []) if isinstance(e, dict))
    print(f"TN-1 OK: all code/IP endpoints in-tenant ({n} declared; model call excepted).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
