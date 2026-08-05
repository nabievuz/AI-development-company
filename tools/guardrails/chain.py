#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve().parent
_BRIDGES_DIR = _HERE.parent / "mcp_bridges"

_FLAG_NAME = "ws_e_tenant_hardening"


PRESIDIO_TOOL_NAME = "mcp__presidio__analyze_text"


def _load_module(filename: str) -> ModuleType:
    path = _BRIDGES_DIR / filename
    name = f"_ws_e_guardrails_{path.stem}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _redaction():
    return _load_module("redaction.py")


def _presidio_bridge():
    return _load_module("presidio_tool_bridge.py")


def _audit_hook():
    return _load_module("audit_external_tool.py")


DEFAULT_FEATURES = _HERE.parent.parent / "config" / "features.yaml"


def flag_on(name: str = _FLAG_NAME, features_path: Path | None = None) -> bool:
    p = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not p.is_file():
        return False
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{name}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


_SUMMARY_RE = re.compile(
    r"^presidio: \d+ entit(?:y|ies)(?: \[(?P<entities>.*?)\])?"
    r"(?: \| risk: (?P<risk>[a-z_]+))? \| redacted: (?P<redacted>.*)$",
    re.DOTALL,
)

UNPARSEABLE_RISK = "unscreened"


def _parse_presidio_summary(summary: str) -> tuple[tuple[str, ...], str, str]:
    match = _SUMMARY_RE.match(summary)
    if not match:


        return (), "[REDACTED:unclassified]", UNPARSEABLE_RISK
    entities_raw = match.group("entities") or ""
    entities = tuple(e.strip() for e in entities_raw.split(",") if e.strip())
    return entities, match.group("redacted"), match.group("risk") or UNPARSEABLE_RISK


def classify_tier(entities: tuple[str, ...]) -> str:
    return "B" if entities else "M"


def policy_decide(tier: str) -> str:
    return "redact" if tier == "B" else "allow"


@dataclass(frozen=True)
class GuardResult:

    output_text: str | None
    tier: str | None
    action: str
    entities: tuple[str, ...] = field(default_factory=tuple)
    denied: bool = False
    reason: str = ""
    injection_risk: str = UNPARSEABLE_RISK


def guard(
    text: str,
    role: str,
    allowlist: dict | None = None,
    flag_override: bool | None = None,
) -> GuardResult:
    enabled = flag_on() if flag_override is None else flag_override
    if not enabled:
        return GuardResult(
            output_text=text,
            tier=None,
            action="inert-flag-off",
            entities=(),
            denied=False,
            reason=f"{_FLAG_NAME} is OFF — guardrail chain inert (byte-identical passthrough)",
        )

    hook = _audit_hook()
    effective_allowlist = allowlist if allowlist is not None else hook.load_allowlist()
    decision, reason = hook.decide(PRESIDIO_TOOL_NAME, role, effective_allowlist)
    if decision == "deny":
        return GuardResult(
            output_text=None,
            tier=None,
            action="deny",
            entities=(),
            denied=True,
            reason=reason,
        )

    presidio = _presidio_bridge()
    summary = presidio.analyze_text(text)
    entities, redacted_text, injection_risk = _parse_presidio_summary(summary)
    tier = classify_tier(entities)
    action = policy_decide(tier)
    output = redacted_text if action == "redact" else text


    scrub = _redaction()
    output = scrub.redact_then_truncate(output, cap=4000)

    return GuardResult(
        output_text=output,
        tier=tier,
        action=action,
        entities=entities,
        denied=False,
        reason=reason,
        injection_risk=injection_risk,
    )
