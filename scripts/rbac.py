#!/usr/bin/env python3
"""rbac.py — WS-E RBAC Founder-gate decision + attributed audit (TN-3 / FR-001, DAS-1582).

The runtime half of the RBAC model whose SSOT is ``config/rbac.yaml`` (design
``docs/design/ws-e-tenant-hardening.md`` §1). Three responsibilities, each fail-closed:

1. ``decide(principal, permission)`` — the access evaluator. Default-DENY: a permission
   not explicitly granted to a principal's kind is denied. The founder-only permissions
   (``gate.approve`` / ``run.trigger`` / ``config.edit.security``) may be held ONLY by a
   ``founder`` principal; :func:`load_grants` REFUSES to load an ``rbac.yaml`` that grants
   one to any other kind (tamper refusal). So ``decide("agent:<any-role>", "gate.approve")``
   is deny **by construction** — the exact ADR-0026 / WS-A "structurally unrepresentable"
   pattern applied to gate approval (§1.3).

2. ``append_gate_approval(...)`` — the ONLY producer of a ``gate_approval`` audit record.
   The ``principal_kind`` is STAMPED from the authenticated principal by the runtime, never
   accepted from a caller — so an ``agent`` principal can never emit a record stamped
   ``principal_kind: founder`` (the append is refused before anything is written, §1.4). The
   record is append-only + attributed + ADR-0012-redacted at write; it carries no secret
   field (Tier-M by construction).

3. ``is_gate_closed(...)`` — a never-auto-approve gate is closed ONLY when a matching
   Founder-identity ``gate_approval`` event exists. A ``approval: human:founder`` frontmatter
   string with NO backing Founder-identity event is a **forged claim** and closes NO gate
   (§1.4 / SC-001). The frontmatter alone is not trusted — the same discipline as the
   Model-Allocation law ("the frontmatter alone is not trusted; model is passed explicitly").

Everything is inert-able behind ``ws_e_tenant_hardening`` (default OFF): with the flag OFF
the enforcement entry points (:func:`enforce_gate_closed`, the SIEM export in
``rbac_siem_export.py``) do not run and dispatch is unchanged (FR-008 / SC-005). The pure
evaluator :func:`decide` is a library primitive usable directly by tests.

The gate_approval audit trail is a DEDICATED append-only ledger,
``board/.rbac-audit.jsonl`` (gitignored runtime state, same posture as the WS-A
``board/.tool-audit.jsonl`` and ``board/.control-plane-audit.jsonl``). It is read
read-only by ``rbac_siem_export.py`` and never written back to.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

# Self-locating repo root (LAW A — no hardcoded home path). scripts/rbac.py -> scripts/ -> root.
ROOT = Path(__file__).resolve().parent.parent

DEFAULT_RBAC_CONFIG = ROOT / "config" / "rbac.yaml"
DEFAULT_AUDIT_PATH = ROOT / "board" / ".rbac-audit.jsonl"
DEFAULT_FEATURES = ROOT / "config" / "features.yaml"

FLAG = "ws_e_tenant_hardening"

# The permissions that may be held ONLY by a founder principal. load_grants()
# refuses any rbac.yaml that grants one of these to a non-founder kind (§1.3).
# `a2a.publish` (A2-6, DAS-1610/ADR-0040) is the A2A outbound publish-gate
# permission — publishing/enabling/repointing the A2A endpoint is a Founder act
# (mirrors TN-3), so it is structurally founder-only exactly like the original
# three: `decide("agent:<any-role>", "a2a.publish")` is deny by construction,
# and `load_grants()` refuses to load an `rbac.yaml` that granted it to a
# non-founder kind (the same refuse-to-load lock, applied to a fourth permission).
FOUNDER_ONLY = frozenset(
    {"gate.approve", "run.trigger", "config.edit.security", "a2a.publish"}
)

# Recognised grant values in the matrix. Anything else is a config error (fail-closed).
_VALID_GRANTS = frozenset({"allow", "own"})

# The QONUN-5 never-auto-approve categories (mirrors scripts/check_never_auto_approve
# ._QONUN5_FLOOR). Each maps to the human-only founder role — the RBAC double-lock.
QONUN5_CATEGORIES = frozenset(
    {
        "new_goal",
        "security_sensitive",
        "schema_migration",
        "gate5_deployment",
        "governance_or_policy",
        "permission_change",
        "secret_change",
    }
)

# Tier-M (controlled-vocabulary / id / enum / timestamp) keys of a gate_approval record.
# These are exported as-is; every OTHER key is Tier-B and is ADR-0012-scrubbed on export.
GATE_APPROVAL_TIER_M = frozenset(
    {
        "event_type",
        "ticket_id",
        "principal_id",
        "principal_kind",
        "category",
        "gate",
        "ts",
        "created_at",
        "attestation_ref",
        "trace_id",
        "run_id",
    }
)


class RbacConfigError(RuntimeError):
    """Raised when ``config/rbac.yaml`` is present but violates a structural invariant.

    A tampered security config (e.g. ``gate.approve`` granted to an agent kind) is a loud,
    fail-closed refusal — never a silent load.
    """


class ApprovalRefused(RuntimeError):
    """Raised when a principal that does not hold ``gate.approve`` attempts to emit a
    ``gate_approval`` record — the write never happens (§1.4)."""


# ---------------------------------------------------------------------------
# Lazy path-based load of the ADR-0012 scrubber (reuse VERBATIM — no fork).
# ---------------------------------------------------------------------------
_redaction: Any = None


def _redaction_mod() -> Any:
    global _redaction
    if _redaction is None:
        spec = importlib.util.spec_from_file_location(
            "rbac_redaction", ROOT / "tools" / "mcp_bridges" / "redaction.py"
        )
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise ImportError("cannot load tools/mcp_bridges/redaction.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _redaction = mod
    return _redaction


# ---------------------------------------------------------------------------
# Feature flag (FR-008). Fail-safe to OFF — a broken/absent config never turns
# enforcement ON. Line-scan (no YAML dependency), matching tools/sandbox/flag.py.
#
# The config file is the ONLY source. There used to be a ``DASLAB_WS_E_FLAG``
# environment override here, read BEFORE the ``features_path`` argument, and it
# was wrong in both directions: an ambient ``=false`` silently disabled a security
# posture that ``config/features.yaml`` commits as ON (activated 2026-07-26), and
# an explicitly passed ``features_path`` could not be reached at all. FR-008 places
# this flag in ``config/features.yaml``, and ADR-0019's canonical reader
# (``scripts/feature_flags.enabled``) honours no env var either — so neither the
# spec nor the SSOT reader ever sanctioned the override. Its docstring called it a
# test affordance; no test needs it (the two that set it also pass an explicit
# path, or rely on the committed value).
#
# The line-scan stays rather than delegating to ``feature_flags.enabled``: that
# reader falls back to all-OFF DEFAULTS when PyYAML is absent, which for a security
# flag would just be a different silent weakening.
# ---------------------------------------------------------------------------
def is_enabled(features_path: Path | None = None) -> bool:
    """True iff ``ws_e_tenant_hardening`` resolves truthy. Default OFF ⇒ enforcement inert.

    Resolved from the features file only: ``features_path`` when given, else
    :data:`DEFAULT_FEATURES`. No environment variable can flip it.
    """
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


# ---------------------------------------------------------------------------
# Grant matrix loading + the structural founder-only invariant (§1.3).
# ---------------------------------------------------------------------------
def load_grants(config_path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load and validate the ``grants`` matrix from ``config/rbac.yaml``.

    Fail-closed asymmetry:
    - config ABSENT ⇒ return ``{}`` (nothing grantable — every decide() denies). A missing
      RBAC file can never accidentally grant a permission.
    - config PRESENT but STRUCTURALLY invalid ⇒ raise :class:`RbacConfigError` (a tampered
      security surface is a loud refusal, not a silent partial load). Structural invariants:
        * a founder-only permission (:data:`FOUNDER_ONLY`) may appear only under ``founder``;
        * every grant value is ``allow`` or ``own``.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_RBAC_CONFIG
    if not path.is_file():
        return {}
    try:
        import yaml  # noqa: PLC0415 - optional dependency, imported lazily
    except ImportError as exc:  # pragma: no cover - yaml is a repo dependency
        raise RbacConfigError("pyyaml unavailable — cannot evaluate RBAC config") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RbacConfigError(f"rbac.yaml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RbacConfigError("rbac.yaml is not a mapping")
    raw_grants = data.get("grants") or {}
    if not isinstance(raw_grants, dict):
        raise RbacConfigError("rbac.yaml 'grants' is not a mapping")

    grants: dict[str, dict[str, str]] = {}
    for kind, perms in raw_grants.items():
        kind = str(kind)
        if not isinstance(perms, dict):
            raise RbacConfigError(f"grants for kind {kind!r} is not a mapping")
        cleaned: dict[str, str] = {}
        for perm, value in perms.items():
            perm = str(perm)
            value = str(value).strip().lower()
            if value not in _VALID_GRANTS:
                raise RbacConfigError(
                    f"grant {kind}.{perm} = {value!r} is not one of {sorted(_VALID_GRANTS)}"
                )
            # Structural founder-only invariant: gate.approve / run.trigger /
            # config.edit.security may be granted ONLY to founder — refuse to load otherwise.
            if perm in FOUNDER_ONLY and kind != "founder":
                raise RbacConfigError(
                    f"STRUCTURAL VIOLATION: founder-only permission {perm!r} granted to "
                    f"non-founder kind {kind!r} — refusing to load (fail-closed, QONUN-5)"
                )
            cleaned[perm] = value
        grants[kind] = cleaned
    return grants


def _kind_of(principal: str) -> str | None:
    """Resolve a principal string to exactly one kind, or ``None`` (deny-all) if unknown.

    ``founder`` / ``audit-team`` / ``orchestrator`` are exact names; an ``agent:<role>`` is
    any string prefixed ``agent:`` (or ``agent/``). Anything else — a bare role name, a
    forged handle, an empty string — resolves to ``None`` and holds NOTHING (fail-closed).
    """
    p = str(principal).strip().lower()
    if p == "founder":
        return "founder"
    if p in {"audit-team", "audit_team", "audit-reader"}:
        return "audit-team"
    if p == "orchestrator":
        return "orchestrator"
    if p.startswith(("agent:", "agent/")):
        return "agent"
    return None


def decide(
    principal: str,
    permission: str,
    *,
    scope: bool | dict[str, Any] | None = None,
    config: dict[str, dict[str, str]] | None = None,
    config_path: Path | None = None,
) -> tuple[str, str]:
    """Return ``("allow"|"deny", reason)`` for *principal* requesting *permission*.

    Default-DENY. A permission absent from the principal's kind is denied. An unknown
    principal kind is denied everything. A scoped (``own``) grant — an agent's own ticket /
    own run — is allowed only when *scope* establishes ownership (``scope is True`` or a
    dict whose ``owner`` matches *principal*); otherwise it fail-closes to deny.

    ``decide("agent:<any-role>", "gate.approve")`` is deny by construction: the founder-only
    permission is absent from the agent kind AND :func:`load_grants` would refuse to load a
    config that granted it (§1.3).
    """
    grants = config if config is not None else load_grants(config_path)
    kind = _kind_of(principal)
    if kind is None:
        return ("deny", f"unknown principal kind for {principal!r} — holds nothing (fail-closed)")
    grant = grants.get(kind, {}).get(permission)
    if grant is None:
        return ("deny", f"{kind} is not granted {permission!r} (default-deny)")
    if grant == "allow":
        return ("allow", f"{kind} holds {permission!r}")
    if grant == "own":
        owner_ok = scope is True or (
            isinstance(scope, dict) and str(scope.get("owner", "")) == str(principal)
        )
        if owner_ok:
            return ("allow", f"{kind} holds {permission!r} for its own scope")
        return (
            "deny",
            f"{kind} holds {permission!r} only for its own scope; ownership not established",
        )
    return ("deny", f"unrecognised grant {grant!r} for {kind}.{permission} (fail-closed)")


def can(principal: str, permission: str, **kwargs: Any) -> bool:
    """Boolean convenience over :func:`decide` — True iff the decision is ``allow``."""
    return decide(principal, permission, **kwargs)[0] == "allow"


# ---------------------------------------------------------------------------
# The attributed gate_approval audit trail (§2.1) — append-only, redacted at write.
# ---------------------------------------------------------------------------
def _append_audit(record: dict[str, Any], audit_path: Path | None = None) -> None:
    """Append one JSON record to the dedicated append-only RBAC audit ledger.

    Durable append discipline (O_APPEND on POSIX). The ledger is NEVER rewritten or
    truncated by this module — a correction is a new compensating record.
    """
    path = Path(audit_path) if audit_path is not None else DEFAULT_AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
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


def build_gate_approval(
    *,
    principal_id: str,
    principal_kind: str,
    ticket_id: str,
    category: str,
    gate: str,
    created_at: str,
    attestation_ref: str | None = None,
    trace_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a ``gate_approval`` record dict (Tier-M by construction — no secret field).

    Pure builder (no clock read, no I/O) — ``created_at`` is caller-supplied for
    determinism/testability. The ``principal_kind`` here is whatever the CALLER of the
    builder passed; the SAFE producer is :func:`append_gate_approval`, which stamps the
    kind from the authenticated principal and refuses a non-approver.
    """
    record: dict[str, Any] = {
        "event_type": "gate_approval",
        "ticket_id": ticket_id,
        "principal_id": principal_id,
        "principal_kind": principal_kind,
        "category": category,
        "gate": gate,
        "ts": created_at,
        "created_at": created_at,
    }
    if attestation_ref is not None:
        record["attestation_ref"] = attestation_ref
    if trace_id is not None:
        record["trace_id"] = trace_id
    if run_id is not None:
        record["run_id"] = run_id
    return record


def append_gate_approval(
    *,
    principal: str,
    ticket_id: str,
    category: str,
    gate: str,
    created_at: str,
    attestation_ref: str | None = None,
    trace_id: str | None = None,
    run_id: str | None = None,
    audit_path: Path | None = None,
    config: dict[str, dict[str, str]] | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Record an attributed ``gate_approval`` — the ONLY valid producer of one (§1.4).

    The ``principal_kind`` is STAMPED by the runtime from *principal* (:func:`_kind_of`),
    NOT accepted from any caller/agent output — so an ``agent`` principal can never produce
    a record stamped ``principal_kind: founder``. Before anything is written the principal
    must actually hold ``gate.approve`` (``decide(...) == allow``); otherwise
    :class:`ApprovalRefused` is raised and the ledger is untouched.

    Returns the appended record. Raises :class:`ApprovalRefused` for a non-approver
    (agent / audit-team / orchestrator / unknown).
    """
    decision, reason = decide(principal, "gate.approve", config=config, config_path=config_path)
    if decision != "allow":
        raise ApprovalRefused(
            f"{principal!r} cannot emit a gate_approval — {reason}. No record written."
        )
    kind = _kind_of(principal)  # == "founder" only for a genuine founder principal
    record = build_gate_approval(
        principal_id=str(principal),
        principal_kind=str(kind),
        ticket_id=ticket_id,
        category=category,
        gate=gate,
        created_at=created_at,
        attestation_ref=attestation_ref,
        trace_id=trace_id,
        run_id=run_id,
    )
    # Belt-and-suspenders: redact any Tier-B value at write (ADR-0012). Tier-M ids pass as-is.
    scrub = _redaction_mod().safe_scrub
    safe = {k: (v if k in GATE_APPROVAL_TIER_M else scrub(v)) for k, v in record.items()}
    _append_audit(safe, audit_path)
    return safe


def iter_gate_approvals(audit_path: Path | None = None) -> list[dict[str, Any]]:
    """Read the append-only RBAC audit ledger (read-only), oldest-first.

    Corrupt/partial lines are skipped (replay tolerance) — never crash the reader.
    """
    path = Path(audit_path) if audit_path is not None else DEFAULT_AUDIT_PATH
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict) and ev.get("event_type") == "gate_approval":
                out.append(ev)
    return out


def is_gate_closed(
    ticket_id: str,
    category: str,
    *,
    approval_claim: str | None = None,
    audit_path: Path | None = None,
) -> tuple[bool, str]:
    """Is the never-auto-approve gate for (*ticket_id*, *category*) actually closed?

    A gate closes ONLY when a matching Founder-identity ``gate_approval`` event exists in
    the audit ledger (``principal_kind == "founder"`` AND ``ticket_id`` + ``category``
    match). The *approval_claim* frontmatter string (e.g. ``"human:founder"``) is a CLAIM,
    NOT the fact: with no backing Founder-identity event it is a **forged approval** and
    the gate stays OPEN (§1.4 / SC-001).

    Returns ``(closed, reason)``.
    """
    for ev in iter_gate_approvals(audit_path):
        if (
            ev.get("ticket_id") == ticket_id
            and ev.get("category") == category
            and ev.get("principal_kind") == "founder"
        ):
            return (True, f"backed by a Founder-identity gate_approval event ({ev.get('principal_id')})")
    claim = f" (frontmatter claim {approval_claim!r} is unverified)" if approval_claim else ""
    return (
        False,
        f"no matching Founder-identity gate_approval event for {ticket_id}/{category}"
        f"{claim} — gate NOT closed (forged/absent approval rejected)",
    )


def enforce_gate_closed(
    ticket_id: str,
    category: str,
    *,
    approval_claim: str | None = None,
    audit_path: Path | None = None,
    features_path: Path | None = None,
) -> tuple[bool, str]:
    """Flag-gated wrapper over :func:`is_gate_closed` (FR-008).

    With ``ws_e_tenant_hardening`` OFF (default) enforcement is INERT — returns
    ``(True, "inert")`` so dispatch is byte-identical to pre-merge (the WS-E surface does
    not exist). With the flag ON it delegates to :func:`is_gate_closed`.
    """
    if not is_enabled(features_path):
        return (True, "ws_e_tenant_hardening OFF — RBAC gate enforcement inert (dispatch unchanged)")
    return is_gate_closed(ticket_id, category, approval_claim=approval_claim, audit_path=audit_path)


if __name__ == "__main__":  # pragma: no cover - manual probe
    import sys

    who = sys.argv[1] if len(sys.argv) > 1 else "agent:backend-em"
    what = sys.argv[2] if len(sys.argv) > 2 else "gate.approve"
    dec, why = decide(who, what)
    print(f"decide({who!r}, {what!r}) -> {dec} — {why}")
