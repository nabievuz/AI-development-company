
from __future__ import annotations

import json
from pathlib import Path


def _expected(fixtures: Path) -> dict[str, float]:
    data = json.loads((fixtures / "budget_requests.json").read_text(encoding="utf-8"))
    remaining = float(data.get("total_cap_usd", 0))
    requests = list(data.get("requests", []))

    allocations: dict[str, float] = {str(r.get("dept")): 0.0 for r in requests}
    tiers = sorted({r.get("priority_tier") for r in requests}, key=lambda t: (t is None, t))

    for tier in tiers:
        tier_reqs = [r for r in requests if r.get("priority_tier") == tier]
        tier_total = sum(float(r.get("requested_usd", 0)) for r in tier_reqs)
        if tier_total <= 0:
            continue
        if remaining <= 0:
            break
        if remaining >= tier_total:
            for r in tier_reqs:
                allocations[str(r.get("dept"))] = float(r.get("requested_usd", 0))
            remaining -= tier_total
        else:
            for r in tier_reqs:
                share = remaining * float(r.get("requested_usd", 0)) / tier_total
                allocations[str(r.get("dept"))] = share
            remaining = 0.0
            break

    return allocations


def verify(submission: dict, fixtures: Path) -> float:
    expected = _expected(fixtures)
    total_expected = sum(expected.values())
    if total_expected <= 0:
        return 0.0

    reported = submission.get("allocations", {})
    if not isinstance(reported, dict):
        return 0.0

    error = 0.0
    for dept, expected_amount in expected.items():
        got = reported.get(dept, 0)
        try:
            got_amount = float(got)
        except (TypeError, ValueError):
            got_amount = 0.0
        error += abs(got_amount - expected_amount)

    return max(0.0, min(1.0, 1.0 - error / total_expected))
