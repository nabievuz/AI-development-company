from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

INJECTION_SCREEN_PATH = ROOT / "governance" / "guardrails" / "injection.py"

_INJECTION_MODULE_ALIAS = "daslab_guardrail_injection"


class UntrustedInputError(RuntimeError):
    pass


_injection_module: Any = None


def injection_screen() -> Any:
    global _injection_module
    if _injection_module is not None:
        return _injection_module
    cached = sys.modules.get(_INJECTION_MODULE_ALIAS)
    if cached is not None:
        _injection_module = cached
        return _injection_module
    if not INJECTION_SCREEN_PATH.is_file():
        raise UntrustedInputError(
            f"the prompt-injection screen is missing at {INJECTION_SCREEN_PATH} — "
            "untrusted input cannot be screened, so the boundary fails closed"
        )
    spec = importlib.util.spec_from_file_location(
        _INJECTION_MODULE_ALIAS, INJECTION_SCREEN_PATH
    )
    if spec is None or spec.loader is None:
        raise UntrustedInputError(f"cannot load {INJECTION_SCREEN_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_INJECTION_MODULE_ALIAS] = module
    spec.loader.exec_module(module)
    _injection_module = module
    return _injection_module


@dataclass(frozen=True)
class PayloadLimits:

    max_serialized_bytes: int = 65_536
    max_depth: int = 6
    max_nodes: int = 512
    max_container_items: int = 128
    max_string_chars: int = 16_384
    max_key_chars: int = 128


DEFAULT_LIMITS = PayloadLimits()


def _kind_of(node: Any) -> str:
    if isinstance(node, Mapping):
        return "object"
    if isinstance(node, (str, bytes, bytearray)):
        return "string"
    if isinstance(node, Sequence):
        return "array"
    return "scalar"


def payload_limit_violations(
    payload: Any, limits: PayloadLimits | None = None
) -> list[str]:
    caps = limits or DEFAULT_LIMITS
    violations: list[str] = []
    pending: list[tuple[Any, str, int]] = [(payload, "", 1)]
    nodes = 0

    while pending:
        node, path, depth = pending.pop()
        label = path or "<root>"
        nodes += 1
        if nodes > caps.max_nodes:
            violations.append(
                f"payload carries more than {caps.max_nodes} values — refused "
                "before any recursive scan is attempted"
            )
            break
        if depth > caps.max_depth:
            violations.append(
                f"{_kind_of(node)} at {label} nests deeper than the maximum "
                f"depth of {caps.max_depth}"
            )
            continue
        if isinstance(node, Mapping):
            if len(node) > caps.max_container_items:
                violations.append(
                    f"object at {label} has {len(node)} keys, over the limit of "
                    f"{caps.max_container_items}"
                )
            for key, value in node.items():
                key_text = str(key)
                if len(key_text) > caps.max_key_chars:
                    violations.append(
                        f"key at {label} is {len(key_text)} characters, over the "
                        f"limit of {caps.max_key_chars}"
                    )
                child = f"{path}.{key_text}" if path else key_text
                pending.append((value, child, depth + 1))
        elif isinstance(node, (str, bytes, bytearray)):
            if len(node) > caps.max_string_chars:
                violations.append(
                    f"value at {label} is {len(node)} characters, over the limit "
                    f"of {caps.max_string_chars}"
                )
        elif isinstance(node, Sequence):
            if len(node) > caps.max_container_items:
                violations.append(
                    f"array at {label} has {len(node)} items, over the limit of "
                    f"{caps.max_container_items}"
                )
            for index, value in enumerate(node):
                pending.append((value, f"{path}[{index}]", depth + 1))

    if violations:
        return _deduplicate(violations)

    try:
        encoded = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        return [f"payload is not serialisable and cannot be size-checked: {exc}"]
    if len(encoded) > caps.max_serialized_bytes:
        return [
            f"payload is {len(encoded)} bytes, over the limit of "
            f"{caps.max_serialized_bytes} bytes"
        ]
    return []


def _deduplicate(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def screen(payload: Any) -> Any:
    return injection_screen().screen_untrusted(payload)


def quarantine(text: Any, source: str) -> str:
    return injection_screen().wrap_untrusted(text, source)


def is_blocked(verdict: Any) -> bool:
    return bool(getattr(verdict, "blocked", False))


def is_clean(verdict: Any) -> bool:
    return bool(getattr(verdict, "clean", False))


def risk_name(verdict: Any) -> str:
    risk = getattr(verdict, "risk", None)
    name = getattr(risk, "name", None)
    return str(name).lower() if name is not None else "unknown"


def signal_names(verdict: Any) -> list[str]:
    return [str(getattr(signal, "value", signal)) for signal in getattr(verdict, "signals", ())]


def describe(verdict: Any) -> str:
    summary = getattr(verdict, "summary", None)
    return summary() if callable(summary) else str(verdict)


def excerpts(verdict: Any, limit: int = 4) -> list[str]:
    return [str(item) for item in getattr(verdict, "excerpts", ())][:limit]
