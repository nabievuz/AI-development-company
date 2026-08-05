
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_TOP_LEVEL = ("name", "image", "description", "sku")
REQUIRED_OFFER_FIELDS = ("price", "priceCurrency")


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _invalid_fields(fixtures: Path) -> set[str]:
    data = json.loads(
        (fixtures / "product.jsonld.json").read_text(encoding="utf-8")
    )
    invalid: set[str] = set()

    for field in REQUIRED_TOP_LEVEL:
        if field not in data or _is_empty(data.get(field)):
            invalid.add(field)

    offers = data.get("offers", {})
    if not isinstance(offers, dict):
        offers = {}
    for field in REQUIRED_OFFER_FIELDS:
        if field not in offers or _is_empty(offers.get(field)):
            invalid.add(f"offers.{field}")

    return invalid


def verify(submission: dict, fixtures: Path) -> float:
    expected = _invalid_fields(fixtures)
    if not expected:
        return 0.0

    reported = submission.get("invalid_fields", [])
    if not isinstance(reported, list):
        return 0.0
    reported_set = {str(x) for x in reported}

    hits = len(reported_set & expected)
    false_pos = len(reported_set - expected)
    return max(0.0, (hits - false_pos) / len(expected))
