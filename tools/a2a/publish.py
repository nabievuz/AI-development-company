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


PERMISSION = "a2a.publish"


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
    pass


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
