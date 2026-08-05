#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

FLAG = "ws_e_tenant_hardening"


SIEM_ENDPOINT_ROLE = "audit"
SIEM_ENDPOINT_NAME = "audit_store"


OTEL_LOGS_PATH = "/v1/logs"
_TIER_B_CAP = 280


class BoundaryError(RuntimeError):
    pass


def _load_module(relpath: str, name: str) -> Any:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:
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


def is_enabled(features_path: Path | None = None) -> bool:
    return bool(_rbac_mod().is_enabled(features_path))


def _load_tenant_config(config_path: Path | None = None) -> dict[str, Any]:
    cit = _check_in_tenant_mod()
    path = config_path or cit.DEFAULT_CONFIG
    if cit.yaml is None:
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
    return str(_siem_endpoint(_load_tenant_config(config_path)).get("url", ""))


def resolve_target(config_path: Path | None = None) -> str:
    base = endpoint_url(config_path).rstrip("/")
    if not base:
        raise BoundaryError(f"'{SIEM_ENDPOINT_NAME}' endpoint has no url")

    if "://" in base and base.split("://", 1)[0].lower() in {"file", "stdio", "unix", "sqlite"}:
        return base
    return base + OTEL_LOGS_PATH


def assert_in_tenant(config_path: Path | None = None) -> str:
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


def redact_record(record: dict[str, Any]) -> dict[str, Any] | None:
    tier_m = _rbac_mod().GATE_APPROVAL_TIER_M
    scrub = _redaction_mod().scrub
    out: dict[str, Any] = {}
    try:
        for key, value in record.items():
            if key in tier_m:
                out[key] = value
                continue
            scrubbed = scrub(value if isinstance(value, str) else str(value))
            out[key] = scrubbed[:_TIER_B_CAP]
    except Exception:
        return None
    return out


def derive_trace_id(ticket_id: str) -> str:
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


def http_post_transport(target: str, payload: dict[str, Any]) -> None:
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    urllib.request.urlopen(req, timeout=10)


@dataclass
class ExportResult:

    ran: bool = False
    target: str | None = None
    read: int = 0
    dropped: int = 0
    exported: int = 0
    posted: bool = False
    otlp_records: list[dict[str, Any]] = field(default_factory=list)


def iter_audit_records(audit_path: Path | None = None) -> Iterator[dict[str, Any]]:
    yield from _rbac_mod().iter_gate_approvals(audit_path)


def export_audit(
    *,
    audit_path: Path | None = None,
    config_path: Path | None = None,
    features_path: Path | None = None,
    transport: Callable[[str, dict[str, Any]], None] | None = None,
    post: bool = False,
) -> ExportResult:
    if not is_enabled(features_path):
        return ExportResult(ran=False)

    target = assert_in_tenant(config_path)

    result = ExportResult(ran=True, target=target)
    for record in iter_audit_records(audit_path):
        result.read += 1
        safe = redact_record(record)
        if safe is None:
            result.dropped += 1
            continue
        result.otlp_records.append(map_record_to_otlp(safe))
        result.exported += 1

    if post and result.otlp_records:
        send = transport or http_post_transport
        send(target, build_otlp_payload(result.otlp_records))
        result.posted = True

    return result


if __name__ == "__main__":
    res = export_audit()
    print(
        f"ws_e_tenant_hardening: {'ON' if res.ran else 'OFF (inert)'} — "
        f"read={res.read} exported={res.exported} dropped={res.dropped} target={res.target}"
    )
