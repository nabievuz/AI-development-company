#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_RBAC_CONFIG = ROOT / "config" / "rbac.yaml"
DEFAULT_AUDIT_PATH = ROOT / "board" / ".rbac-audit.jsonl"
DEFAULT_FEATURES = ROOT / "config" / "features.yaml"

FLAG = "ws_e_tenant_hardening"


FOUNDER_ONLY = frozenset(
    {"gate.approve", "run.trigger", "config.edit.security", "a2a.publish"}
)


_VALID_GRANTS = frozenset({"allow", "own"})


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
    pass


class ApprovalRefused(RuntimeError):
    pass


_redaction: Any = None


def _redaction_mod() -> Any:
    global _redaction
    if _redaction is None:
        spec = importlib.util.spec_from_file_location(
            "rbac_redaction", ROOT / "tools" / "mcp_bridges" / "redaction.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("cannot load tools/mcp_bridges/redaction.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _redaction = mod
    return _redaction


def is_enabled(features_path: Path | None = None) -> bool:
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


def load_grants(config_path: Path | None = None) -> dict[str, dict[str, str]]:
    path = Path(config_path) if config_path is not None else DEFAULT_RBAC_CONFIG
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError as exc:
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


            if perm in FOUNDER_ONLY and kind != "founder":
                raise RbacConfigError(
                    f"STRUCTURAL VIOLATION: founder-only permission {perm!r} granted to "
                    f"non-founder kind {kind!r} — refusing to load (fail-closed, QONUN-5)"
                )
            cleaned[perm] = value
        grants[kind] = cleaned
    return grants


def _kind_of(principal: str) -> str | None:
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
    return decide(principal, permission, **kwargs)[0] == "allow"


def _append_audit(record: dict[str, Any], audit_path: Path | None = None) -> None:
    path = Path(audit_path) if audit_path is not None else DEFAULT_AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
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
    decision, reason = decide(principal, "gate.approve", config=config, config_path=config_path)
    if decision != "allow":
        raise ApprovalRefused(
            f"{principal!r} cannot emit a gate_approval — {reason}. No record written."
        )
    kind = _kind_of(principal)
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

    scrub = _redaction_mod().safe_scrub
    safe = {k: (v if k in GATE_APPROVAL_TIER_M else scrub(v)) for k, v in record.items()}
    _append_audit(safe, audit_path)
    return safe


def iter_gate_approvals(audit_path: Path | None = None) -> list[dict[str, Any]]:
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
    if not is_enabled(features_path):
        return (True, "ws_e_tenant_hardening OFF — RBAC gate enforcement inert (dispatch unchanged)")
    return is_gate_closed(ticket_id, category, approval_claim=approval_claim, audit_path=audit_path)


if __name__ == "__main__":
    import sys

    who = sys.argv[1] if len(sys.argv) > 1 else "agent:backend-em"
    what = sys.argv[2] if len(sys.argv) > 2 else "gate.approve"
    dec, why = decide(who, what)
    print(f"decide({who!r}, {what!r}) -> {dec} — {why}")
