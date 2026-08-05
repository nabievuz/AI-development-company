#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

FLAG = "ws_d_langfuse_lens"


OTEL_TRACE_PATH = "/api/public/otel/v1/traces"


LANGFUSE_ENDPOINT_ROLE = "observability"
LANGFUSE_ENDPOINT_NAME = "langfuse_observability"


_OTLP_STATUS_UNSET = 0
_OTLP_STATUS_OK = 1
_OTLP_STATUS_ERROR = 2


_OTLP_SPAN_KIND_INTERNAL = 1


_TIER_B_CAP = 280


_TIER_M_KEYS = frozenset(
    {
        "event_type",
        "ticket_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "kind",
        "gen_ai.agent.name",
        "gen_ai.request.model",
        "status",
        "run_id",
        "start",
        "end",
        "duration_ms",
        "cached",
        "created_at",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cached_input_tokens",
    }
)


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


_redaction = None
_check_in_tenant = None
_feature_flags = None
_events = None


def _redaction_mod() -> Any:
    global _redaction
    if _redaction is None:
        _redaction = _load_module("tools/mcp_bridges/redaction.py", "ws_d_redaction")
    return _redaction


def _check_in_tenant_mod() -> Any:
    global _check_in_tenant
    if _check_in_tenant is None:
        _check_in_tenant = _load_module("scripts/check_in_tenant.py", "ws_d_check_in_tenant")
    return _check_in_tenant


def _feature_flags_mod() -> Any:
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = _load_module("scripts/feature_flags.py", "ws_d_feature_flags")
    return _feature_flags


def _events_mod() -> Any:
    global _events
    if _events is None:
        _events = _load_module("scripts/dgox/events.py", "ws_d_events")
    return _events


def is_enabled(features_path: Path | None = None) -> bool:
    return bool(_feature_flags_mod().enabled(FLAG, features_path))


class BoundaryError(RuntimeError):
    pass


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


def _langfuse_endpoint(config: dict[str, Any]) -> dict[str, Any]:
    for ep in config.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        if ep.get("name") == LANGFUSE_ENDPOINT_NAME or str(ep.get("role", "")).lower() == LANGFUSE_ENDPOINT_ROLE:
            return ep
    raise BoundaryError(
        f"no '{LANGFUSE_ENDPOINT_NAME}' endpoint declared in tenant_boundary.yaml"
    )


def endpoint_url(config_path: Path | None = None) -> str:
    return str(_langfuse_endpoint(_load_tenant_config(config_path)).get("url", ""))


def resolve_target(config_path: Path | None = None) -> str:
    base = endpoint_url(config_path).rstrip("/")
    if not base:
        raise BoundaryError(f"'{LANGFUSE_ENDPOINT_NAME}' endpoint has no url")
    return base + OTEL_TRACE_PATH


def assert_in_tenant(config_path: Path | None = None) -> str:
    cit = _check_in_tenant_mod()
    config = _load_tenant_config(config_path)

    violations = cit.evaluate(config)
    if violations:
        raise BoundaryError(
            "TN-1: tenant boundary not intact — refusing to export:\n  - "
            + "\n  - ".join(violations)
        )


    raw = endpoint_url(config_path)
    if not cit.is_in_tenant(raw):
        raise BoundaryError(
            f"TN-1: {LANGFUSE_ENDPOINT_NAME} target resolves to an EXTERNAL host: {raw}"
        )
    return resolve_target(config_path)


def redact_span(span: dict[str, Any]) -> dict[str, Any] | None:
    scrub = _redaction_mod().scrub
    out: dict[str, Any] = {}
    try:
        for key, value in span.items():
            if key in _TIER_M_KEYS:
                out[key] = value
                continue

            scrubbed = scrub(value if isinstance(value, str) else str(value))
            out[key] = scrubbed[:_TIER_B_CAP]
    except Exception:
        return None
    return out


def derive_trace_id(ticket_id: str) -> str:
    return hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()[:32]


def derive_span_id(span_id: str) -> str:
    return hashlib.sha256(span_id.encode("utf-8")).hexdigest()[:16]


def _iso_to_unix_nanos(ts: str) -> int:
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000_000)


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


def _status_code(status: str) -> int:
    if status == "ok":
        return _OTLP_STATUS_OK
    if status == "error":
        return _OTLP_STATUS_ERROR
    return _OTLP_STATUS_UNSET


def map_span_to_otlp(span: dict[str, Any]) -> dict[str, Any]:
    ticket_id = str(span.get("trace_id") or span.get("ticket_id") or "")
    parent = span.get("parent_span_id")
    attributes = [
        _attr("gen_ai.operation.name", span.get("kind")),
        _attr("gen_ai.agent.name", span.get("gen_ai.agent.name")),
        _attr("gen_ai.request.model", span.get("gen_ai.request.model")),
        _attr("daslab.span.duration_ms", span.get("duration_ms")),
        _attr("daslab.usage.cached", span.get("cached")),
    ]
    for tok_key in (
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cached_input_tokens",
    ):
        if tok_key in span:
            attributes.append(_attr(tok_key, span.get(tok_key)))

    for key, value in span.items():
        if key in _TIER_M_KEYS:
            continue
        attributes.append(_attr(key, value))

    otlp_span: dict[str, Any] = {
        "traceId": derive_trace_id(ticket_id),
        "spanId": derive_span_id(str(span.get("span_id", ""))),
        "parentSpanId": derive_span_id(str(parent)) if parent else "",
        "name": str(span.get("kind", "")),
        "kind": _OTLP_SPAN_KIND_INTERNAL,
        "startTimeUnixNano": str(_iso_to_unix_nanos(span["start"])),
        "endTimeUnixNano": str(_iso_to_unix_nanos(span["end"])),
        "attributes": attributes,
        "status": {"code": _status_code(str(span.get("status", "")))},
    }
    return otlp_span


def build_otlp_payload(otlp_spans: list[dict[str, Any]], run_id: str | None = None) -> dict[str, Any]:
    resource_attrs = [_attr("service.name", "daslab")]
    if run_id:
        resource_attrs.append(_attr("daslab.run_id", run_id))
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeSpans": [
                    {
                        "scope": {"name": "daslab.ws-d.lens"},
                        "spans": otlp_spans,
                    }
                ],
            }
        ]
    }


def http_post_transport(target: str, payload: dict[str, Any]) -> None:
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
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
    otlp_spans: list[dict[str, Any]] = field(default_factory=list)


def iter_spans(events_path: Path | None = None) -> Iterator[dict[str, Any]]:
    yield from _events_mod().iter_events(events_path, event_type="span")


def export_spans(
    *,
    events_path: Path | None = None,
    config_path: Path | None = None,
    features_path: Path | None = None,
    transport: Callable[[str, dict[str, Any]], None] | None = None,
    post: bool = False,
) -> ExportResult:
    if not is_enabled(features_path):
        return ExportResult(ran=False)


    target = assert_in_tenant(config_path)

    result = ExportResult(ran=True, target=target)
    run_id: str | None = None
    for span in iter_spans(events_path):
        result.read += 1
        if run_id is None:
            run_id = span.get("run_id")

        safe = redact_span(span)
        if safe is None:
            result.dropped += 1
            continue

        result.otlp_spans.append(map_span_to_otlp(safe))
        result.exported += 1

    if post and result.otlp_spans:
        send = transport or http_post_transport
        send(target, build_otlp_payload(result.otlp_spans, run_id=run_id))
        result.posted = True

    return result


if __name__ == "__main__":
    res = export_spans()
    print(
        f"ws_d_langfuse_lens: {'ON' if res.ran else 'OFF (inert)'} — "
        f"read={res.read} exported={res.exported} dropped={res.dropped} "
        f"target={res.target}"
    )
