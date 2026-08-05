#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

import feature_flags

FEATURES_PATH: Path = feature_flags.FEATURES


DECLARED_DEFAULTS: dict[str, bool] = {
    "dgox_emit": False,
    "t4_t7_governors": False,
    "organism_emit": False,
    "heartbeat_enabled": False,
    "ws_a_tool_bridge": False,
    "ws_b_agent_sdk_runner": False,
    "ws_c_langgraph_loop": False,
    "ws_d_langfuse_lens": False,
    "ws_e_tenant_hardening": False,
    "ws_e_openweight_ejectpath": False,
    "ws_g_proof": False,
    "ws_h_control_plane": False,
    "ws_f_heartbeat": False,
    "a2a_outbound": False,
}


COMMITTED_OVERRIDES: dict[str, bool] = {
    "organism_emit": True,
    "ws_a_tool_bridge": True,
    "ws_b_agent_sdk_runner": True,
    "ws_c_langgraph_loop": True,
    "ws_d_langfuse_lens": True,
    "ws_e_tenant_hardening": True,
    "ws_g_proof": True,
    "ws_h_control_plane": True,
    "a2a_outbound": True,
}


FLAGS_READ_OUTSIDE_FEATURE_FLAGS: frozenset[str] = frozenset({"ws_e_openweight_ejectpath"})


def expected_values() -> dict[str, bool]:
    return {flag: COMMITTED_OVERRIDES.get(flag, default) for flag, default in DECLARED_DEFAULTS.items()}


def load_committed(features_path: Path | str | None = None) -> dict[str, object]:
    path = Path(features_path) if features_path is not None else FEATURES_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping of flag -> bool")
    return data


def drift_problems(committed: dict[str, object]) -> list[str]:
    problems: list[str] = []
    expected = expected_values()

    for flag, value in COMMITTED_OVERRIDES.items():
        if flag not in DECLARED_DEFAULTS:
            problems.append(f"{flag}: listed in COMMITTED_OVERRIDES but never declared in DECLARED_DEFAULTS")
        elif value == DECLARED_DEFAULTS[flag]:
            problems.append(
                f"{flag}: COMMITTED_OVERRIDES repeats the declared default {value!r} — "
                "an override entry must record a real deviation"
            )

    for flag in feature_flags.DEFAULTS:
        if flag not in DECLARED_DEFAULTS:
            problems.append(
                f"{flag}: feature_flags.DEFAULTS knows this flag but it is undeclared here — "
                "declare its default and its committed value"
            )
        elif feature_flags.DEFAULTS[flag] != DECLARED_DEFAULTS[flag]:
            problems.append(
                f"{flag}: declared default {DECLARED_DEFAULTS[flag]!r} != "
                f"feature_flags.DEFAULTS {feature_flags.DEFAULTS[flag]!r}"
            )

    for flag in DECLARED_DEFAULTS:
        if flag not in feature_flags.DEFAULTS and flag not in FLAGS_READ_OUTSIDE_FEATURE_FLAGS:
            problems.append(
                f"{flag}: declared here but unknown to feature_flags.DEFAULTS, so "
                "feature_flags.load() silently drops its committed value"
            )

    for flag in sorted(set(committed) - set(DECLARED_DEFAULTS)):
        problems.append(
            f"{flag}: committed in the features file but undeclared in code — "
            "an undeclared flag is read by nothing and drifts silently"
        )

    for flag in sorted(set(DECLARED_DEFAULTS) - set(committed)):
        problems.append(
            f"{flag}: declared in code but absent from the features file — "
            "every flag ships an explicit committed value"
        )

    for flag in sorted(set(DECLARED_DEFAULTS) & set(committed)):
        value = committed[flag]
        if not isinstance(value, bool):
            problems.append(f"{flag}: committed value {value!r} is not a boolean")
            continue
        if value != expected[flag]:
            problems.append(
                f"{flag}: committed {value!r} != declared {expected[flag]!r} "
                f"(default {DECLARED_DEFAULTS[flag]!r}"
                + (
                    f", override {COMMITTED_OVERRIDES[flag]!r})"
                    if flag in COMMITTED_OVERRIDES
                    else ", no override declared)"
                )
                + " — flip the code declaration in the same commit as the config"
            )

    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "check_feature_flags.py — the code is the source of truth for feature-flag "
            "defaults. Fails when config/features.yaml drifts from the declared defaults "
            "and their explicitly declared overrides."
        )
    )
    ap.add_argument("--features", type=Path, default=None, help="config/features.yaml path override")
    args = ap.parse_args(argv)

    path = args.features if args.features is not None else FEATURES_PATH
    if not path.is_file():
        sys.stderr.write(f"ERROR: features file not found: {path}\n")
        return 2
    try:
        committed = load_committed(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write(f"ERROR: cannot read {path}: {exc}\n")
        return 2

    problems = drift_problems(committed)
    if problems:
        sys.stderr.write(f"FAIL: feature-flag drift ({path}):\n")
        for problem in problems:
            sys.stderr.write(f"  - {problem}\n")
        return 1

    on = sorted(flag for flag, value in expected_values().items() if value)
    print(
        f"OK: {len(DECLARED_DEFAULTS)} feature flags match their declared values "
        f"({path}). Declared default is OFF for every flag; "
        f"{len(on)} are deliberately ON: {', '.join(on)}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
