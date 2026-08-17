from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = ROOT / "config" / "features.yaml"
DEFAULT_EVENTS_PATH = ROOT / "board" / ".events.jsonl"
DEFAULT_QUOTA_PATH = ROOT / "board" / ".a2a-quota.json"


FEATURE_FLAG = "a2a_outbound"


ENDPOINT_ROLE = "a2a"


DEFAULT_BIND = "http://127.0.0.1:8765"


QUOTA_STATE_FILENAME = ".a2a-quota.json"


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
_untrusted: Any = None
_credentials: Any = None
_quota: Any = None


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


def _untrusted_mod() -> Any:
    global _untrusted
    if _untrusted is None:
        _untrusted = _load_module("tools/mcp_bridges/untrusted_input.py", "a2a_untrusted_input")
    return _untrusted


def _credentials_mod() -> Any:
    global _credentials
    if _credentials is None:
        _credentials = _load_module("tools/a2a/credentials.py", "a2a_credentials")
    return _credentials


def _quota_mod() -> Any:
    global _quota
    if _quota is None:
        _quota = _load_module("tools/a2a/quota.py", "a2a_quota")
    return _quota


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
    REFUSED_UNAUTHENTICATED = "refused_unauthenticated"
    REFUSED_PAYLOAD_LIMIT = "refused_payload_limit"
    REFUSED_INJECTION = "refused_injection"
    REFUSED_QUOTA = "refused_quota"


@dataclass(frozen=True)
class CallResult:

    outcome: CallOutcome
    reason: str
    admission: Any | None = None
    forwarded: Any | None = None
    identity: Any | None = None
    screening: Any | None = None

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


def _forbidden_fields_present(payload: Any) -> list[str]:
    found: set[str] = set()
    pending: list[tuple[Any, str]] = [(payload, "")]
    while pending:
        node, path = pending.pop()
        if isinstance(node, Mapping):
            for key, value in node.items():
                key_text = str(key)
                child = f"{path}.{key_text}" if path else key_text
                if key_text.strip().lower() in FORBIDDEN_FIELDS:
                    found.add(child)
                pending.append((value, child))
        elif isinstance(node, str | bytes | bytearray):
            continue
        elif isinstance(node, Sequence):
            for index, value in enumerate(node):
                pending.append((value, f"{path}[{index}]"))
    return sorted(found)


def _validate_proposal_shape(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload is not a mapping"]
    errors = []
    for field in REQUIRED_PROPOSAL_FIELDS:
        v = payload.get(field)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"missing/empty required field: {field!r}")
    return errors


def _redact_node(node: Any, scrub: Callable[[Any], str]) -> Any:
    if isinstance(node, Mapping):
        return {str(key): _redact_node(value, scrub) for key, value in node.items()}
    if isinstance(node, str | bytes | bytearray):
        return scrub(node)
    if isinstance(node, Sequence):
        return [_redact_node(value, scrub) for value in node]
    return scrub(node)


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    scrub = _redaction_mod().safe_scrub
    return {str(k): _redact_node(v, scrub) for k, v in payload.items()}


def quarantine_for_review(payload: Mapping[str, Any], source: str) -> str:
    untrusted = _untrusted_mod()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str, sort_keys=True)
    return untrusted.quarantine(rendered, source)


def _quota_state_path(events_path: Path | None, quota_path: Path | None) -> Path:
    if quota_path is not None:
        return Path(quota_path)
    if events_path is not None:
        return Path(events_path).parent / QUOTA_STATE_FILENAME
    return DEFAULT_QUOTA_PATH


def _deny(
    outcome: CallOutcome,
    reason: str,
    *,
    ts: str,
    principal_id: str,
    verified: bool,
    events_path: Path | None,
    extra: dict[str, Any] | None = None,
) -> CallResult:
    record: dict[str, Any] = {
        "event_type": "a2a_call",
        "ts": ts,
        "principal_id": principal_id,
        "principal_verified": bool(verified),
        "decision": "deny",
        "outcome": outcome.value,
        "reason": reason,
    }
    if extra:
        record.update(extra)
    _append_event(record, events_path)
    return CallResult(outcome=outcome, reason=reason)


def handle_call(
    payload: dict[str, Any],
    *,
    principal: str | None = None,
    credential: str | None = None,
    model: str = "a2a-caller",
    bind_url: str = DEFAULT_BIND,
    flag_enabled: bool | None = None,
    intake_handler: Callable[[dict[str, Any], str], Any] | None = None,
    events_path: Path | None = None,
    features_path: Path | None = None,
    credentials_path: Path | None = None,
    credential_registry: Any | None = None,
    quota_path: Path | None = None,
    quota_policy: Any | None = None,
    payload_limits: Any | None = None,
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

    claimed = str(principal or "").strip()

    if not endpoint_bind_in_tenant(bind_url):
        return _deny(
            CallOutcome.REJECTED_TENANT,
            (
                f"TN-1 BLOCK: endpoint bind {bind_url!r} is not in-tenant — a "
                "hosted relay/registry is refused (config/tenant_boundary.yaml, "
                "scripts/check_in_tenant.is_in_tenant reused verbatim)"
            ),
            ts=ts,
            principal_id=claimed,
            verified=False,
            events_path=events_path,
        )

    creds = _credentials_mod()
    try:
        registry = (
            tuple(credential_registry)
            if credential_registry is not None
            else creds.load_credential_registry(credentials_path)
        )
    except creds.CredentialConfigError as exc:
        return _deny(
            CallOutcome.REFUSED_UNAUTHENTICATED,
            f"REFUSED: the A2A credential registry is unusable — {exc}",
            ts=ts,
            principal_id=claimed,
            verified=False,
            events_path=events_path,
        )

    identity, identity_reason = creds.resolve_caller_identity(
        credential=credential, claimed_principal=claimed, registry=registry
    )
    if identity is None:
        return _deny(
            CallOutcome.REFUSED_UNAUTHENTICATED,
            identity_reason,
            ts=ts,
            principal_id=claimed,
            verified=False,
            events_path=events_path,
        )

    principal_id = identity.principal_id
    verified = identity.verified

    untrusted = _untrusted_mod()
    limit_violations = untrusted.payload_limit_violations(payload, payload_limits)
    if limit_violations:
        return _deny(
            CallOutcome.REFUSED_PAYLOAD_LIMIT,
            (
                "REFUSED: payload exceeds the accepted size/shape limits — "
                + "; ".join(limit_violations)
            ),
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
            extra={"limit_violations": limit_violations},
        )

    forbidden = _forbidden_fields_present(payload) if isinstance(payload, dict) else ["<non-mapping payload>"]
    if forbidden:
        return _deny(
            CallOutcome.REFUSED_FORBIDDEN_FIELD,
            (
                f"REFUSED: payload carries forbidden control field(s) {forbidden} — "
                "a goal-proposal object has no place for a governance write (§1.1); "
                "the field is refused, never silently stripped-and-accepted; the "
                "scan walks nested objects and arrays, not just the top level"
            ),
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
            extra={"forbidden_fields": forbidden},
        )

    shape_errors = _validate_proposal_shape(payload)
    if shape_errors:
        return _deny(
            CallOutcome.REFUSED_MALFORMED,
            f"REFUSED: malformed proposal — {'; '.join(shape_errors)}",
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
        )

    verdict = untrusted.screen(payload)
    if untrusted.is_blocked(verdict):
        return _deny(
            CallOutcome.REFUSED_INJECTION,
            (
                "REFUSED: the proposal carries instruction-shaped content — "
                f"{untrusted.describe(verdict)}; an external peer may propose a "
                "goal, never issue an instruction"
            ),
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
            extra={
                "injection_risk": untrusted.risk_name(verdict),
                "injection_signals": untrusted.signal_names(verdict),
                "injection_excerpts": [
                    _redaction_mod().safe_scrub(item) for item in untrusted.excerpts(verdict)
                ],
            },
        )

    quota = _quota_mod()
    policy = quota_policy or (quota.VERIFIED_POLICY if verified else quota.UNVERIFIED_POLICY)
    reservation = quota.reserve(
        principal_id,
        policy=policy,
        state_path=_quota_state_path(events_path, quota_path),
    )
    if not reservation.granted:
        return _deny(
            CallOutcome.REFUSED_QUOTA,
            f"REFUSED: {reservation.reason}",
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
            extra={"quota_used": reservation.used, "quota_limit": reservation.limit},
        )

    admit = _ws_b_admission_mod().admit
    admission = admit(ticket_id=reservation.reference, role=ENDPOINT_ROLE, model=model)
    if not admission.admitted:
        result = _deny(
            CallOutcome.REJECTED_ADMISSION,
            f"ADR-0009 admission denied: {admission.reason}",
            ts=ts,
            principal_id=principal_id,
            verified=verified,
            events_path=events_path,
            extra={"call_ref": reservation.reference},
        )
        return CallResult(
            outcome=result.outcome,
            reason=result.reason,
            admission=admission,
            identity=identity,
            screening=verdict,
        )

    redacted = _redact_payload(payload)
    _append_event(
        {
            "event_type": "a2a_call",
            "ts": ts,
            "principal_id": principal_id,
            "principal_verified": verified,
            "credential_id": identity.credential_id,
            "call_ref": reservation.reference,
            "quota_used": reservation.used,
            "quota_limit": reservation.limit,
            "decision": "allow",
            "outcome": CallOutcome.ADMITTED.value,
            "reason": (
                "admitted: in-tenant, identity resolved, within payload limits, no "
                "forbidden field at any depth, no instruction-shaped content, "
                "within per-principal quota, ADR-0009 admission ok"
            ),
            "identity_reason": identity_reason,
            "injection_risk": untrusted.risk_name(verdict),
            "injection_signals": untrusted.signal_names(verdict),
            "redacted_payload": redacted,
        },
        events_path,
    )

    forwarded = intake_handler(redacted, principal_id) if intake_handler is not None else None
    return CallResult(
        outcome=CallOutcome.ADMITTED,
        reason="admitted, screened, redacted, and audited",
        admission=admission,
        forwarded=forwarded,
        identity=identity,
        screening=verdict,
    )
