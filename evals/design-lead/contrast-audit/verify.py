from __future__ import annotations

import json
from pathlib import Path

AA_NORMAL_TEXT_RATIO = 4.5


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    rl, gl, bl = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1, l2 = _relative_luminance(fg_hex), _relative_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _failing_pairs(fixtures: Path) -> set[str]:
    data = json.loads((fixtures / "tokens.json").read_text(encoding="utf-8"))
    failing = set()
    for pair in data.get("pairs", []):
        ratio = _contrast_ratio(pair["fg"], pair["bg"])
        if ratio < AA_NORMAL_TEXT_RATIO:
            failing.add(str(pair["name"]))
    return failing


def verify(submission: dict, fixtures: Path) -> float:
    expected = _failing_pairs(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("failing", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
