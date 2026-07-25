#!/usr/bin/env python3
"""kill_switch_drill.py — ORGANISM WS4 HEARTBEAT kill-switch + safety-rail drill (DAS-1478).

GATE-4 Testing for the WS4 heartbeat. This is the end-to-end DRILL that proves the
scheduler `--tick` (``scripts/loop_controller.py --tick``) can never run away: every
ADR-0027 safety invariant is exercised against a live, feature-flag-enabled tick in
an isolated temp workspace, and the never-auto-approve law is checked by scanning a
synthetic event log for zero gate/approval violations.

**Activate, don't duplicate (ADR-0027).** The drill imports and calls the real
brakes — ``loop_controller.tick``, ``break_glass``, ``flow_router``, the cost-ledger,
``check_loop_mode`` — never a re-implemented copy. It adds no controller logic; it is
purely an executable proof harness.

Six rails, one pass (:func:`run_all_drills`):
  * SI-3  break-glass kill-switch — an engaged override forces the tick to idle, and
          the override AUTO-EXPIRES after 60 min so dispatch resumes (bounded stop).
  * SI-4  quiet hours — a tick inside the quiet window idles.
  * SI-5  per-day budget cap — seeded spend over the cap idles the tick; the per-run
          cap is asserted present as a hard ceiling in config/budgets.yaml.
  * SI-6  max_concurrent_waves — a wave already in flight idles a new dispatch tick.
  * SI-7  never-auto-approve — the decision alphabet is the closed {dispatch, validate,
          idle} set (no approve/answer action), a synthetic event log scans to ZERO
          gate/approval violations, a seeded auto-approval is DETECTED (scanner has
          teeth), and the tick writes NOTHING to the store (it cannot sign a gate).
  * SI-2  check_loop_mode.py stays exit 0 — the loop never flips to live/auto_apply.

The cheap unit variant runs on every PR via ``tests/test_kill_switch_drill.py``
(and the ``--smoke`` step in ci.yml); the expensive >=20-iteration accumulation runs
on the scheduled ``.github/workflows/kill-switch-drill.yml`` job. All drills run in a
throwaway temp workspace — NEVER board/.events.jsonl, config/loop.yaml, or the real
config/features.yaml.

Exit codes: 0 = every rail held on every iteration, 1 = a rail failed, 2 = usage error.

Usage:
    python3 scripts/kill_switch_drill.py --smoke            # cheap: 1 pass (CI, every PR)
    python3 scripts/kill_switch_drill.py --iterations 30    # expensive: 30 passes (scheduled)
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Make scripts/ importable (same pattern as every other entrypoint).
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import loop_controller as lc  # noqa: E402
from flow_router import DECISIONS, DISPATCH, IDLE, VALIDATE  # noqa: E402

_ROOT = _SCRIPTS.parent
_REAL_LOOP_CONFIG = _ROOT / "config" / "loop.yaml"
_REAL_BUDGETS = _ROOT / "config" / "budgets.yaml"

# A fixed noon UTC anchor — outside the default 22:00–06:00 quiet window.
_T_NOON = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
# 23:30 UTC — inside the default quiet window.
_T_QUIET = datetime(2026, 7, 3, 23, 30, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# SI-7 — gate/approval violation scanner (the load-bearing "zero violations" proof).
# ---------------------------------------------------------------------------

#: Human actors permitted to grant a gate/approval/interrupt-answer (SI-7
#: allow-list; DAS-1637). Everything else — including an unrecognised, blank,
#: or absent actor — is a violation. This inverts the historic deny-list
#: (`AUTO_ACTORS`, retained below only for the docstring reference/back-compat
#: import): in DasLab every actor except the Founder is an agent, so "not on
#: the deny-list" silently passed agent role-keys (`qa-lead`, `orchestrator`,
#: `cto`, `claude`, `subagent`, …) through as human. Fail-closed is the point
#: of the inversion — an actor this scanner has never heard of must NOT read
#: as human by default.
#:
#: Where this list lives, and why here and not a config file: this ticket's
#: zone lock is `scripts/` + `tests/` (governance/config edits are out of
#: scope for a QA-Eng ticket), which already settles it for DAS-1637. On the
#: merits, a code constant in reviewed engineering source is arguably the
#: RIGHT home for something this security-critical anyway — a config-file
#: entry can be edited by a lower-ceremony path than a PR+CI-gated code
#: change, and an extra entry here is exactly the kind of change (widening
#: who may sign a gate) that should cost a review, not a one-line YAML edit.
#: If DasLab later needs this list managed outside engineering review (e.g.
#: rotating multiple human operators without a code deploy), promote it to a
#: governed config file (e.g. `config/rbac.yaml`, which already models
#: role/actor policy) behind its own ADR — do not silently soften the bar.
ALLOWED_HUMAN_ACTORS: frozenset[str] = frozenset({"founder"})

#: DEPRECATED (DAS-1637) — kept only so any external importer sees a clear
#: pointer to the replacement; no longer consulted by the scanner below.
AUTO_ACTORS: frozenset[str] = frozenset(
    {
        "",
        "auto",
        "heartbeat",
        "loop_controller",
        "loop-controller",
        "flow_router",
        "flow-router",
        "scheduler",
        "cron",
        "cron_tick",
        "system",
        "bot",
        "agent",
        "daslab-cycle",
    }
)

#: Decision/status strings that clearly mean "NOT granted" (DAS-1638). This is
#: the opposite shape from the old `_GRANTED` allow-list it replaces: `_GRANTED`
#: matched a closed list of grant verbs, so an unrecognised verb — `accepted`,
#: `ok`, `signed_off` — silently read as "not granted" and an agent-signed
#: approval carrying it passed clean. Inverting to "clearly-not-granted" fails
#: closed the same direction DAS-1637 fixed for actors: an unknown decision
#: word is now treated as GRANTED, not as safe-by-default. A genuine rejection
#: (`decision: "rejected"`) or an explicitly-still-open item (`pending`, an
#: interrupt-card's `status: "open"`) must NOT flag — those are real,
#: unambiguous "not granted" states, so they are the only things on this list.
_NOT_GRANTED = frozenset({
    "rejected", "denied", "declined", "revoked", "withdrawn",
    "pending", "deferred", "blocked", "waiting",
    "open", "unanswered", "unresolved", "raised",
})

#: DEPRECATED (DAS-1638) — kept only so an external importer sees a clear
#: pointer to the replacement; no longer consulted by the scanner below.
_GRANTED = frozenset({"approved", "signed", "passed", "granted", "answered", "resumed"})

#: `config_write` key spellings that name the heartbeat kill-switch flag.
#: Deliberately narrow (DAS-1638 sequencing note): `config_write` is not yet a
#: producer type in `dgox.events._VALID_EVENT_TYPES` (re-checked as part of
#: this ticket — still true), so there is no schema to derive further key
#: spellings from. A dotted `features.heartbeat_enabled` form is a plausible
#: future spelling but is DEFERRED rather than guessed — see the ticket log.
_HEARTBEAT_FLAG_KEYS = frozenset({"heartbeat_enabled"})

#: Event-type aliases (DAS-1638): `event_type` was the one field the SI-7
#: scanner never normalised, even though actor and decision both are — so
#: `GATE_CHECK`, `gate_decision`, or `aadl_gate` carrying an agent-approved
#: GATE-5 slipped past the `et in (...)` membership check below. Every key is
#: matched after lowercase+strip; the value is the canonical spelling the rest
#: of this module compares against.
_EVENT_TYPE_ALIASES: dict[str, str] = {
    "gate_check": "gate_check",
    "gate-check": "gate_check",
    "gatecheck": "gate_check",
    "gate_decision": "gate_check",
    "gate-decision": "gate_check",
    "gatedecision": "gate_check",
    "aadl_gate": "gate_check",
    "aadl-gate": "gate_check",
    "aadlgate": "gate_check",
    "approval": "approval",
    "interrupt_answer": "interrupt_answer",
    "interrupt-answer": "interrupt_answer",
    "interruptanswer": "interrupt_answer",
    "interrupt_card": "interrupt_card",
    "interrupt-card": "interrupt_card",
    "interruptcard": "interrupt_card",
    "config_write": "config_write",
    "config-write": "config_write",
    "configwrite": "config_write",
}


def _normalize_event_type(value: Any) -> str:
    """Canonicalise an `event_type` spelling (DAS-1638).

    Lowercases and strips, then maps known aliases (case/hyphen/underscore
    variants, plus the `gate_decision` / `aadl_gate` spellings a real
    producer uses today) onto the canonical name the rest of this module
    compares against. An unrecognised event type passes through unchanged —
    this function only closes known-alias gaps, it does not invent new
    membership.
    """
    raw = str(value or "").strip().lower()
    return _EVENT_TYPE_ALIASES.get(raw, raw)


def _actor_is_human(value: Any) -> bool:
    """True only if *value* names an actor on :data:`ALLOWED_HUMAN_ACTORS` (SI-7).

    Fail-closed: an unrecognised, blank, or absent actor is NOT human. This is
    the entire point of the DAS-1637 allow-list inversion — there is no
    "neither list matches, so pass" path.
    """
    return str(value or "").strip().lower() in ALLOWED_HUMAN_ACTORS


def _actor_is_auto(value: Any) -> bool:
    """Back-compat shim (DAS-1637): "not human" under the new allow-list."""
    return not _actor_is_human(value)


def _approval_value_is_auto(value: Any) -> bool:
    """True if an ``approval`` field is an auto-approval (``auto`` / ``auto:*``)."""
    return str(value or "").strip().lower().startswith("auto")


def _truthy(value: Any) -> bool:
    """Loose truthiness for a YAML/JSON-ish scalar (``true`` / ``"true"`` / ``1``)."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


#: Recognised falsy scalar spellings (DAS-1638) — the only values a
#: heartbeat-flag write is allowed to resolve to WITHOUT flagging. Anything
#: else — an unrecognised string, ``None``, a non-scalar — is unparseable and
#: fails closed (see :func:`_parse_flag_bool`).
_FALSY_STRINGS = frozenset({"false", "0", "no", "off"})
_TRUTHY_STRINGS = frozenset({"true", "1", "yes", "on"})


def _parse_flag_bool(value: Any) -> bool | None:
    """Parse a config-write value as ON (``True``) / OFF (``False``) / unparseable (``None``).

    DAS-1638: the old ``_truthy`` helper only ever answered "is this
    truthy?", so anything it did not recognise — ``"enabled"``, ``None``, a
    bare key with no value at all — silently read as "not truthy" and the
    flip rule failed OPEN (treated it as a pass). This helper instead
    returns a real three-way verdict so the caller can fail CLOSED: ``None``
    means "cannot be classified" and must be treated as a violation, not a
    clean value.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, int | float):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _TRUTHY_STRINGS:
            return True
        if s in _FALSY_STRINGS:
            return False
        return None
    # list/dict/other non-scalar — cannot be classified.
    return None


def _resolved_flag_value(d: dict[str, Any]) -> Any:
    """Resolve a write's intended value, preferring ``value`` over ``new_value`` (DAS-1638).

    Fixes the ``ev.get("value", ev.get("new_value"))`` wart: that only falls
    back to ``new_value`` when the ``value`` key is **absent**, so
    ``{"value": None, "new_value": True}`` read as "no value" and slipped
    through as not-a-flip. This falls back whenever ``value`` is absent OR
    explicitly ``None``.
    """
    if "value" in d and d["value"] is not None:
        return d["value"]
    return d.get("new_value")


def _config_write_flips_heartbeat_on(ev: dict[str, Any]) -> bool:
    """True if a ``config_write`` event on ``heartbeat_enabled`` is a violation (DAS-1638).

    Fails CLOSED: once a write is confirmed to target the heartbeat flag (by
    key, or nested under ``changes``), a value that cannot be parsed
    unambiguously as OFF is treated as a violation — this covers a missing
    value, an explicit ``None`` with no usable ``new_value`` fallback, an
    unrecognised string (``"enabled"``), and any non-scalar. Only a value
    that parses cleanly to ``False`` is safe — turning the switch OFF is
    never the dangerous direction (DAS-1637's own acceptance case).

    Recognised shapes are deliberately narrow (DAS-1638 sequencing note,
    re-checked as part of this ticket — still true): ``config_write`` is not
    yet a producer type in ``dgox.events._VALID_EVENT_TYPES``, so there is no
    schema to derive further shapes from.
      - ``{"key"|"field"|"setting": "heartbeat_enabled", "value"|"new_value": <scalar>}``
      - ``{"changes": {"heartbeat_enabled": <scalar>, ...}}``
    A dotted ``features.heartbeat_enabled`` key and a ``path``+``content``
    file-write shape are plausible future spellings but are explicitly
    DEFERRED rather than guessed — see the ticket log. `event_type`
    case/spelling variants (``CONFIG_WRITE``, ``config-write``, …) are
    already covered by :func:`_normalize_event_type`, shared with the rest of
    the scanner.
    """
    key = str(ev.get("key") or ev.get("field") or ev.get("setting") or "").strip().lower()
    if key in _HEARTBEAT_FLAG_KEYS:
        parsed = _parse_flag_bool(_resolved_flag_value(ev))
        if parsed is not False:  # True (ON) or None (unparseable) both flag.
            return True

    changes = ev.get("changes")
    if isinstance(changes, dict):
        for flag_key in _HEARTBEAT_FLAG_KEYS:
            if flag_key in changes:
                parsed = _parse_flag_bool(changes[flag_key])
                if parsed is not False:
                    return True
    return False


def scan_gate_approval_violations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the events that record an AUTO-approved gate or interrupt-card (SI-7).

    A violation is any event in which a gate was signed, an approval was
    granted, or an interrupt-card was answered/resumed by an actor **not on**
    :data:`ALLOWED_HUMAN_ACTORS` (fail-closed: unrecognised/absent ⇒
    violation), or with an ``approval: auto*`` / ``auto_approved: true``
    marker, or — DAS-1637 — a ``config_write`` that turns ``heartbeat_enabled``
    ON. A PENDING gate (awaiting the Founder) and a genuine human approval
    (`approved_by: founder`) are NOT violations — the scan proves the
    heartbeat never advances past a human gate.

    DAS-1638 — grant detection is a **"clearly-not-granted" set**
    (:data:`_NOT_GRANTED`), not a grant-verb allow-list: an unrecognised
    decision word (``accepted``, ``ok``, ``signed_off``, …) is now treated as
    GRANTED, fail-closed the same direction DAS-1637 fixed for actors. Only an
    unambiguous non-grant (`rejected`, `pending`, an interrupt-card's
    `open`/`unanswered`, …) reads as safe. ``event_type`` is normalised
    (:func:`_normalize_event_type`) the same way actor and decision already
    were, so ``GATE_CHECK`` / ``gate_decision`` / ``aadl_gate`` no longer
    dodge the membership check below.

    Boundary-case reasoning for the decision field (DAS-1638): ``decision:
    ""``, a missing ``decision`` key, ``decision: None``, and a non-string
    decision (e.g. a stray ``True``/int/dict) all normalise, via
    ``str(x or "").strip().lower()``, to a string that is not in
    :data:`_NOT_GRANTED` — none of them is an unambiguous "not granted"
    signal, so all of them fall on the GRANTED side of the fail-closed line,
    same as an unrecognised word. This only matters when the *actor* is also
    non-human: a human-attributed event (``approved_by: founder``) never
    flags regardless of how ambiguous the decision text is, because the
    violation condition below is an AND of "not clearly-rejected" with "actor
    not on the human allow-list" — an event with a genuinely missing decision
    AND a genuinely missing actor is exactly the shape a Founder-facing
    fail-closed gate should refuse to wave through as clean.

    Pure and failure-isolated: non-dict entries are skipped, never raised on. An
    empty list means the log is clean (the SI-7 acceptance: count == 0).
    """
    violations: list[dict[str, Any]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        et = _normalize_event_type(ev.get("event_type"))
        approver = ev.get("approved_by", ev.get("operator"))
        approval_val = ev.get("approval")
        decided = str(ev.get("decision") or ev.get("status") or "").strip().lower()

        auto = False
        if et in ("approval", "gate_check", "interrupt_answer", "interrupt_card"):
            auto = (
                bool(ev.get("auto_approved"))
                or _approval_value_is_auto(approval_val)
                # NOT clearly-rejected/pending ⇒ treated as granted (fail
                # closed on an unrecognised verb) when the actor isn't human.
                or (decided not in _NOT_GRANTED and not _actor_is_human(approver))
                # An `approval` event is a grant by definition; non-human ⇒ violation.
                or (et == "approval" and not _actor_is_human(approver))
            )

        # An interrupt-card answered/resumed by a non-allow-listed actor.
        answered_by = ev.get("interrupt_answered_by") or ev.get("resumed_by")
        if answered_by is not None and not _actor_is_human(answered_by):
            auto = True

        # DAS-1637: an explicit rule for the flag-flip itself — no actor gets a
        # free pass here, human or not, because this scanner only ever sees a
        # log entry, not who ran the Founder-only flip procedure.
        if et == "config_write" and _config_write_flips_heartbeat_on(ev):
            auto = True

        if auto:
            violations.append(ev)
    return violations


def decision_alphabet_is_closed() -> bool:
    """True if the router decision set is exactly {dispatch, validate, idle} (SI-7).

    Structural proof: there is no ``approve``/``answer``/``sign`` action in the
    closed set, so the router cannot represent signing a gate or answering an
    interrupt-card.
    """
    forbidden = {"approve", "answer", "sign", "auto_approve", "grant"}
    return frozenset({DISPATCH, VALIDATE, IDLE}) == DECISIONS and not DECISIONS & forbidden


# ---------------------------------------------------------------------------
# Isolated-config writers (a drill NEVER touches real config).
# ---------------------------------------------------------------------------


def _write_flags(work_dir: Path, *, enabled: bool) -> Path:
    path = work_dir / "features.yaml"
    path.write_text(f"heartbeat_enabled: {'true' if enabled else 'false'}\n", encoding="utf-8")
    return path


def _write_schedule(work_dir: Path, *, start: str = "22:00", end: str = "06:00",
                    max_concurrent: int = 1) -> Path:
    path = work_dir / "schedule.yaml"
    path.write_text(
        f"max_concurrent_waves: {max_concurrent}\n"
        "never_auto_approve: true\n"
        "quiet_hours:\n"
        f"  start: '{start}'\n"
        f"  end: '{end}'\n"
        "  timezone: UTC\n",
        encoding="utf-8",
    )
    return path


def _write_budgets(work_dir: Path, *, per_day_usd: float) -> Path:
    """Write an isolated budgets.yaml fixture.

    DAS-1639: the tick's SI-5 per-day rail (``loop_controller._per_day_budget_exceeded``)
    reads ``mustaqil.caps.per_day.max_cost_usd`` — the MUSTAQIL runner's own hard
    dispatch ceiling — not the top-level ``caps.per_day`` block, which
    ``config/budgets.yaml`` itself documents as informational-only. This fixture
    writes ``per_day_usd`` under ``mustaqil.caps.per_day`` so the drill exercises
    the same key the rail actually consults. The top-level ``caps:`` block is
    also written (mirroring the real SSOT's shape) so any drill that separately
    inspects the org-level block still finds one, but it plays no role in the
    tick decision the drills assert on.

    DAS-1641/R3: since ``_per_day_budget_exceeded`` now threads this fixture's
    own path into ``aggregate_spans`` for tier pricing (instead of always
    resolving pricing from the real ``config/budgets.yaml``), this isolated
    fixture must carry its own ``tiers:`` block or every span it prices comes
    back at $0.00 and the SI-5 drill can never observe a breach. Values mirror
    ``config/budgets.yaml``'s real pricing (only ``opus`` is exercised by
    ``drill_budget_caps``, but all three are written for parity with the real
    SSOT's shape).
    """
    path = work_dir / "budgets.yaml"
    path.write_text(
        "caps:\n"
        f"  per_run:\n    max_cost_usd: {per_day_usd}\n"
        f"  per_day:\n    max_cost_usd: {per_day_usd}\n"
        "mustaqil:\n"
        "  caps:\n"
        f"    per_day:\n      max_cost_usd: {per_day_usd}\n"
        "tiers:\n"
        "  opus:\n"
        "    input_per_1m: 5.00\n"
        "    cached_input_per_1m: 0.50\n"
        "    output_per_1m: 25.00\n"
        "  sonnet:\n"
        "    input_per_1m: 3.00\n"
        "    cached_input_per_1m: 0.30\n"
        "    output_per_1m: 15.00\n"
        "  haiku:\n"
        "    input_per_1m: 1.00\n"
        "    cached_input_per_1m: 0.10\n"
        "    output_per_1m: 5.00\n",
        encoding="utf-8",
    )
    return path


def _tick(work_dir: Path, *, schedule: Path, budgets: Path, flags: Path, events: Path,
          trigger: str, pending: bool, now: datetime) -> dict[str, Any]:
    """Run one real ``loop_controller.tick`` against isolated config (never real config)."""
    return lc.tick(
        schedule_path=schedule,
        loop_config=_REAL_LOOP_CONFIG,          # read-only; SI-2 asserts it is untouched
        experiments=work_dir / "experiments",
        metrics_history=work_dir / ".metrics-history.jsonl",
        events_path=events,
        budgets_path=budgets,
        feature_flags_path=flags,
        trigger=trigger,
        pending_work=pending,
        now=now,
    )


# ---------------------------------------------------------------------------
# The six rail drills. Each returns {"name", "ok", ...detail}.
# ---------------------------------------------------------------------------


def drill_break_glass(work_dir: Path) -> dict[str, Any]:
    """SI-3: an engaged break-glass halts the tick; auto-expiry restores dispatch."""
    from break_glass import append_event, build_activation, fmt_ts

    events = work_dir / "bg.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    append_event(
        build_activation(
            activation_id="BG-DRILL-001",
            reason="kill-switch drill",
            operator="sre-eng",
            created_at=fmt_ts(_T_NOON),
        ),
        path=events,
    )

    engaged = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="ticket_created", pending=True, now=_T_NOON)
    # 90 minutes later the 60-min override has auto-expired.
    expired = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="ticket_created", pending=True, now=_T_NOON + timedelta(minutes=90))

    ok = (
        engaged["safety_rails"]["break_glass_active"] is True
        and engaged["decision"]["action"] == IDLE
        and expired["safety_rails"]["break_glass_active"] is False
        and expired["decision"]["action"] == DISPATCH
    )
    return {
        "name": "SI-3 break_glass_kill_switch",
        "ok": ok,
        "engaged_action": engaged["decision"]["action"],
        "expired_action": expired["decision"]["action"],
    }


def drill_quiet_hours(work_dir: Path) -> dict[str, Any]:
    """SI-4: a dispatch tick inside the quiet window idles."""
    events = work_dir / "qh.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    quiet = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                  trigger="ticket_created", pending=True, now=_T_QUIET)
    ok = quiet["safety_rails"]["in_quiet_hours"] is True and quiet["decision"]["action"] == IDLE
    return {"name": "SI-4 quiet_hours", "ok": ok, "action": quiet["decision"]["action"]}


def drill_budget_caps(work_dir: Path) -> dict[str, Any]:
    """SI-5: per-day spend over the cap idles the tick; per-run cap is a hard ceiling."""
    import yaml
    from dgox.events import EventStore, build_span

    events = work_dir / "budget.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    # Tiny per-day cap; one opus span (priced from the REAL config) blows past it.
    budgets = _write_budgets(work_dir, per_day_usd=0.01)

    store = EventStore(events)
    store.append(
        build_span(
            ticket_id="DAS-DRILL",
            span_id="span-budget-1",
            parent_span_id=None,
            kind="invoke_agent",
            agent_name="qa-lead",
            model="opus",                 # $5.00 / 1M input tokens (config/budgets.yaml)
            start="2026-07-03T12:00:00Z",
            end="2026-07-03T12:00:01Z",
            created_at="2026-07-03T12:00:01Z",
            input_tokens=1_000_000,       # ⇒ ~$5.00 estimated cost ≫ $0.01 cap
            output_tokens=0,
            run_id="run-budget",
        )
    )

    over = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                 trigger="cron_tick", pending=True, now=_T_NOON)

    # Per-run cap presence in the REAL SSOT. DAS-1641/R1: this reads
    # `mustaqil.caps` — the MUSTAQIL runner's OWN caps — not the top-level
    # `caps:` block. `config/budgets.yaml` documents the top-level block as
    # informational-only (not a blocking gate until C1 is promoted); ADR-0027
    # SI-5 (`docs/adr/0027-scheduler-safety.md`) is explicit that the
    # heartbeat treats `mustaqil.caps` as its hard dispatch ceiling
    # *regardless of the org-wide gate promotion state* — a self-imposed
    # budget stricter than, and independent of, the shared informational
    # gate. Reading the top-level block here (as this line used to) checked
    # the wrong cap: it would pass even if `mustaqil.caps` were absent or
    # malformed, i.e. even if the actual SI-5 ceiling did not exist.
    real = yaml.safe_load(_REAL_BUDGETS.read_text(encoding="utf-8")) or {}
    _real_mustaqil_caps = (real.get("mustaqil") or {}).get("caps") or {}
    per_run = (_real_mustaqil_caps.get("per_run") or {})
    per_day = (_real_mustaqil_caps.get("per_day") or {})
    per_run_ok = (
        float(per_run.get("max_cost_usd", 0) or 0) > 0
        and int(per_run.get("max_input_tokens", 0) or 0) > 0
        and int(per_run.get("max_output_tokens", 0) or 0) > 0
        and float(per_day.get("max_cost_usd", 0) or 0) >= float(per_run.get("max_cost_usd", 0) or 0)
    )

    ok = (
        over["safety_rails"]["per_day_budget_exceeded"] is True
        and over["decision"]["action"] == IDLE
        and per_run_ok
    )
    return {
        "name": "SI-5 budget_caps",
        "ok": ok,
        "per_day_action": over["decision"]["action"],
        "per_run_ceiling_ok": per_run_ok,
    }


def drill_max_concurrent(work_dir: Path) -> dict[str, Any]:
    """SI-6: a wave already in flight (run_start with no run_end) idles a dispatch tick."""
    from dgox.events import EventStore, build_run_start

    events = work_dir / "concurrent.events.jsonl"
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir, max_concurrent=1)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    # One open run: run_start with no matching run_end ⇒ a wave is in flight.
    EventStore(events).append(
        build_run_start(
            ticket_id="DAS-DRILL",
            run_id="run-in-flight",
            goal="organism-ws4-heartbeat",
            engine_version="1.2.0",
            created_at="2026-07-03T11:59:00Z",
        )
    )

    stacked = _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
                    trigger="cron_tick", pending=True, now=_T_NOON)
    # The router degrades a would-be dispatch to idle citing SI-6.
    ok = stacked["decision"]["action"] == IDLE and "SI-6" in stacked["decision"]["reason"]
    return {
        "name": "SI-6 max_concurrent_waves",
        "ok": ok,
        "action": stacked["decision"]["action"],
        "reason": stacked["decision"]["reason"],
    }


def _synthetic_event_log() -> list[dict[str, Any]]:
    """A clean synthetic event log: real work, a PENDING gate, an UNANSWERED interrupt,
    and a genuine HUMAN approval — none of which is an auto-approval (SI-7)."""
    from dgox.events import build_routing_decision, build_run_end, build_run_start

    return [
        build_run_start(
            ticket_id="DAS-DRILL", run_id="run-1", goal="organism-ws4-heartbeat",
            engine_version="1.2.0", created_at="2026-07-03T12:00:00Z",
        ),
        build_routing_decision(
            ticket_id="DAS-DRILL", from_status="todo", to_status="in_progress",
            assignee="qa-lead", model="opus", reason="drill routing",
            confidence=0.9, policy_checks=["aadl_predecessor_gate_closed"],
            fallback="block_and_escalate_to_cto", created_at="2026-07-03T12:00:01Z",
            run_id="run-1",
        ),
        # A gate awaiting the Founder — PENDING, not granted → not a violation.
        {"event_type": "gate_check", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:02Z", "gate": "GATE-5",
         "decision": "pending", "approved_by": ""},
        # An interrupt-card raised, not yet answered → not a violation.
        {"event_type": "interrupt_card", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:03Z", "status": "open"},
        # A genuine HUMAN approval → not a violation.
        {"event_type": "approval", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:00:04Z", "approval": "human:founder",
         "approved_by": "founder", "decision": "approved"},
        build_run_end(
            ticket_id="DAS-DRILL", run_id="run-1", outcome="success", model="opus",
            merged_pr="PR-1", ci_status="green", t7_pass=True, t7_score=0.95,
            created_at="2026-07-03T12:05:00Z",
        ),
    ]


def drill_never_auto_approve(work_dir: Path) -> dict[str, Any]:
    """SI-7: closed decision alphabet, zero violations in a clean log, scanner has teeth,
    and a live tick writes NOTHING to the store (it cannot sign a gate)."""
    flags = _write_flags(work_dir, enabled=True)
    sched = _write_schedule(work_dir)
    budgets = _write_budgets(work_dir, per_day_usd=500.0)

    # 1) The decision alphabet is structurally closed (no approve/answer action).
    alphabet_ok = decision_alphabet_is_closed()

    # 2) A clean synthetic event log scans to ZERO gate/approval violations.
    clean_log = _synthetic_event_log()
    clean_violations = scan_gate_approval_violations(clean_log)

    # 3) The scanner has teeth: a seeded auto-approval is detected (a false-clean
    #    scanner would silently pass every drill — this positive control prevents it).
    dirty_log = [
        *clean_log,
        {"event_type": "approval", "ticket_id": "DAS-DRILL",
         "created_at": "2026-07-03T12:06:00Z", "approval": "auto",
         "approved_by": "heartbeat", "decision": "approved"},
    ]
    dirty_violations = scan_gate_approval_violations(dirty_log)

    # 4) A live tick over a real event store writes NOTHING (heartbeat cannot sign).
    import contextlib

    from dgox.events import EventStore
    events = work_dir / "nse.events.jsonl"
    store = EventStore(events)
    for ev in clean_log:
        # only append events with a valid known envelope (gate_check/approval/interrupt
        # are reserved types the store accepts; the raw dicts validate fine)
        with contextlib.suppress(ValueError):
            store.append(ev)
    before = events.read_bytes() if events.exists() else b""
    for trigger in ("cron_tick", "ticket_created", "wave_completed",
                    "interrupt_answered", "after_n_runs"):
        _tick(work_dir, schedule=sched, budgets=budgets, flags=flags, events=events,
              trigger=trigger, pending=True, now=_T_NOON)
    after = events.read_bytes() if events.exists() else b""
    store_untouched = before == after
    post_violations = scan_gate_approval_violations(
        [__import_json_loads(line) for line in after.decode("utf-8").splitlines() if line.strip()]
    )

    ok = (
        alphabet_ok
        and len(clean_violations) == 0
        and len(dirty_violations) == 1
        and store_untouched
        and len(post_violations) == 0
    )
    return {
        "name": "SI-7 never_auto_approve",
        "ok": ok,
        "alphabet_closed": alphabet_ok,
        "clean_violations": len(clean_violations),
        "seeded_violation_detected": len(dirty_violations) == 1,
        "store_untouched": store_untouched,
        "post_tick_violations": len(post_violations),
    }


def __import_json_loads(line: str) -> dict[str, Any]:
    """Local json.loads shim (kept out of module import list for a tidy header)."""
    import json
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else {}
    except Exception:  # noqa: BLE001 — a corrupt line scans as no-violation
        return {}


def drill_loop_mode() -> dict[str, Any]:
    """SI-2: check_loop_mode.py stays exit 0 — the loop never flips to live/auto_apply."""
    import check_loop_mode as clm

    rc = clm.main(["--config", str(_REAL_LOOP_CONFIG)])
    return {"name": "SI-2 check_loop_mode", "ok": rc == 0, "exit_code": rc}


# ---------------------------------------------------------------------------
# One pass = all six rails, in an isolated temp workspace.
# ---------------------------------------------------------------------------


def run_all_drills(work_dir: Path) -> dict[str, Any]:
    """Run one pass of all six rail drills; return {"ok", "results"}."""
    work_dir.mkdir(parents=True, exist_ok=True)
    results = [
        drill_break_glass(work_dir),
        drill_quiet_hours(work_dir),
        drill_budget_caps(work_dir),
        drill_max_concurrent(work_dir),
        drill_never_auto_approve(work_dir),
        drill_loop_mode(),
    ]
    return {"ok": all(r["ok"] for r in results), "results": results}


def run_drills(*, iterations: int, tmp_root: Path) -> int:
    """Run ``iterations`` full drill passes; return a process exit code (0 = all held)."""
    print(f"kill-switch-drill: running {iterations} pass(es) of the 6 safety rails...")
    failures: list[str] = []
    for i in range(iterations):
        outcome = run_all_drills(tmp_root / f"pass-{i:03d}")
        status = "ok" if outcome["ok"] else "FAIL"
        rails = " ".join(f"{r['name'].split()[0]}={'ok' if r['ok'] else 'FAIL'}"
                         for r in outcome["results"])
        print(f"  pass[{i:03d}] {status}: {rails}")
        if not outcome["ok"]:
            for r in outcome["results"]:
                if not r["ok"]:
                    failures.append(f"pass[{i}] {r['name']}: {r}")

    if failures:
        sys.stderr.write(
            "kill-switch-drill FAILED:\n" + "\n".join(f"  - {f}" for f in failures) + "\n"
        )
        return 1
    print("kill-switch-drill: OK — every safety rail held on every pass "
          "(zero gate/approval violations, loop off).")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--smoke", action="store_true",
                       help="cheap CI variant: 1 full drill pass (every PR)")
    group.add_argument("--iterations", type=int, default=None,
                       help="expensive scheduled variant: run N full drill passes (>=20)")
    ap.add_argument("--keep", action="store_true", help="keep the temp drill directory (debug)")
    args = ap.parse_args(argv)

    iterations = 1 if args.smoke else (args.iterations if args.iterations is not None else 1)
    if iterations < 1:
        sys.stderr.write("--iterations must be >= 1\n")
        return 2

    tmp_root = Path(tempfile.mkdtemp(prefix="daslab-kill-switch-drill-"))
    try:
        return run_drills(iterations=iterations, tmp_root=tmp_root)
    finally:
        if not args.keep:
            import shutil
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
