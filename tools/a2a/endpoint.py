from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = ROOT / "config" / "features.yaml"
DEFAULT_EVENTS_PATH = ROOT / "board" / ".events.jsonl"


FEATURE_FLAG = "a2a_outbound"


ENDPOINT_ROLE = "a2a"


DEFAULT_BIND = "http://127.0.0.1:8765"


FORBIDDEN_FIELDS = frozenset(
    {
        "approval",
        "stage",
        "status",
        "assignee",
        "gate",
        "gate_status",
        "ticket_type",
        "dispatch_order",
        "reviewer",
        "routing",
    }
)


REQUIRED_PROPOSAL_FIELDS = frozenset({"title", "summary"})


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


_check_in_tenant: Any = None
_ws_b_admission: Any = None
_redaction: Any = None


def _check_in_tenant_mod() -> Any:
    global _check_in_tenant
    if _check_in_tenant is None:
        _check_in_tenant = _load_module("scripts/check_in_tenant.py", "a2a_check_in_tenant")
    return _check_in_tenant


def _ws_b_admission_mod() -> Any:
    global _ws_b_admission
    if _ws_b_admission is None:
        _ws_b_admission = _load_module("scripts/ws_b_admission.py", "a2a_ws_b_admission")
    return _ws_b_admission


def _redaction_mod() -> Any:
    global _redaction
    if _redaction is None:
        _redaction = _load_module("tools/mcp_bridges/redaction.py", "a2a_redaction")
    return _redaction


def is_enabled(features_path: Path | None = None) -> bool:
    path = Path(features_path) if features_path is not None else FEATURES_PATH
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{FEATURE_FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


def endpoint_bind_in_tenant(bind_url: str) -> bool:
    return bool(_check_in_tenant_mod().is_in_tenant(bind_url))


class CallOutcome(StrEnum):
    ADMITTED = "admitted"
    UNAVAILABLE = "unavailable"
    REJECTED_TENANT = "rejected_tenant"
    REJECTED_ADMISSION = "rejected_admission"
    REFUSED_FORBIDDEN_FIELD = "refused_forbidden_field"
    REFUSED_MALFORMED = "refused_malformed"


@dataclass(frozen=True)
class CallResult:

    outcome: CallOutcome
    reason: str
    admission: Any | None = None
    forwarded: Any | None = None

    @property
    def admitted(self) -> bool:
        return self.outcome is CallOutcome.ADMITTED


def _utcnow() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_event(record: dict[str, Any], path: Path | None = None) -> None:
    p = Path(path) if path is not None else DEFAULT_EVENTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(p, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            import fcntl

            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError, NameError):
                import fcntl

                fcntl.flock(fh, fcntl.LOCK_UN)


def _forbidden_fields_present(payload: dict[str, Any]) -> list[str]:
    return sorted({str(k) for k in payload if str(k).strip().lower() in FORBIDDEN_FIELDS})


def _validate_proposal_shape(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload is not a mapping"]
    errors = []
    for field in REQUIRED_PROPOSAL_FIELDS:
        v = payload.get(field)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"missing/empty required field: {field!r}")
    return errors


def _redact_payload(payload: dict[str, Any]) -> dict[str, str]:
    scrub = _redaction_mod().safe_scrub
    return {str(k): scrub(v) for k, v in payload.items()}


def handle_call(
    payload: dict[str, Any],
    *,
    principal: str,
    model: str = "a2a-caller",
    bind_url: str = DEFAULT_BIND,
    flag_enabled: bool | None = None,
    intake_handler: Callable[[dict[str, Any], str], Any] | None = None,
    events_path: Path | None = None,
    features_path: Path | None = None,
    created_at: str | None = None,
) -> CallResult:
    ts = created_at or _utcnow()
    enabled = is_enabled(features_path) if flag_enabled is None else flag_enabled
    if not enabled:
        return CallResult(
            outcome=CallOutcome.UNAVAILABLE,
            reason=(
                f"`{FEATURE_FLAG}` flag is OFF (default) — the endpoint does not "
                "exist; no call reaches it, no event is emitted (SC-005)"
            ),
        )

    if not endpoint_bind_in_tenant(bind_url):
        result = CallResult(
            outcome=CallOutcome.REJECTED_TENANT,
            reason=(
                f"TN-1 BLOCK: endpoint bind {bind_url!r} is not in-tenant — a "
                "hosted relay/registry is refused (config/tenant_boundary.yaml, "
                "scripts/check_in_tenant.is_in_tenant reused verbatim)"
            ),
        )
        _append_event(
            {
                "event_type": "a2a_call",
                "ts": ts,
                "principal_id": str(principal),
                "decision": "deny",
                "outcome": result.outcome.value,
                "reason": result.reason,
            },
            events_path,
        )
        return result

    forbidden = _forbidden_fields_present(payload) if isinstance(payload, dict) else ["<non-mapping payload>"]
    if forbidden:
        result = CallResult(
            outcome=CallOutcome.REFUSED_FORBIDDEN_FIELD,
            reason=(
                f"REFUSED: payload carries forbidden control field(s) {forbidden} — "
                "a goal-proposal object has no place for a governance write (§1.1); "
                "the field is refused, never silently stripped-and-accepted"
            ),
        )
        _append_event(
            {
                "event_type": "a2a_call",
                "ts": ts,
                "principal_id": str(principal),
                "decision": "deny",
                "outcome": result.outcome.value,
                "reason": result.reason,
                "forbidden_fields": forbidden,
            },
            events_path,
        )
        return result

    shape_errors = _validate_proposal_shape(payload)
    if shape_errors:
        result = CallResult(
            outcome=CallOutcome.REFUSED_MALFORMED,
            reason=f"REFUSED: malformed proposal — {'; '.join(shape_errors)}",
        )
        _append_event(
            {
                "event_type": "a2a_call",
                "ts": ts,
                "principal_id": str(principal),
                "decision": "deny",
                "outcome": result.outcome.value,
                "reason": result.reason,
            },
            events_path,
        )
        return result

    admit = _ws_b_admission_mod().admit
    admission = admit(ticket_id="DAS-1610", role=ENDPOINT_ROLE, model=model)
    if not admission.admitted:
        result = CallResult(
            outcome=CallOutcome.REJECTED_ADMISSION,
            reason=f"ADR-0009 admission denied: {admission.reason}",
            admission=admission,
        )
        _append_event(
            {
                "event_type": "a2a_call",
                "ts": ts,
                "principal_id": str(principal),
                "decision": "deny",
                "outcome": result.outcome.value,
                "reason": result.reason,
            },
            events_path,
        )
        return result

    redacted = _redact_payload(payload)
    _append_event(
        {
            "event_type": "a2a_call",
            "ts": ts,
            "principal_id": str(principal),
            "decision": "allow",
            "outcome": CallOutcome.ADMITTED.value,
            "reason": "admitted: in-tenant, no forbidden field, ADR-0009 admission ok",
            "redacted_payload": redacted,
        },
        events_path,
    )


    forwarded = intake_handler(redacted, str(principal)) if intake_handler is not None else None
    return CallResult(
        outcome=CallOutcome.ADMITTED,
        reason="admitted, redacted, and audited",
        admission=admission,
        forwarded=forwarded,
    )
