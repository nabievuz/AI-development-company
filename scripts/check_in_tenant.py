#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path
from urllib.parse import urlsplit

from _paths import ROOT

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG = ROOT / "config" / "tenant_boundary.yaml"


_LOCAL_SCHEMES = {"file", "stdio", "unix", "sqlite"}

_LOCAL_NAMES = {"localhost"}
_LOCAL_SUFFIXES = (".local", ".internal", ".lan", ".localdomain")


def _host_of(url: str) -> tuple[str, str]:
    parts = urlsplit(url if "://" in url else f"//{url}")
    return parts.scheme.lower(), (parts.hostname or "").lower()


def is_in_tenant(url: str) -> bool:
    scheme, host = _host_of(url)
    if scheme in _LOCAL_SCHEMES:
        return True
    if not host:

        return True
    if host in _LOCAL_NAMES or host.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:


        return "." not in host
    return ip.is_loopback or ip.is_private or ip.is_link_local


def evaluate(config: dict) -> list[str]:
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
            continue
        if not is_in_tenant(url):
            violations.append(
                f"{name} (role={role or '?'}) resolves to an EXTERNAL host: {url}"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='check_in_tenant.py — TN-1 in-tenant boundary precondition guard (DAS-1543).')
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
