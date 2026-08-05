#!/usr/bin/env python3

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None


_ENV_ALLOWLIST = "DASLAB_EGRESS_ALLOWLIST"

_ENV_PROFILE = "DASLAB_EGRESS_PROFILE"
_DEFAULT_REL = "config/egress-allowlist.yaml"


def _allowlist_path() -> Path | None:
    env = os.environ.get(_ENV_ALLOWLIST)
    if env:
        return Path(env)

    here = Path.cwd()
    for base in (here, *here.parents):
        candidate = base / _DEFAULT_REL
        if candidate.is_file():
            return candidate
    return None


def load_profiles(path: Path | None = None) -> dict[str, list[str]]:
    p = path or _allowlist_path()
    if p is None or yaml is None:
        return {}
    try:
        data = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, domains in profiles.items():
        if isinstance(domains, list):
            out[str(name)] = [str(d).strip().lower() for d in domains if str(d).strip()]
        else:
            out[str(name)] = []
    return out


def host_matches(host: str, domains: list[str]) -> bool:
    if not host:
        return False
    host = host.strip().lower().rstrip(".")
    for entry in domains:
        if not entry:
            continue
        if entry.startswith("*."):
            base = entry[2:]
            if base and host.endswith("." + base):
                return True
        else:
            if host == entry or host.endswith("." + entry):
                return True
    return False


def _ip_is_internal(ip: str) -> bool:
    try:
        obj = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        obj.is_private
        or obj.is_loopback
        or obj.is_link_local
        or obj.is_reserved
        or obj.is_multicast
        or obj.is_unspecified
    )


def resolve_ips(host: str, resolver=None) -> list[str]:
    resolver = resolver or socket.getaddrinfo
    try:
        infos = resolver(host, None)
    except (OSError, socket.gaierror, Exception):
        return []
    ips: list[str] = []
    for info in infos:
        try:
            ips.append(info[4][0])
        except (IndexError, TypeError):
            continue
    return ips


def check_egress(
    url: str,
    profile_name: str | None,
    profiles: dict[str, list[str]] | None = None,
    resolver=None,
) -> tuple[bool, str]:
    if profiles is None:
        profiles = load_profiles()
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "egress denied — no host in URL"

    domains = profiles.get(profile_name or "", [])
    if not domains:
        return False, f"egress denied — profile {profile_name!r} is empty/absent (deny-all)"

    if not host_matches(host, domains):
        return False, f"egress denied — {host} not in profile {profile_name!r}"


    ips = resolve_ips(host, resolver)
    if not ips:
        return False, f"egress denied — {host} did not resolve (cannot verify target)"
    for ip in ips:
        if _ip_is_internal(ip) and ip not in domains:
            return False, (
                f"egress denied — {host} resolves to internal address {ip} "
                "(loopback/link-local/RFC-1918); not explicitly IP-scoped"
            )
    return True, f"egress allowed — {host} in profile {profile_name!r}"


def active_profile() -> str:
    return os.environ.get(_ENV_PROFILE, "") or ""
