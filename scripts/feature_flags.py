#!/usr/bin/env python3
"""feature_flags.py — latent-machine feature flags (ADR-0019, remediation P10).

Single reader for `config/features.yaml`. Flags default **OFF** (consumerless machinery
stays quiet so it cannot burn tokens), and an unknown/empty file falls back to the same
defaults. Code paths gate emission with `enabled("dgox_emit")` etc.; the /daslab-cycle
skill reads the same file before its step-5d shadow emission (`dgox_emit`) and before the
ORGANISM WS1 "pulse" run-model wiring — run-open, wave checkpoints, and run_start/run_end/
span emission at steps 0/5/6 (`organism_emit`, a SEPARATE channel from `dgox_emit`).

Usage:
    python scripts/feature_flags.py            # print the resolved flags
    from feature_flags import enabled
    if enabled("dgox_emit"): ...
"""
from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a repo dependency
    yaml = None

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES = REPO_ROOT / "config" / "features.yaml"
DEFAULTS: dict[str, bool] = {
    "dgox_emit": False,
    "t4_t7_governors": False,
    "organism_emit": False,
    "heartbeat_enabled": False,  # WS4 HEARTBEAT (ADR-0027 SI-7) — default OFF; Founder flip-only
}


def load(path: Path | None = None) -> dict[str, bool]:
    p = path or FEATURES
    if yaml is None or not p.exists():
        return dict(DEFAULTS)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return dict(DEFAULTS)
    return {**DEFAULTS, **{k: bool(v) for k, v in data.items() if k in DEFAULTS}}


def enabled(flag: str, path: Path | None = None) -> bool:
    return bool(load(path).get(flag, False))


def main(argv: list[str] | None = None) -> int:
    for k, v in load().items():
        print(f"{k} = {'on' if v else 'off'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
