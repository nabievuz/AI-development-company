#!/usr/bin/env python3
"""rbac_siem_export.py — WS-E read-only SIEM audit export (TN-4 / FR-002, DAS-1582).

A **read-side, one-way** adapter that ships the append-only RBAC audit trail
(``gate_approval`` records, ``board/.rbac-audit.jsonl``) — and, when present, the
canonical event-store gate/approval records — to the tenant's SIEM as redacted OTel/JSON.
It is the exact posture of the WS-D Langfuse lens (``tools/observability/otlp_exporter.py``)
and reuses the SAME ADR-0012 scrubber and the SAME ``check_in_tenant`` boundary guard — no
fork, no second redactor, no parallel boundary check (design ``docs/design/
ws-e-tenant-hardening.md`` §2.2).

Four guarantees (FR-002 / TN-4):

- **Read-only + one-way.** Data flows exactly one direction: audit ledger -> redaction ->
  SIEM. This module exposes NO write path into ``board/.events.jsonl``, a ticket file, an
  attestation, or the audit ledger it reads. A SIEM outage/divergence changes no
  board/dispatch outcome (the event store stays system-of-record). The export never writes
  back — there is no reachable operation that does (asserted by SC-002).
- **Redaction at the boundary (ADR-0012).** Even though gate_approval records are Tier-M by
  construction (§2.1), every field passes the ADR-0012 §2 scrubber before it leaves the
  process — belt-and-suspenders, reusing ``tools/mcp_bridges/redaction.py`` verbatim. Tier-M
  ids (attestation hash, hex trace id) survive intact; an unclassifiable value drops to
  ``[REDACTED:unclassified]``. No source code and no IP is in the exported shape.
- **In-tenant target.** The SIEM sink is resolved from ``config/tenant_boundary.yaml`` as an
  in-tenant ``role: audit`` endpoint and re-checked with ``check_in_tenant`` VERBATIM; a
  hosted SIEM url fails the boundary and BLOCKS the export before anything is shipped
  (``audit`` is not in ``accepted_external_roles`` — only ``model`` is).
- **Flag OFF by default.** Guarded by ``ws_e_tenant_hardening`` (OFF); with the flag OFF
  :func:`export_audit` is inert (no read, no target resolve, no POST) and returns
  ``ExportResult(ran=False)`` — dispatch byte-identical (FR-008 / SC-005).

Dependency posture: stdlib only for the core; the repo's own ``rbac`` / ``redaction`` /
``check_in_tenant`` helpers are loaded by file path (no package install). The transport is
pluggable; the default POSTs with the stdlib and is never exercised by unit tests (they
pass a capturing transport and default ``post=False``).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Self-locating repo root. scripts/rbac_siem_export.py -> scripts/ -> repo root.
ROOT = Path(__file__).resolve().parent.parent

FLAG = "ws_e_tenant_hardening"

# The tenant-boundary endpoint that owns the SIEM export target (design §2.3 / §4.2). The
# SIEM is declared as an in-tenant `role: audit` sink; `audit` is NOT an accepted external
# role, so a hosted SIEM url fails check_in_tenant and blocks the export.
SIEM_ENDPOINT_ROLE = "audit"
SIEM_ENDPOINT_NAME = "audit_store"

# OTLP-style constants (mirrors tools/observability/otlp_exporter.py).
OTEL_LOGS_PATH = "/v1/logs"
_TIER_B_CAP = 280


class BoundaryError(RuntimeError):
    """Raised when the SIEM target is not in-tenant — fail closed, nothing exported."""


# ---------------------------------------------------------------------------
# Lazy path-based load of the repo's own helpers (reuse verbatim — no fork).
# ---------------------------------------------------------------------------
def _load_module(relpath: str, name: str) -> Any:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {relpath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_rbac: Any = None
_redaction: Any = None
_check_in_tenant: Any = None


def _rbac_mod() -> Any:
    global _rbac
    if _rbac is None:
        _rbac = _load_module("scripts/rbac.py", "rbac_for_siem")
    return _rbac


def _redaction_mod() -> Any:
    global _redaction
    if _redaction is None:
        _redaction = _load_module("tools/mcp_bridges/redaction.py", "rbac_siem_redaction")
    return _redaction


def _check_in_tenant_mod() -> Any:
    global _check_in_tenant
    if _check_in_tenant is None:
        _check_in_tenant = _load_module("scripts/check_in_tenant.py", "rbac_siem_check_in_tenant")
    return _check_in_tenant


# ---------------------------------------------------------------------------
# Feature flag (FR-008).
# ---------------------------------------------------------------------------
def is_enabled(features_path: Path | None = None) -> bool:
    """True iff ``ws_e_tenant_hardening`` is ON. Default OFF ⇒ the exporter is inert."""
    return bool(_rbac_mod().is_enabled(features_path))


# ---------------------------------------------------------------------------
# Target resolution + in-tenant guard (TN-1 reuse) — design §2.3 / §4.
# ---------------------------------------------------------------------------
def _load_tenant_config(config_path: Path | None = None) -> dict[str, Any]:
    cit = _check_in_tenant_mod()
    path = config_path or cit.DEFAULT_CONFIG
    if cit.yaml is None:  # pragma: no cover - yaml is a repo dependency
        raise BoundaryError("pyyaml unavailable — cannot evaluate tenant boundary")
    if not Path(path).is_file():
        raise BoundaryError(f"tenant boundary config not found: {path}")
    data = cit.yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BoundaryError(f"tenant boundary config is not a mapping: {path}")
    return data


def _siem_endpoint(config: dict[str, Any]) -> dict[str, Any]:
    for ep in config.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        if ep.get("name") == SIEM_ENDPOINT_NAME or str(ep.get("role", "")).lower() == SIEM_ENDPOINT_ROLE:
            return ep
    raise BoundaryError(
        f"no '{SIEM_ENDPOINT_NAME}' (role={SIEM_ENDPOINT_ROLE}) endpoint declared in tenant_boundary.yaml"
    )


def endpoint_url(config_path: Path | None = None) -> str:
    """The RAW audit-sink ``url`` — the SAME value the boundary check inspects."""
    return str(_siem_endpoint(_load_tenant_config(config_path)).get("url", ""))


def resolve_target(config_path: Path | None = None) -> str:
    """The full OTLP endpoint the exporter POSTs to — the in-tenant audit sink url +
    ``/v1/logs``. No hosted default and no fallback branch."""
    base = endpoint_url(config_path).rstrip("/")
    if not base:
        raise BoundaryError(f"'{SIEM_ENDPOINT_NAME}' endpoint has no url")
    # A file:// / stdio:// audit sink is a local ledger path, exported to as-is.
    if "://" in base and base.split("://", 1)[0].lower() in {"file", "stdio", "unix", "sqlite"}:
        return base
    return base + OTEL_LOGS_PATH


def assert_in_tenant(config_path: Path | None = None) -> str:
    """Reuse ``check_in_tenant`` VERBATIM: fail closed unless the whole tenant boundary is
    intact AND the audit sink itself is in-tenant. ``audit`` is not in
    ``accepted_external_roles`` (only ``model`` is), so a hosted SIEM url blocks here —
    before any export. Returns the resolved OTLP target on success."""
    cit = _check_in_tenant_mod()
    config = _load_tenant_config(config_path)
    violations = cit.evaluate(config)
    if violations:
        raise BoundaryError(
            "TN-1: tenant boundary not intact — refusing to export:\n  - " + "\n  - ".join(violations)
        )
    raw = endpoint_url(config_path)
    if not cit.is_in_tenant(raw):
        raise BoundaryError(
            f"TN-1: {SIEM_ENDPOINT_NAME} target resolves to an EXTERNAL host: {raw}"
        )
    return resolve_target(config_path)


# ---------------------------------------------------------------------------
# Redaction-on-export (FR-002) — reuse the ADR-0012 scrubber verbatim.
# ---------------------------------------------------------------------------
def redact_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return an export-safe copy of *record*, or ``None`` to DROP it (fail closed).

    Tier-M keys (ids/enums/timestamps) pass as-is so the attestation hash and hex trace id
    are not over-redacted; every other (Tier-B) key is scrubbed with the ADR-0012 §2 scrubber
    and length-capped — **redact -> truncate -> emit**. If the scrubber RAISES on any
    attribute the WHOLE record is dropped (never shipped raw)."""
    tier_m = _rbac_mod().GATE_APPROVAL_TIER_M
    scrub = _redaction_mod().scrub  # the RAISING variant — a crash ⇒ drop the record
    out: dict[str, Any] = {}
    try:
        for key, value in record.items():
            if key in tier_m:
                out[key] = value
                continue
            scrubbed = scrub(value if isinstance(value, str) else str(value))
            out[key] = scrubbed[:_TIER_B_CAP]
    except Exception:  # noqa: BLE001 — a scrubber crash must never ship raw content
        return None
    return out


# ---------------------------------------------------------------------------
# Record -> OTLP/JSON log field-map shim (design §2.2). The stored field names are
# already the controlled attribute names, so this is a mapping shim, not a rename.
# ---------------------------------------------------------------------------
def derive_trace_id(ticket_id: str) -> str:
    """Derive a conformant OTLP 16-byte (32-hex) trace id from the ticket id (stable)."""
    return hashlib.sha256(str(ticket_id).encode("utf-8")).hexdigest()[:32]


def _attr(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        av: dict[str, Any] = {"boolValue": value}
    elif isinstance(value, int):
        av = {"intValue": str(value)}
    elif isinstance(value, float):
        av = {"doubleValue": value}
    else:
        av = {"stringValue": "" if value is None else str(value)}
    return {"key": key, "value": av}


def map_record_to_otlp(record: dict[str, Any]) -> dict[str, Any]:
    """Map a (already-redacted) gate_approval record onto an OTLP log record (OTLP/HTTP
    JSON shape). Every field rides as an attribute; the ticket id derives the trace id."""
    ticket_id = str(record.get("ticket_id", ""))
    attributes = [_attr(k, v) for k, v in record.items()]
    return {
        "timeUnixNano": "0",
        "severityText": "AUDIT",
        "body": {"stringValue": str(record.get("event_type", "gate_approval"))},
        "traceId": derive_trace_id(ticket_id),
        "attributes": attributes,
    }


def build_otlp_payload(otlp_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap OTLP log records in a single OTLP/HTTP ``resourceLogs`` request body."""
    return {
        "resourceLogs": [
            {
                "resource": {"attributes": [_attr("service.name", "daslab")]},
                "scopeLogs": [
                    {
                        "scope": {"name": "daslab.ws-e.rbac-audit"},
                        "logRecords": otlp_records,
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# Transport (pluggable; the stdlib default needs NO third-party dep).
# ---------------------------------------------------------------------------
def http_post_transport(target: str, payload: dict[str, Any]) -> None:  # pragma: no cover - network
    """POST an OTLP/HTTP JSON payload to *target* using only the stdlib."""
    import urllib.request  # noqa: PLC0415

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    urllib.request.urlopen(req, timeout=10)  # noqa: S310 - in-tenant target, guarded


# ---------------------------------------------------------------------------
# The one entry point (FR-002) — read-only, one-way.
# ---------------------------------------------------------------------------
@dataclass
class ExportResult:
    """Outcome of an :func:`export_audit` call — a pure, inspectable value."""

    ran: bool = False           # False ⇒ flag OFF, exporter inert (SC-005)
    target: str | None = None   # the in-tenant OTLP endpoint (None when inert)
    read: int = 0               # audit records read from the ledger
    dropped: int = 0            # records dropped by fail-closed redaction
    exported: int = 0           # records mapped to OTLP
    posted: bool = False        # whether a transport POST was performed
    otlp_records: list[dict[str, Any]] = field(default_factory=list)


def iter_audit_records(audit_path: Path | None = None) -> Iterator[dict[str, Any]]:
    """Read-only iterator over the gate_approval records in the RBAC audit ledger.

    Delegates to ``rbac.iter_gate_approvals`` — this is the ONLY store touch and it is a
    READ (there is no write-back path anywhere in this module)."""
    yield from _rbac_mod().iter_gate_approvals(audit_path)


def export_audit(
    *,
    audit_path: Path | None = None,
    config_path: Path | None = None,
    features_path: Path | None = None,
    transport: Callable[[str, dict[str, Any]], None] | None = None,
    post: bool = False,
) -> ExportResult:
    """Read -> redact -> field-map -> (optionally) POST the RBAC audit trail to the tenant
    SIEM. **Inert when the flag is OFF** (FR-008 / SC-005): no read, no target resolve, no
    POST — returns ``ExportResult(ran=False)``.

    Ordering: [1] in-tenant target check (fail closed, BEFORE any read) -> [2] redact each
    record (fail closed; a dropped record is a missing SIEM row, never a leak) -> [3] OTLP
    field-map -> optional transport. ``post`` defaults to False so tests never touch the
    network. This function has NO write path back into the board/event store/ledger."""
    if not is_enabled(features_path):
        return ExportResult(ran=False)  # inert — dispatch byte-identical (SC-005)

    target = assert_in_tenant(config_path)  # [1] fail closed before any export

    result = ExportResult(ran=True, target=target)
    for record in iter_audit_records(audit_path):
        result.read += 1
        safe = redact_record(record)  # [2] fail closed
        if safe is None:
            result.dropped += 1
            continue
        result.otlp_records.append(map_record_to_otlp(safe))  # [3] field-map
        result.exported += 1

    if post and result.otlp_records:
        send = transport or http_post_transport
        send(target, build_otlp_payload(result.otlp_records))
        result.posted = True

    return result


if __name__ == "__main__":  # pragma: no cover - manual probe
    res = export_audit()
    print(
        f"ws_e_tenant_hardening: {'ON' if res.ran else 'OFF (inert)'} — "
        f"read={res.read} exported={res.exported} dropped={res.dropped} target={res.target}"
    )
