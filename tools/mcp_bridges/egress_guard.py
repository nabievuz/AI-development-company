#!/usr/bin/env python3
"""Egress enforcement for the WS-A tool bridge — DasLab (ADR-0033 TB-4, C4/C5/C6).

Deny-all outbound network access except an explicit domain allow-list
(Founder answer Q5). A request reaches a host only if BOTH hold:

  * **C6 — label-boundary domain match.** The host equals an allow-list base or
    is a dotted sub-domain of it (``host == base or host.endswith("." + base)``),
    never a bare substring/suffix. A ``*.base`` wildcard entry matches sub-domains
    only, not the apex and not a look-alike suffix (``evilbase`` is denied).
  * **C5 — resolved-IP SSRF block.** The host is RESOLVED and every resulting IP
    is checked; a request that resolves to loopback, link-local
    (169.254.0.0/16, incl. cloud-metadata 169.254.169.254), or an RFC-1918 /
    otherwise-internal range is DENIED unless the invoking profile narrowly and
    explicitly scopes that exact host/IP. The URL host STRING alone is never
    trusted — a DNS-rebinding ``ok.example`` that resolves to 169.254.169.254 is
    blocked.

Deny-by-default: an absent or empty profile denies every host. This module owns
the check; the sidecar (``langchain_tool_bridge.web_fetch``) calls it before any
network syscall, and additionally DISABLES redirect-following (C4) so a
302-to-internal cannot bypass this gate.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover — yaml is a repo dependency
    yaml = None

# Env override for the tracked allow-list file (ADR-0003 no hardcoded paths).
_ENV_ALLOWLIST = "DASLAB_EGRESS_ALLOWLIST"
# The role's active egress profile, set when the sidecar is launched for a role.
_ENV_PROFILE = "DASLAB_EGRESS_PROFILE"
_DEFAULT_REL = "config/egress-allowlist.yaml"


def _allowlist_path() -> Path | None:
    env = os.environ.get(_ENV_ALLOWLIST)
    if env:
        return Path(env)
    # Walk up from cwd to find the tracked config; None if not found.
    here = Path.cwd()
    for base in (here, *here.parents):
        candidate = base / _DEFAULT_REL
        if candidate.is_file():
            return candidate
    return None


def load_profiles(path: Path | None = None) -> dict[str, list[str]]:
    """Return ``{profile_name: [domain, ...]}`` from the tracked allow-list.

    Deny-by-default: a missing file, unreadable file, or malformed shape returns
    ``{}`` (which denies every host for every profile). Never raises.
    """
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
    """C6 — label-boundary host match against an allow-list of domains.

    Plain entry ``example.org`` matches ``example.org`` and any ``*.example.org``
    sub-domain. A ``*.example.org`` entry matches sub-domains ONLY (not the apex).
    Never a bare substring/suffix: ``evilexample.org`` never matches ``example.org``.
    """
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
    """True for loopback / link-local / private / reserved / multicast / unspecified."""
    try:
        obj = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable → treat as unsafe (fail-closed)
    return (
        obj.is_private
        or obj.is_loopback
        or obj.is_link_local
        or obj.is_reserved
        or obj.is_multicast
        or obj.is_unspecified
    )


def resolve_ips(host: str, resolver=None) -> list[str]:
    """Resolve *host* to a list of IP strings. ``[]`` on any failure (fail-closed)."""
    resolver = resolver or socket.getaddrinfo
    try:
        infos = resolver(host, None)
    except (OSError, socket.gaierror, Exception):  # noqa: BLE001 — any resolver error = deny
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
    """Deny-all-except-allow-list egress decision. Returns ``(allowed, reason)``.

    Order: parse host → C6 label-boundary match against the profile → C5 resolve
    and block internal IPs unless the profile explicitly scopes the exact host.
    Any missing piece denies (deny-by-default).
    """
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

    # C5 — never trust the host string alone; resolve and inspect every IP. An
    # internal IP is blocked UNLESS the profile lists that exact IP literal (a
    # narrow, explicit scope). A plain domain-name entry NEVER waives the block —
    # otherwise every allow-listed host would silently defeat SSRF protection.
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
