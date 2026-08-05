#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES = REPO_ROOT / "config" / "features.yaml"
DEFAULTS: dict[str, bool] = {
    "dgox_emit": False,
    "t4_t7_governors": False,
    "organism_emit": False,
    "heartbeat_enabled": False,


    "ws_a_tool_bridge": False,
    "ws_b_agent_sdk_runner": False,
    "ws_c_langgraph_loop": False,
    "ws_d_langfuse_lens": False,
    "ws_e_tenant_hardening": False,
    "ws_g_proof": False,
    "ws_h_control_plane": False,
    "ws_f_heartbeat": False,
    "a2a_outbound": False,
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
