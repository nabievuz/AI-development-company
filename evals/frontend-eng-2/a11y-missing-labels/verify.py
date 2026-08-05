
from __future__ import annotations

import re
from pathlib import Path


def _attrs(tag: str) -> dict[str, str]:
    return dict(re.findall(r'([a-zA-Z-]+)="([^"]*)"', tag))


def _violations(fixtures: Path) -> set[str]:
    html = (fixtures / "form.html").read_text(encoding="utf-8")

    label_ids = set(re.findall(r'<label\b[^>]*\bfor="([^"]+)"', html))

    violations: set[str] = set()


    for tag in re.findall(r"<input\b[^>]*>", html):
        attrs = _attrs(tag)
        el_id = attrs.get("id")
        if not el_id:
            continue
        has_label = el_id in label_ids
        has_aria = "aria-label" in attrs or "aria-labelledby" in attrs
        if not has_label and not has_aria:
            violations.add(el_id)


    for tag in re.findall(r"<img\b[^>]*>", html):
        attrs = _attrs(tag)
        el_id = attrs.get("id")
        if not el_id:
            continue
        if "alt" not in attrs:
            violations.add(el_id)


    for tag_attrs, content in re.findall(r"<button([^>]*)>(.*?)</button>", html, re.S):
        attrs = _attrs(tag_attrs)
        el_id = attrs.get("id")
        if not el_id:
            continue
        text = re.sub(r"<[^>]+>", "", content).strip()
        has_aria = "aria-label" in attrs
        if not text and not has_aria:
            violations.add(el_id)

    return violations


def verify(submission: dict, fixtures: Path) -> float:
    expected = _violations(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("violations", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, min(1.0, (hits - false_pos) / len(expected)))
