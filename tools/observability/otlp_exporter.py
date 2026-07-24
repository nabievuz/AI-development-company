#!/usr/bin/env python3
"""otlp_exporter.py — WS-D LENS read-side OTLP exporter (ADR-0036 / DAS-1573).

A **non-invasive, read-side** adapter that ships the already-emitted ADR-0024
span records (``event_type: "span"`` in ``board/.events.jsonl``) to a
**self-hosted** Langfuse instance as OTLP. It is NEVER wired into
``EventStore.append`` or dispatch — it is a second, downstream *reader* of the
canonical span stream (like any replay/scorer), so with the feature flag OFF it
does not run at all and dispatch/event emission is byte-identical (SC-001).

The four guarantees this module implements (design ``docs/design/ws-d-langfuse-lens.md``):

- **FR-001 / OB-2 — field-map shim + self-host only.** Map the ADR-0024 span
  (already OTel-GenAI-named, ADR-0024 §2) onto an OTLP payload and POST to the
  self-host Langfuse ``/api/public/otel`` trace endpoint, whose target is read
  from ``config/tenant_boundary.yaml``'s ``langfuse_observability`` entry — no
  built-in hosted default and no fallback branch.
- **FR-002 / OB-3 — redaction-on-export.** Every attribute passes the ADR-0012
  M/B/F classification + the EXISTING ``tools/mcp_bridges/redaction.py`` scrubber
  (no fork) **before** it leaves the process. Fail-closed: redact→truncate→emit;
  Tier-F never crosses; if the scrubber raises, the whole span is DROPPED (a
  missing view row is always preferable to a leaked one). Tier-M ids
  (``span_id`` / derived ``trace_id``) are never over-redacted.
- **FR-003 / C2 — event store canonical, lens derived.** The exporter only
  *reads* the canonical stream; it never writes ``board/.events.jsonl``, a ticket
  file, or any routing field. Losing/disabling it changes no dispatch outcome.
- **FR-004 — flag OFF by default.** Guarded by ``ws_d_langfuse_lens`` (OFF); with
  the flag OFF ``export_spans`` is inert (no read, no target resolve, no POST).

Dependency posture: the CORE of this module imports only the stdlib plus the
repo's own ``redaction`` / ``check_in_tenant`` / ``feature_flags`` helpers (loaded
by file path, no package install). The transport is pluggable and the stdlib
``urllib`` default (:func:`http_post_transport`) needs NO third-party dep; the
optional ``opentelemetry-exporter-otlp-proto-http`` (see
``requirements-observability.txt``) is opt-in and never imported here.
"""
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

# Self-locating repo root (LAW A — no hardcoded home path). This file lives at
# ``tools/observability/otlp_exporter.py`` → parents[2] is the repo root.
ROOT = Path(__file__).resolve().parents[2]

FLAG = "ws_d_langfuse_lens"

# Langfuse ingests OTLP on its own trace endpoint (design §1.1 / §1.4).
OTEL_TRACE_PATH = "/api/public/otel/v1/traces"

# The tenant-boundary endpoint entry that owns the exporter target (design §1.4).
LANGFUSE_ENDPOINT_ROLE = "observability"
LANGFUSE_ENDPOINT_NAME = "langfuse_observability"

# OTLP span status codes (opentelemetry.proto.trace.v1 Status.StatusCode).
_OTLP_STATUS_UNSET = 0
_OTLP_STATUS_OK = 1
_OTLP_STATUS_ERROR = 2

# OTLP SpanKind (proto). ADR-0024 spans are internal orchestration/GenAI work.
_OTLP_SPAN_KIND_INTERNAL = 1

# ADR-0012 §2 bounded-free-text cap (matches redaction.redact_then_truncate).
_TIER_B_CAP = 280

# ---------------------------------------------------------------------------
# ADR-0012 M/B/F classification of the ADR-0024 span fields (design §2.1).
# ---------------------------------------------------------------------------
# Tier-M — controlled vocabulary / ids / enums / numerics / ISO timestamps.
# Exported as-is; NEVER scrubbed (so the high-entropy opaque ``span_id`` and the
# derived hex ``trace_id`` are not over-redacted — design §2.2 / ADR-0012 {32,}).
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
# Every other key an emitter might attach to a span is Tier-B (bounded free text)
# and is §2-scrubbed + length-capped before export; a Tier-F-shaped value that a
# future emitter attaches is caught by the same scrub (deny-by-default).


# ---------------------------------------------------------------------------
# Lazy, path-based loading of the repo's own helpers (no package install, no
# fork). We REUSE tools/mcp_bridges/redaction.py and scripts/check_in_tenant.py
# verbatim rather than reimplementing them (design §2.2 / §4.1).
# ---------------------------------------------------------------------------
def _load_module(relpath: str, name: str) -> Any:
    """Import a repo module by file path, with ``scripts/`` importable.

    ``check_in_tenant`` does ``from _paths import ROOT``; adding ``scripts/`` to
    ``sys.path`` lets that intra-repo import resolve without installing anything.
    """
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {relpath}")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so any @dataclass introspection (cls.__module__) resolves.
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


# ---------------------------------------------------------------------------
# Feature flag (FR-004).
# ---------------------------------------------------------------------------
def is_enabled(features_path: Path | None = None) -> bool:
    """True iff ``ws_d_langfuse_lens`` is ON. Default OFF ⇒ the exporter is inert."""
    return bool(_feature_flags_mod().enabled(FLAG, features_path))


# ---------------------------------------------------------------------------
# Target resolution + in-tenant guard (FR-001 / SC-004 / TN-1) — design §1.4 / §4.
# ---------------------------------------------------------------------------
class BoundaryError(RuntimeError):
    """Raised when the exporter target is not in-tenant — fail closed, no export."""


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
    """The RAW ``langfuse_observability.url`` — the SAME value the boundary check
    inspects (design §1.4: the checked value and the exported-to value are one)."""
    return str(_langfuse_endpoint(_load_tenant_config(config_path)).get("url", ""))


def resolve_target(config_path: Path | None = None) -> str:
    """The full OTLP trace endpoint the exporter POSTs to — the self-host Langfuse
    ``langfuse_observability.url`` + ``/api/public/otel/...``. No hosted default."""
    base = endpoint_url(config_path).rstrip("/")
    if not base:
        raise BoundaryError(f"'{LANGFUSE_ENDPOINT_NAME}' endpoint has no url")
    return base + OTEL_TRACE_PATH


def assert_in_tenant(config_path: Path | None = None) -> str:
    """Reuse ``check_in_tenant`` VERBATIM (design §4.1): fail closed unless the
    tenant boundary is intact AND the langfuse endpoint itself is in-tenant.

    ``observability`` is NOT in ``accepted_external_roles`` (only ``model`` is), so
    a hosted Langfuse/LangSmith url makes ``evaluate()`` return a violation and this
    blocks — before any export. Returns the resolved OTLP target on success.
    """
    cit = _check_in_tenant_mod()
    config = _load_tenant_config(config_path)
    # Full-boundary guard, reused verbatim (no second/parallel boundary check).
    violations = cit.evaluate(config)
    if violations:
        raise BoundaryError(
            "TN-1: tenant boundary not intact — refusing to export:\n  - "
            + "\n  - ".join(violations)
        )
    # Belt: the exporter's own target must itself resolve in-tenant. This reads the
    # SAME endpoint entry resolve_target() exports to, so the check cannot be dodged.
    raw = endpoint_url(config_path)
    if not cit.is_in_tenant(raw):
        raise BoundaryError(
            f"TN-1: {LANGFUSE_ENDPOINT_NAME} target resolves to an EXTERNAL host: {raw}"
        )
    return resolve_target(config_path)


# ---------------------------------------------------------------------------
# Redaction-on-export (FR-002 / OB-3) — design §2. Reuse the ADR-0012 scrubber.
# ---------------------------------------------------------------------------
def redact_span(span: dict[str, Any]) -> dict[str, Any] | None:
    """Return an export-safe copy of *span*, or ``None`` to DROP it (fail closed).

    - Tier-M keys (ids/enums/numerics/timestamps) are passed as-is — the opaque
      ``span_id`` and derived hex ``trace_id`` must survive intact (no over-redaction).
    - Every other (Tier-B) key is scrubbed with the ADR-0012 §2 scrubber and then
      length-capped — **redact → truncate → emit**, so a secret split by the cap
      cannot survive; a Tier-F-shaped value is caught by the same scrub.
    - If the scrubber RAISES on any attribute, the WHOLE span is dropped (return
      ``None``) — never shipped raw (design §2.2).
    """
    scrub = _redaction_mod().scrub  # the RAISING variant — a crash ⇒ drop the span
    out: dict[str, Any] = {}
    try:
        for key, value in span.items():
            if key in _TIER_M_KEYS:
                out[key] = value
                continue
            # Tier-B: redact THEN truncate (ADR-0012 §2 ordering).
            scrubbed = scrub(value if isinstance(value, str) else str(value))
            out[key] = scrubbed[:_TIER_B_CAP]
    except Exception:  # noqa: BLE001 — scrubber crash must never ship raw content
        return None
    return out


# ---------------------------------------------------------------------------
# ADR-0024 span → OTLP field-map shim (FR-001) — design §1.2.
# ---------------------------------------------------------------------------
def derive_trace_id(ticket_id: str) -> str:
    """Derive a conformant OTLP 16-byte (32-hex) trace id from the ticket id.

    Pure function of the ticket id (ADR-0024 §1 reserves this) — stable across runs.
    """
    return hashlib.sha256(ticket_id.encode("utf-8")).hexdigest()[:32]


def derive_span_id(span_id: str) -> str:
    """Derive a conformant OTLP 8-byte (16-hex) span id from the opaque span id."""
    return hashlib.sha256(span_id.encode("utf-8")).hexdigest()[:16]


def _iso_to_unix_nanos(ts: str) -> int:
    """Convert a caller-supplied ISO-8601 ``Z`` timestamp to unix nanoseconds."""
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000_000)


def _attr(key: str, value: Any) -> dict[str, Any]:
    """One OTLP KeyValue attribute, typed by the Python value."""
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
    """Map a (already-redacted) ADR-0024 span record onto an OTLP span object
    (OTLP/HTTP JSON shape). Mirrors the ADR-0024 §2 table (design §1.2).

    The persisted field names already ARE the OTel GenAI attribute names, so this
    is a mapping shim over correctly-named data, not a rename.
    """
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
    # Any surviving Tier-B free-text attribute rides along verbatim (already scrubbed).
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
    """Wrap OTLP spans in a single OTLP/HTTP ``resourceSpans`` request body."""
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


# ---------------------------------------------------------------------------
# Transport (pluggable; the stdlib default needs NO third-party dep).
# ---------------------------------------------------------------------------
def http_post_transport(target: str, payload: dict[str, Any]) -> None:  # pragma: no cover - network
    """POST an OTLP/HTTP JSON payload to *target* using only the stdlib.

    Kept out of the hot path of the unit tests (they pass a capturing transport).
    A view outage here is by design non-fatal to dispatch (FR-003): the caller
    isolates failures.
    """
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10)  # noqa: S310 - in-tenant target, guarded


# ---------------------------------------------------------------------------
# The one entry point (FR-001..FR-004) — design §0 / §1.3.
# ---------------------------------------------------------------------------
@dataclass
class ExportResult:
    """Outcome of an :func:`export_spans` call — a pure, inspectable value."""

    ran: bool = False           # False ⇒ flag OFF, exporter was inert (SC-001)
    target: str | None = None   # the in-tenant OTLP endpoint (None when inert)
    read: int = 0               # span records read from the stream
    dropped: int = 0            # spans dropped by fail-closed redaction
    exported: int = 0           # spans mapped to OTLP and handed to the transport
    posted: bool = False        # whether a transport POST was performed
    otlp_spans: list[dict[str, Any]] = field(default_factory=list)


def iter_spans(events_path: Path | None = None) -> Iterator[dict[str, Any]]:
    """Read-only iterator over the ``span`` records in the canonical event store.

    Reuses ``scripts/dgox/events.iter_events`` — this is the ONLY store touch and
    it is a read (FR-003: no write-back path).
    """
    yield from _events_mod().iter_events(events_path, event_type="span")


def export_spans(
    *,
    events_path: Path | None = None,
    config_path: Path | None = None,
    features_path: Path | None = None,
    transport: Callable[[str, dict[str, Any]], None] | None = None,
    post: bool = False,
) -> ExportResult:
    """Redact → field-map → (optionally) POST the ADR-0024 span stream to self-host
    Langfuse. **Inert when the flag is OFF** (FR-004 / SC-001): no read, no target
    resolve, no POST — returns ``ExportResult(ran=False)``.

    Ordering (design §0): [1] redact (FR-002) → [2] OTLP field-map (FR-001) →
    [3] in-tenant target check (SC-004) → transport. The in-tenant check runs
    BEFORE any POST; a hosted target raises :class:`BoundaryError` and nothing is
    shipped. ``post`` defaults to False so callers/tests never touch the network
    unless they explicitly opt in and supply/accept a transport.
    """
    if not is_enabled(features_path):
        return ExportResult(ran=False)  # inert — dispatch byte-identical (SC-001)

    # [3] In-tenant target check BEFORE any export (fail closed; design §4).
    target = assert_in_tenant(config_path)

    result = ExportResult(ran=True, target=target)
    run_id: str | None = None
    for span in iter_spans(events_path):
        result.read += 1
        if run_id is None:
            run_id = span.get("run_id")
        # [1] redact (fail closed) — a dropped span is a missing view row, never a leak.
        safe = redact_span(span)
        if safe is None:
            result.dropped += 1
            continue
        # [2] field-map shim.
        result.otlp_spans.append(map_span_to_otlp(safe))
        result.exported += 1

    if post and result.otlp_spans:
        send = transport or http_post_transport
        send(target, build_otlp_payload(result.otlp_spans, run_id=run_id))
        result.posted = True

    return result


if __name__ == "__main__":  # pragma: no cover - manual probe
    res = export_spans()
    print(
        f"ws_d_langfuse_lens: {'ON' if res.ran else 'OFF (inert)'} — "
        f"read={res.read} exported={res.exported} dropped={res.dropped} "
        f"target={res.target}"
    )
