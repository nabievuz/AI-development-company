"""publish.py — the A2A publish-is-a-Founder-act gate (A2-6/FR-003), DAS-1610.

Design ``docs/design/a2a-outbound.md`` §2.2/§2.3. Publishing, enabling, or
repointing the A2A endpoint is a distribution/governance decision reserved to
the Founder (QONUN-5) — never a workstream-ticket decision, never automated,
never self-triggered on merge. Two independent fail-closed legs, EITHER of
which refuses the act (both legs logged, allow and deny symmetric, §2.2):

1. **Founder-identity RBAC** — ``scripts/rbac.decide(principal, "a2a.publish")``
   (REUSED verbatim, the WS-E SSOT evaluator; no new identity mechanism).
   ``a2a.publish`` is registered in ``rbac.FOUNDER_ONLY``, so
   ``rbac.load_grants()`` REFUSES to load an ``rbac.yaml`` that granted it to
   a non-Founder kind — the structural refuse-to-load lock this ticket's build
   requirement calls for.
2. **TN-1 in-tenant boundary on the publish target** —
   ``scripts/check_in_tenant.is_in_tenant`` (REUSED verbatim). A hosted
   relay/registry ``target`` is refused even for a genuine Founder — RBAC
   authority and the tenant boundary are independent locks; passing one never
   waives the other.

Every publish/enable/repoint attempt — allow AND deny — is appended to the
canonical append-only event store (``board/.events.jsonl``, ADR-0024/0025) as
an ``a2a_publish`` event, attributed from the authenticated principal (never
accepted from request content) per the design §2.2 event shape.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENTS_PATH = ROOT / "board" / ".events.jsonl"

# The Founder-only permission this gate checks (registered in
# scripts/rbac.py's FOUNDER_ONLY set alongside gate.approve/run.trigger/
# config.edit.security).
PERMISSION = "a2a.publish"


# ---------------------------------------------------------------------------
# Lazy, path-based loading of sibling repo modules — REUSE, never reimplement
# (mirrors tools/model_gateway/gateway.py's `_load_module` / tools/a2a/endpoint.py).
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
_check_in_tenant: Any = None


def _rbac_mod() -> Any:
    global _rbac
    if _rbac is None:
        _rbac = _load_module("scripts/rbac.py", "a2a_publish_rbac")
    return _rbac


def _check_in_tenant_mod() -> Any:
    global _check_in_tenant
    if _check_in_tenant is None:
        _check_in_tenant = _load_module("scripts/check_in_tenant.py", "a2a_publish_check_in_tenant")
    return _check_in_tenant


class PublishRefused(RuntimeError):
    """Raised when publish is refused — RBAC deny or TN-1 boundary violation.

    The refusal event is ALWAYS appended to the ledger BEFORE this is raised
    (the deny path is symmetric to the allow path, design §2.2) — a caller
    catching this exception still has an audited record of the attempt.
    """


def _utcnow() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_event(record: dict[str, Any], path: Path | None = None) -> None:
    """Durable append (O_APPEND + flock + fsync) — mirrors
    ``scripts/rbac._append_audit`` / ``tools/a2a/endpoint._append_event``.
    Never rewrites/truncates the ledger; a correction is a new event."""
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


def build_publish_event(
    *,
    principal_id: str,
    principal_kind: str,
    decision: str,
    flag_state: bool,
    target: str,
    reason: str,
    ts: str,
) -> dict[str, Any]:
    """Build an ``a2a_publish`` event dict (design §2.2 event shape).

    Pure builder (no clock read, no I/O) — ``ts`` is caller-supplied for
    determinism/testability, matching ``scripts/rbac.build_gate_approval``'s
    discipline. Every field here is Tier-M (id/enum/reference/timestamp);
    ``target`` is a resolved endpoint bind/config REFERENCE, never a secret.
    """
    return {
        "event_type": "a2a_publish",
        "ts": ts,
        "principal_id": principal_id,
        "principal_kind": principal_kind,
        "decision": decision,
        "flag_state": bool(flag_state),
        "target": str(target),
        "reason": reason,
    }


def publish(
    principal: str,
    *,
    target: str,
    flag_state: bool = True,
    created_at: str | None = None,
    config: dict[str, dict[str, str]] | None = None,
    config_path: Path | None = None,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    """Publish/enable/repoint the A2A endpoint — a Founder act (A2-6/§2.2).

    Returns the appended ``allow`` event on success. Raises
    :class:`PublishRefused` — after logging the ``deny`` event — if EITHER:

    - *principal* does not hold ``a2a.publish`` (``rbac.decide`` != allow;
      denied by construction for any ``agent:*``/``orchestrator``/
      ``audit-team``/unknown principal — only a genuine ``founder`` principal
      can ever hold it, and only if ``rbac.yaml`` legally grants it, itself
      gated by the ``FOUNDER_ONLY`` refuse-to-load lock), or
    - *target* does not resolve in-tenant (TN-1) — a hosted relay/registry is
      refused even for a genuine Founder; the two locks are independent.
    """
    rbac = _rbac_mod()
    ts = created_at or _utcnow()
    decision, reason = rbac.decide(principal, PERMISSION, config=config, config_path=config_path)
    kind = rbac._kind_of(principal)

    if decision != "allow":
        event = build_publish_event(
            principal_id=str(principal),
            principal_kind=str(kind),
            decision="deny",
            flag_state=flag_state,
            target=target,
            reason=reason,
            ts=ts,
        )
        _append_event(event, audit_path)
        raise PublishRefused(
            f"a2a.publish refused for {principal!r}: {reason}. Event logged, endpoint NOT published."
        )

    cit = _check_in_tenant_mod()
    if not cit.is_in_tenant(target):
        tn1_reason = (
            f"TN-1 BLOCK: publish target {target!r} resolves to an EXTERNAL host — "
            "no hosted relay/registry is permitted, even for a genuine Founder act "
            "(config/tenant_boundary.yaml, scripts/check_in_tenant.is_in_tenant reused verbatim)"
        )
        event = build_publish_event(
            principal_id=str(principal),
            principal_kind=str(kind),
            decision="deny",
            flag_state=flag_state,
            target=target,
            reason=tn1_reason,
            ts=ts,
        )
        _append_event(event, audit_path)
        raise PublishRefused(f"{tn1_reason}. Event logged, endpoint NOT published.")

    event = build_publish_event(
        principal_id=str(principal),
        principal_kind=str(kind),
        decision="allow",
        flag_state=flag_state,
        target=target,
        reason=reason,
        ts=ts,
    )
    _append_event(event, audit_path)
    return event
