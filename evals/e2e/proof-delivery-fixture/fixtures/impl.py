from __future__ import annotations


def counted(events: list[dict]) -> int:
    return sum(
        1
        for e in events
        if e.get("merged_pr") and str(e.get("ci_status", "")).lower() == "green"
    )


def all_gates_closed(statuses: dict[str, str]) -> bool:
    return all(statuses.get(f"gate-{g}") == "closed" for g in range(1, 7))
