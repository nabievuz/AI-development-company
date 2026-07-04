"""Deterministic verifier — growth-marketer / channel-roi-ranking."""
from __future__ import annotations

import json
from pathlib import Path


def _analyse(fixtures: Path) -> tuple[str, str]:
    channels = json.loads((fixtures / "channels.json").read_text(encoding="utf-8"))["channels"]
    best_name, best_roas = None, float("-inf")
    worst_name, worst_roas = None, float("inf")
    for ch in channels:
        spend = ch["spend"]
        if spend <= 0:
            continue
        roas = ch["revenue"] / spend
        if roas > best_roas:
            best_roas, best_name = roas, ch["name"]
        if roas < worst_roas:
            worst_roas, worst_name = roas, ch["name"]
    return str(best_name), str(worst_name)


def verify(submission: dict, fixtures: Path) -> float:
    expected_scale, expected_cut = _analyse(fixtures)
    credit = 0.0
    if str(submission.get("scale_channel", "")).strip() == expected_scale:
        credit += 0.5
    if str(submission.get("cut_channel", "")).strip() == expected_cut:
        credit += 0.5
    return credit
