#!/usr/bin/env python3
"""break_glass.py — BREAK-GLASS emergency override.

A time-limited (60-minute), scope-restricted (single rollback), audit-required
emergency override of the approval gates. Activation is appended to the
append-only DGO-X audit log (``board/.events.jsonl``) and AUTO-EXPIRES after 60
minutes — ``is_active(now)`` is false once the window passes, with no manual
deactivation needed.

It does NOT relax QONUN-5 in steady state: only a live, logged, auto-expiring
activation grants the bounded override, and every activation requires a
post-incident review within 24h (enforced by check_break_glass_review.py).

The pure builders take ``created_at`` as an argument (deterministic, testable);
only the CLI reads the wall clock — mirroring the DGO-X event-store discipline.

Library + CLI:
    python3 scripts/break_glass.py activate --reason "prod incident" --operator cto
    python3 scripts/break_glass.py status
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _paths import ROOT

WINDOW_MINUTES = 60
REVIEW_DEADLINE_HOURS = 24
ACTIVATION_EVENT = "break_glass_activation"
REVIEW_EVENT = "break_glass_review"
ALLOWED_SCOPE = "single_rollback"
DEFAULT_STORE = ROOT / "board" / ".events.jsonl"


def utcnow() -> datetime:
    """Current UTC time (the only wall-clock read in this module)."""
    return datetime.now(tz=UTC)


def parse_ts(ts: str) -> datetime | None:
    """Parse an ISO-8601 'YYYY-MM-DDTHH:MM:SSZ' timestamp into aware UTC, or None."""
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def fmt_ts(d: datetime) -> str:
    """Format a datetime as ISO-8601 UTC ending in 'Z'."""
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_activation(
    *,
    activation_id: str,
    reason: str,
    operator: str,
    created_at: str,
    scope: str = ALLOWED_SCOPE,
    window_minutes: int = WINDOW_MINUTES,
    ticket_id: str = "DAS-BREAK-GLASS",
) -> dict:
    """Build a break-glass activation event (single-rollback scope, 60-min expiry).

    Raises ValueError on a disallowed scope (the override may only ever cover a
    single rollback) or an unparseable timestamp.
    """
    if scope != ALLOWED_SCOPE:
        raise ValueError(f"break-glass scope must be {ALLOWED_SCOPE!r}; got {scope!r}")
    start = parse_ts(created_at)
    if start is None:
        raise ValueError(f"created_at must be ISO-8601 Z; got {created_at!r}")
    return {
        "event_type": ACTIVATION_EVENT,
        "ticket_id": ticket_id,
        "created_at": created_at,
        "activation_id": activation_id,
        "reason": reason,
        "operator": operator,
        "scope": scope,
        "window_minutes": window_minutes,
        "expires_at": fmt_ts(start + timedelta(minutes=window_minutes)),
        "review_required_by": fmt_ts(start + timedelta(hours=REVIEW_DEADLINE_HOURS)),
    }


def append_event(event: dict, path: Path = DEFAULT_STORE) -> None:
    """Append one JSON line to the append-only audit log (never rewrites it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        with contextlib.suppress(OSError):
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fh, fcntl.LOCK_UN)


def read_events(path: str | Path = DEFAULT_STORE) -> list[dict]:
    """Read the JSONL audit log; [] if absent. Bad lines are skipped."""
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return events


def iter_activations(events: Iterable[dict]) -> list[dict]:
    """Return the break-glass activation events from a stream."""
    return [e for e in events if e.get("event_type") == ACTIVATION_EVENT]


def active_overrides(now: datetime, path: str | Path = DEFAULT_STORE) -> list[dict]:
    """Activations whose 60-min window covers ``now`` (start <= now < expiry).

    Expiry is RECOMPUTED from created_at + window_minutes (capped at the 60-min
    policy), never trusted from a stored expires_at a forged event could inflate,
    and only single-rollback-scope activations can ever be live.
    """
    out: list[dict] = []
    for ev in iter_activations(read_events(path)):
        if str(ev.get("scope")) != ALLOWED_SCOPE:
            continue
        start = parse_ts(str(ev.get("created_at", "")))
        if start is None:
            continue
        try:
            window = min(int(ev.get("window_minutes", WINDOW_MINUTES)), WINDOW_MINUTES)
        except (TypeError, ValueError):
            window = WINDOW_MINUTES
        if start <= now < start + timedelta(minutes=window):
            out.append(ev)
    return out


def is_active(now: datetime, path: str | Path = DEFAULT_STORE) -> bool:
    """True if any break-glass override is live at ``now`` (auto-expires otherwise)."""
    return bool(active_overrides(now, path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    act = sub.add_parser("activate", help="activate a 60-min single-rollback override")
    act.add_argument("--reason", required=True)
    act.add_argument("--operator", required=True, help="human operator role key (audit)")
    act.add_argument("--id", default=None, help="activation id (default: time-based)")
    act.add_argument("--store", type=Path, default=DEFAULT_STORE)

    st = sub.add_parser("status", help="show whether an override is live now")
    st.add_argument("--store", type=Path, default=DEFAULT_STORE)

    args = ap.parse_args(argv)

    if args.cmd == "activate":
        now = utcnow()
        aid = args.id or (
            "BG-" + fmt_ts(now).translate({ord(":"): None, ord("-"): None}) + "-" + uuid.uuid4().hex[:6]
        )
        event = build_activation(
            activation_id=aid, reason=args.reason, operator=args.operator, created_at=fmt_ts(now)
        )
        append_event(event, args.store)
        print(
            f"BREAK-GLASS activated: {aid} (single rollback) — expires {event['expires_at']}, "
            f"post-incident review required by {event['review_required_by']}."
        )
        return 0

    now = utcnow()
    live = active_overrides(now, args.store)
    if live:
        ids = ", ".join(str(e.get("activation_id")) for e in live)
        print(f"BREAK-GLASS ACTIVE: {len(live)} override(s) [{ids}].")
    else:
        print("BREAK-GLASS inactive (no override within its 60-min window).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
