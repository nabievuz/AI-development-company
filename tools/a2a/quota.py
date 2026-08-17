from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

FILELOCK_PATH = ROOT / "scripts" / "filelock.py"

_FILELOCK_ALIAS = "a2a_quota_filelock"

STATE_VERSION = 1


class QuotaStoreError(RuntimeError):
    pass


_filelock: Any = None


def _filelock_mod() -> Any:
    global _filelock
    if _filelock is not None:
        return _filelock
    cached = sys.modules.get(_FILELOCK_ALIAS)
    if cached is not None:
        _filelock = cached
        return _filelock
    if not FILELOCK_PATH.is_file():
        raise QuotaStoreError(
            f"the durable-write helper is missing at {FILELOCK_PATH}; the quota "
            "store refuses to do a lock-free read-modify-write"
        )
    spec = importlib.util.spec_from_file_location(_FILELOCK_ALIAS, FILELOCK_PATH)
    if spec is None or spec.loader is None:
        raise QuotaStoreError(f"cannot load {FILELOCK_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_FILELOCK_ALIAS] = module
    spec.loader.exec_module(module)
    _filelock = module
    return _filelock


@dataclass(frozen=True)
class QuotaPolicy:

    max_calls: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")


VERIFIED_POLICY = QuotaPolicy(max_calls=60, window_seconds=3600.0)

UNVERIFIED_POLICY = QuotaPolicy(max_calls=20, window_seconds=3600.0)


@dataclass(frozen=True)
class QuotaDecision:

    granted: bool
    principal_id: str
    used: int
    limit: int
    window_seconds: float
    reference: str
    reason: str


def _call_reference(principal_id: str, moment: float, used: int) -> str:
    digest = hashlib.sha256(
        f"{principal_id}|{moment:.6f}|{used}".encode()
    ).hexdigest()
    return f"A2A-CALL-{digest[:16].upper()}"


def _load_state(raw: str) -> dict[str, list[float]]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    calls = parsed.get("calls")
    if not isinstance(calls, dict):
        return {}
    state: dict[str, list[float]] = {}
    for principal, stamps in calls.items():
        if not isinstance(stamps, list):
            continue
        numeric = [float(s) for s in stamps if isinstance(s, int | float)]
        state[str(principal)] = numeric
    return state


def _dump_state(state: dict[str, list[float]]) -> str:
    payload = {
        "version": STATE_VERSION,
        "calls": {p: sorted(s) for p, s in sorted(state.items()) if s},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def reserve(
    principal_id: str,
    *,
    policy: QuotaPolicy,
    state_path: Path,
    now: float | None = None,
) -> QuotaDecision:
    name = str(principal_id).strip()
    if not name:
        raise ValueError("principal_id is required to charge a quota")
    moment = time.time() if now is None else float(now)
    cutoff = moment - policy.window_seconds
    outcome: dict[str, Any] = {}

    def _transform(current: str) -> str:
        state = _load_state(current)
        recent = [stamp for stamp in state.get(name, []) if stamp > cutoff]
        if len(recent) >= policy.max_calls:
            outcome["granted"] = False
            outcome["used"] = len(recent)
            state[name] = recent
            return _dump_state(state)
        outcome["granted"] = True
        outcome["used"] = len(recent) + 1
        state[name] = [*recent, moment]
        return _dump_state(state)

    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _filelock_mod().locked_update_text(path, _transform, default=_dump_state({}))

    used = int(outcome.get("used", 0))
    granted = bool(outcome.get("granted", False))
    if granted:
        return QuotaDecision(
            granted=True,
            principal_id=name,
            used=used,
            limit=policy.max_calls,
            window_seconds=policy.window_seconds,
            reference=_call_reference(name, moment, used),
            reason=(
                f"within quota: call {used} of {policy.max_calls} allowed in the "
                f"last {int(policy.window_seconds)}s for this principal"
            ),
        )
    return QuotaDecision(
        granted=False,
        principal_id=name,
        used=used,
        limit=policy.max_calls,
        window_seconds=policy.window_seconds,
        reference="",
        reason=(
            f"per-principal quota exhausted: {used} call(s) already made in the "
            f"last {int(policy.window_seconds)}s, limit is {policy.max_calls}"
        ),
    )


def usage(principal_id: str, *, state_path: Path, window_seconds: float, now: float | None = None) -> int:
    path = Path(state_path)
    if not path.is_file():
        return 0
    moment = time.time() if now is None else float(now)
    cutoff = moment - window_seconds
    state = _load_state(path.read_text(encoding="utf-8"))
    return len([stamp for stamp in state.get(str(principal_id).strip(), []) if stamp > cutoff])
