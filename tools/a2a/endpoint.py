"""endpoint.py — the A2A outbound governed endpoint (FR-001, FR-005), DAS-1610.

Realizes the ONE governed edge design ``docs/design/a2a-outbound.md`` §0/§2.4
fixes: an external agent-system caller reaches exactly one edge, and
:func:`handle_call` is it. This module stands up **no second admission path**
and **no board-write path of its own** — it wires the ``a2a_outbound`` flag,
the TN-1 in-tenant boundary, the reused ADR-0009 admission gateway
(``scripts/ws_b_admission.admit``), and the reused ADR-0012 redaction
discipline (``tools/mcp_bridges/redaction.safe_scrub``) around a call, then
audits it. Building the actual intake handler that writes a
``board/goal-inbox/`` proposal is DAS-1611's job (``scripts/a2a_intake``,
a distinct repo zone); this module's ``intake_handler`` parameter is a pure
dependency-injection seam so a caller (or a test) can wire that handler in
without this module importing across the zone boundary.

Injection defense (A2-3, design §1.4): the caller payload is untrusted DATA,
never instruction. A forbidden control field (``approval``/``status``/
``assignee``/... — see :data:`FORBIDDEN_FIELDS`) is refused, never stripped
and silently accepted — and even an admitted call's redacted payload is only
ever *forwarded* to an injected handler; this module contains no code path
that itself writes an approval/gate/routing field anywhere, so such a write
is unreachable by construction (mirrors the WS-A/WS-B "structurally
unrepresentable" pattern).

Ships behind ``a2a_outbound`` (default OFF, ``config/features.yaml``, landed
DAS-1607). Present in ``scripts/feature_flags.py``'s ``DEFAULTS`` allowlist
since DAS-1624 (both readers now agree in either flag state), but
:func:`is_enabled` stays a dedicated line-scan reader mirroring
``scripts/rbac.py``'s ``is_enabled`` — fail-safe-to-OFF on any read problem,
exactly the same posture — rather than delegating to
``scripts/feature_flags.py: enabled()``, to keep this endpoint's own trust
boundary independent of that shared reader.
"""
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

# Dedicated flag (DAS-1607, ADR-0040) — NOT a reuse of ws_d_langfuse_lens; a
# distinct external-caller trust boundary with its own independent kill-switch.
FEATURE_FLAG = "a2a_outbound"

# The role tag under which this endpoint's admission calls are made (mirrors
# tools/model_gateway's role-tagged admission calls).
ENDPOINT_ROLE = "a2a"

# Loopback default per design §2.3 — a tenant-network bind is a deliberate
# Founder act at deploy time, never this module's default.
DEFAULT_BIND = "http://127.0.0.1:8765"

# A goal-proposal object has no place for a governance write (design §1.1).
# Case-insensitive, matched against every top-level payload key. Any of these
# present REFUSES the call outright — never silently stripped-and-accepted.
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

# The minimal required shape of a goal-proposal object (design §1.1).
REQUIRED_PROPOSAL_FIELDS = frozenset({"title", "summary"})


# ---------------------------------------------------------------------------
# Lazy, path-based loading of sibling repo modules — REUSE, never reimplement
# (mirrors tools/model_gateway/gateway.py's `_load_module`). Keeps this
# ticket's footprint to tools/a2a/ with no package install/fork.
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


# ---------------------------------------------------------------------------
# The dedicated a2a_outbound flag reader (line-scan, fail-safe to OFF).
# ---------------------------------------------------------------------------


def is_enabled(features_path: Path | None = None) -> bool:
    """True iff ``a2a_outbound`` resolves truthy. Default OFF => endpoint inert.

    An env override (``DASLAB_A2A_OUTBOUND_FLAG``) takes precedence for tests,
    mirroring ``scripts/rbac.is_enabled``'s override pattern. Any read problem
    (missing file, malformed line) falls back to OFF — a broken config never
    turns the surface on.
    """
    override = os.environ.get("DASLAB_A2A_OUTBOUND_FLAG")
    if override is not None:
        return override.strip().lower() in {"1", "true", "on", "yes"}
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
    """TN-1 check of the endpoint's OWN bind/target (design §2.3, reused verbatim
    from ``scripts/check_in_tenant.is_in_tenant`` — no parallel boundary check)."""
    return bool(_check_in_tenant_mod().is_in_tenant(bind_url))


# ---------------------------------------------------------------------------
# The call outcome vocabulary — every branch returns a result, never raises
# for a sanctioned non-admit outcome (mirrors ws_b_admission.AdmissionOutcome).
# ---------------------------------------------------------------------------


class CallOutcome(StrEnum):
    ADMITTED = "admitted"
    UNAVAILABLE = "unavailable"
    REJECTED_TENANT = "rejected_tenant"
    REJECTED_ADMISSION = "rejected_admission"
    REFUSED_FORBIDDEN_FIELD = "refused_forbidden_field"
    REFUSED_MALFORMED = "refused_malformed"


@dataclass(frozen=True)
class CallResult:
    """The endpoint's verdict for one inbound call. Never carries a raw
    (unredacted) payload — only a redaction-safe reason string and, on ADMIT,
    the redacted echo the audit event also received."""

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
    """Append one JSON record to the canonical append-only event store
    (ADR-0024/0025). Mirrors ``scripts/rbac._append_audit``'s durable-append
    discipline (O_APPEND + flock + fsync); never rewrites/truncates."""
    p = Path(path) if path is not None else DEFAULT_EVENTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(p, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            import fcntl  # noqa: PLC0415 - POSIX-only, optional

            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError, NameError):
                import fcntl  # noqa: PLC0415

                fcntl.flock(fh, fcntl.LOCK_UN)


def _forbidden_fields_present(payload: dict[str, Any]) -> list[str]:
    """Case-insensitive scan for a control-surface field anywhere in the
    payload's top-level keys — a repeated/relabelled field is still caught
    (SC-002b: "however shaped/repeated")."""
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
    """ADR-0012 redact every field's value before it is audited or forwarded —
    reuses the SAME `tools/mcp_bridges/redaction.safe_scrub` scrubber the WS-A
    tool path / WS-D lens / rbac.py gate_approval ledger use (no third redactor,
    §2.4). Fail-closed: an unclassifiable value drops to
    ``[REDACTED:unclassified]`` inside ``safe_scrub`` itself."""
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
    """The ONE governed edge an external agent-system caller reaches (design §0).

    Fail-closed precondition order — every check runs BEFORE any side effect,
    mirroring ``ws_b_admission.admit``'s own "validate inputs up front" discipline:

    1. ``a2a_outbound`` flag ON — else UNAVAILABLE, no audit event, no further
       check reached (the endpoint does not exist; SC-005 byte-identical-when-OFF).
    2. the endpoint's own ``bind_url`` resolves in-tenant (TN-1) — else
       REJECTED_TENANT (a hosted relay/registry BLOCKS), audited as a deny.
    3. the payload carries NO forbidden control field (§1.1) and has the
       minimal required proposal shape — else REFUSED_* (audited as a deny,
       no forward — the caller is told, never silently fixed/dropped).
    4. the ADR-0009 admission gateway (``scripts/ws_b_admission.admit``, REUSED
       verbatim — no second admission path) admits — else REJECTED_ADMISSION
       (audited as a deny).
    5. ADR-0012 redact the payload, append an attributed ``a2a_call`` allow
       event, and ONLY THEN forward the REDACTED payload to ``intake_handler``
       if one is wired (DAS-1611's real handler; ``None`` here is a documented
       no-op forward — this module never writes a board field itself).

    Never raises for a sanctioned non-admit outcome; every branch returns a
    :class:`CallResult`.
    """
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

    # Forward ONLY the redacted payload, and ONLY to an explicitly injected
    # handler (DAS-1611's scripts/a2a_intake) — this endpoint has no board-write
    # code path of its own to be steered into (unreachable by construction).
    forwarded = intake_handler(redacted, str(principal)) if intake_handler is not None else None
    return CallResult(
        outcome=CallOutcome.ADMITTED,
        reason="admitted, redacted, and audited",
        admission=admission,
        forwarded=forwarded,
    )
