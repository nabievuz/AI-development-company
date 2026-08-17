
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dgox.created_at import CREATED_AT_FORMAT, is_valid_created_at


def _resolve_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass

    return Path(__file__).resolve().parents[2]


_ROOT = _resolve_root()


DEFAULT_STORE_PATH: Path = _ROOT / "board" / ".events.jsonl"


def utcnow() -> str:
    return datetime.now(tz=UTC).strftime(CREATED_AT_FORMAT)


_ENVELOPE_REQUIRED = frozenset({"event_type", "ticket_id", "created_at"})
_VALID_EVENT_TYPES = frozenset(
    {
        "routing_decision",
        "agent_invocation",
        "state_violation",
        "mirror_divergence",

        "gate_check",
        "approval",
        "tool_call",
        "run_start",
        "run_end",
        "wave",
        "checkpoint",
        "tool_unavailable",

        "cache_hit",

        "span",

        "ticket_completion",

        "replanned",
    }
)


def validate_envelope(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _ENVELOPE_REQUIRED:
        if field not in event or event[field] is None:
            errors.append(f"missing required field: {field!r}")
    et = event.get("event_type")
    if et is not None and et not in _VALID_EVENT_TYPES:
        errors.append(
            f"unknown event_type {et!r}; expected one of {sorted(_VALID_EVENT_TYPES)}"
        )
    tid = event.get("ticket_id")
    if tid is not None and (not isinstance(tid, str) or not tid.startswith("DAS-") or len(tid) <= 4):
        errors.append(
            f"ticket_id must be a string starting with 'DAS-'; got {tid!r}"
        )
    ca = event.get("created_at")
    if ca is not None and not is_valid_created_at(ca):
        errors.append(
            f"created_at must match the write-seam contract "
            f"{CREATED_AT_FORMAT!r} exactly (DAS-1633); got {ca!r}"
        )
    rid = event.get("run_id")
    if rid is not None and (not isinstance(rid, str) or not rid):
        errors.append(f"run_id must be a non-empty string when present; got {rid!r}")
    return errors


_ROUTING_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "from_status",
        "to_status",
        "assignee",
        "model",
        "reason",
        "confidence",
        "policy_checks",
        "fallback",
        "created_at",
    }
)


def build_routing_decision(
    *,
    ticket_id: str,
    from_status: str,
    to_status: str,
    assignee: str,
    model: str,
    reason: str,
    confidence: float,
    policy_checks: list[str],
    fallback: str,
    created_at: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "routing_decision",
        "ticket_id": ticket_id,
        "from_status": from_status,
        "to_status": to_status,
        "assignee": assignee,
        "model": model,
        "reason": reason,
        "confidence": confidence,
        "policy_checks": list(policy_checks),
        "fallback": fallback,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


def validate_routing_decision(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "routing_decision"):
        errors.append(
            f"event_type must be 'routing_decision'; got {event.get('event_type')!r}"
        )
    confidence = event.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, int | float) or not (0.0 <= float(confidence) <= 1.0)
    ):
        errors.append(
            f"confidence must be a float in [0.0, 1.0]; got {confidence!r}"
        )
    pc = event.get("policy_checks")
    if pc is not None and (not isinstance(pc, list) or not pc or not all(isinstance(s, str) for s in pc)):
        errors.append(
            "policy_checks must be a non-empty list of strings"
        )
    model = event.get("model")
    if model is not None and (not isinstance(model, str) or not model):
        errors.append("model must be a non-empty string")
    assignee = event.get("assignee")
    if assignee is not None and (not isinstance(assignee, str) or not assignee):
        errors.append("assignee must be a non-empty string")
    for field in ("from_status", "to_status", "reason", "fallback"):
        v = event.get(field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{field!r} must be a non-empty string")
    return errors


_AGENT_INVOCATION_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "role_key",
        "model",
        "workspace_id",
        "context_contract",
        "allowed_tools",
        "secrets_policy",
        "exit_contract",
        "created_at",
    }
)


def build_agent_invocation(
    *,
    ticket_id: str,
    run_id: str,
    role_key: str,
    model: str,
    workspace_id: str,
    context_contract: dict[str, Any],
    allowed_tools: list[str],
    secrets_policy: str,
    exit_contract: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    return {
        "event_type": "agent_invocation",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "role_key": role_key,
        "model": model,
        "workspace_id": workspace_id,
        "context_contract": dict(context_contract),
        "allowed_tools": list(allowed_tools),
        "secrets_policy": secrets_policy,
        "exit_contract": dict(exit_contract),
        "created_at": created_at,
    }


def validate_agent_invocation(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "agent_invocation"):
        errors.append(
            f"event_type must be 'agent_invocation'; got {event.get('event_type')!r}"
        )

    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for agent_invocation and must be a non-empty string")
    for str_field in ("role_key", "model", "workspace_id", "secrets_policy"):
        v = event.get(str_field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{str_field!r} must be a non-empty string")
    for dict_field in ("context_contract", "exit_contract"):
        v = event.get(dict_field)
        if v is not None and not isinstance(v, dict):
            errors.append(f"{dict_field!r} must be a dict")
    at = event.get("allowed_tools")
    if at is not None and (
        not isinstance(at, list) or not all(isinstance(s, str) for s in at)
    ):
        errors.append("allowed_tools must be a list of strings")
    return errors


_RUN_START_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "goal",
        "engine_version",
        "created_at",
    }
)


def build_run_start(
    *,
    ticket_id: str,
    run_id: str,
    goal: str,
    engine_version: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "event_type": "run_start",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "goal": goal,
        "engine_version": engine_version,
        "created_at": created_at,
    }


def validate_run_start(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "run_start"):
        errors.append(
            f"event_type must be 'run_start'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for run_start and must be a non-empty string")
    for str_field in ("goal", "engine_version"):
        v = event.get(str_field)
        if v is None or not isinstance(v, str) or not v:
            errors.append(f"{str_field!r} must be a non-empty string")
    return errors


RUN_END_METRICS_FIELDS = frozenset(
    {
        "run_id",
        "created_at",
        "outcome",
        "model",
        "merged_pr",
        "ci_status",
        "t7_pass",
        "t7_score",
    }
)

_RUN_END_REQUIRED = frozenset({"event_type", "ticket_id"}) | RUN_END_METRICS_FIELDS


def build_run_end(
    *,
    ticket_id: str,
    run_id: str,
    outcome: str,
    model: str,
    merged_pr: Any,
    ci_status: str,
    t7_pass: Any,
    t7_score: float,
    created_at: str,
    token_total: int | None = None,
    final_status: str = "",
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "run_end",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "outcome": outcome,
        "model": model,
        "merged_pr": merged_pr,
        "ci_status": ci_status,
        "t7_pass": t7_pass,
        "t7_score": t7_score,
        "created_at": created_at,
    }


    if final_status:
        event["final_status"] = final_status
    if token_total is not None:
        event["token_total"] = token_total
    return event


def validate_run_end(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "run_end"):
        errors.append(
            f"event_type must be 'run_end'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for run_end and must be a non-empty string")


    for field in ("outcome", "model", "merged_pr", "ci_status", "t7_pass", "t7_score"):
        if field not in event:
            errors.append(f"missing metrics-contract field: {field!r} (run_end)")
    for str_field in ("outcome", "model", "ci_status"):
        v = event.get(str_field)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{str_field!r} must be a non-empty string")
    score = event.get("t7_score")
    if score is not None:
        try:
            float(score)
        except (TypeError, ValueError):
            errors.append(f"t7_score must be coercible to float; got {score!r}")
    tt = event.get("token_total")
    if tt is not None and (isinstance(tt, bool) or not isinstance(tt, int) or tt < 0):
        errors.append(f"token_total must be a non-negative integer when present; got {tt!r}")
    return errors


_WAVE_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "wave",
        "tickets",
        "created_at",
    }
)


def build_wave(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    tickets: list[str],
    created_at: str,
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "wave",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "tickets": list(tickets),
        "created_at": created_at,
    }
    if routing is not None:
        event["routing"] = dict(routing)
    return event


def validate_wave(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "wave"):
        errors.append(f"event_type must be 'wave'; got {event.get('event_type')!r}")
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for wave and must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    tickets = event.get("tickets")
    if tickets is not None and (
        not isinstance(tickets, list) or not all(isinstance(t, str) and t for t in tickets)
    ):
        errors.append("tickets must be a list of non-empty strings")
    routing = event.get("routing")
    if routing is not None and not isinstance(routing, dict):
        errors.append("routing must be a dict when present")
    return errors


_CHECKPOINT_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "run_id",
        "wave",
        "board_hash",
        "event_offset",
        "ticket_states",
        "ledger_hashes",
        "created_at",
    }
)


def build_checkpoint(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    board_hash: str,
    event_offset: int,
    ticket_states: dict[str, str],
    ledger_hashes: dict[str, str],
    created_at: str,
    pending_interrupts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "checkpoint",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "board_hash": board_hash,
        "event_offset": event_offset,
        "ticket_states": dict(ticket_states),
        "pending_interrupts": list(pending_interrupts) if pending_interrupts is not None else [],
        "ledger_hashes": dict(ledger_hashes),
        "created_at": created_at,
    }


def validate_checkpoint(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "checkpoint"):
        errors.append(
            f"event_type must be 'checkpoint'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for checkpoint and must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    board_hash = event.get("board_hash")
    if board_hash is not None and (not isinstance(board_hash, str) or not board_hash):
        errors.append("board_hash must be a non-empty string")
    offset = event.get("event_offset")
    if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0):
        errors.append(f"event_offset must be a non-negative integer; got {offset!r}")
    for dict_field in ("ticket_states", "ledger_hashes"):
        v = event.get(dict_field)
        if v is not None and not isinstance(v, dict):
            errors.append(f"{dict_field!r} must be a dict")
    lh = event.get("ledger_hashes")
    if isinstance(lh, dict):
        for link in ("prev", "self"):
            if link not in lh:
                errors.append(f"ledger_hashes must carry {link!r} (checkpoint hash chain)")
    pi = event.get("pending_interrupts")
    if pi is not None and (not isinstance(pi, list) or not all(isinstance(s, str) for s in pi)):
        errors.append("pending_interrupts must be a list of strings")
    return errors


def build_cache_hit(
    *,
    ticket_id: str,
    cache_key: str,
    created_at: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "cache_hit",
        "ticket_id": ticket_id,
        "cache_key": cache_key,
        "cached": True,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


SPAN_OTEL_ATTRS: dict[str, str] = {
    "kind": "gen_ai.operation.name",
    "agent_name": "gen_ai.agent.name",
    "model": "gen_ai.request.model",
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
    "cached_input_tokens": "gen_ai.usage.cached_input_tokens",
}


SPAN_KINDS = frozenset({"invoke_agent", "chat", "execute_tool", "wave", "run"})


SPAN_STATUSES = frozenset({"ok", "error"})

_SPAN_REQUIRED = frozenset(
    {
        "event_type",
        "ticket_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "kind",
        "gen_ai.agent.name",
        "gen_ai.request.model",
        "start",
        "end",
        "duration_ms",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "cached",
        "status",
        "created_at",
    }
)


def _iso_to_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _duration_ms(start: str, end: str) -> int:
    return int((_iso_to_dt(end) - _iso_to_dt(start)).total_seconds() * 1000)


def build_span(
    *,
    ticket_id: str,
    span_id: str,
    parent_span_id: str | None,
    kind: str,
    agent_name: str,
    model: str,
    start: str,
    end: str,
    created_at: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    status: str = "ok",
    run_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": "span",
        "ticket_id": ticket_id,
        "trace_id": ticket_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "kind": kind,
        "gen_ai.agent.name": agent_name,
        "gen_ai.request.model": model,
        "start": start,
        "end": end,
        "duration_ms": _duration_ms(start, end),
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.usage.cached_input_tokens": cached_input_tokens,
        "cached": cached_input_tokens > 0,
        "status": status,
        "created_at": created_at,
    }
    if run_id is not None:
        event["run_id"] = run_id
    return event


def validate_span(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "span"):
        errors.append(f"event_type must be 'span'; got {event.get('event_type')!r}")


    trace_id = event.get("trace_id")
    if not trace_id or not isinstance(trace_id, str):
        errors.append("trace_id must be a non-empty string (= ticket_id)")
    else:
        ticket_id = event.get("ticket_id")
        if ticket_id is not None and trace_id != ticket_id:
            errors.append(
                f"trace_id must equal ticket_id; got {trace_id!r} != {ticket_id!r}"
            )

    span_id = event.get("span_id")
    if not span_id or not isinstance(span_id, str):
        errors.append("span_id must be a non-empty string")


    if "parent_span_id" in event:
        psid = event["parent_span_id"]
        if psid is not None and (not isinstance(psid, str) or not psid):
            errors.append("parent_span_id must be None (root) or a non-empty string")

    kind = event.get("kind")
    if kind is not None and kind not in SPAN_KINDS:
        errors.append(f"kind must be one of {sorted(SPAN_KINDS)}; got {kind!r}")

    status = event.get("status")
    if status is not None and status not in SPAN_STATUSES:
        errors.append(f"status must be one of {sorted(SPAN_STATUSES)}; got {status!r}")

    for attr in ("gen_ai.agent.name", "gen_ai.request.model"):
        v = event.get(attr)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{attr!r} must be a non-empty string")

    for tfield in ("start", "end"):
        v = event.get(tfield)
        if v is not None and (not isinstance(v, str) or not v):
            errors.append(f"{tfield!r} must be a non-empty ISO-8601 string")


    duration = event.get("duration_ms")
    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, int) or duration < 0
    ):
        errors.append(f"duration_ms must be a non-negative integer; got {duration!r}")
    else:
        start, end = event.get("start"), event.get("end")
        if isinstance(start, str) and start and isinstance(end, str) and end:
            try:
                derived = _duration_ms(start, end)
            except ValueError:
                pass
            else:
                if duration is not None and duration != derived:
                    errors.append(
                        f"duration_ms must equal end - start ({derived} ms); got {duration!r}"
                    )

    for tok in ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"):
        v = event.get(tok)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            errors.append(f"{tok!r} must be a non-negative integer; got {v!r}")

    cit = event.get("gen_ai.usage.cached_input_tokens")
    if cit is not None and (isinstance(cit, bool) or not isinstance(cit, int) or cit < 0):
        errors.append(
            f"'gen_ai.usage.cached_input_tokens' must be a non-negative integer; got {cit!r}"
        )


    cached = event.get("cached")
    if cached is not None and not isinstance(cached, bool):
        errors.append(f"cached must be a boolean; got {cached!r}")
    elif (
        isinstance(cached, bool)
        and isinstance(cit, int)
        and not isinstance(cit, bool)
        and cached != (cit > 0)
    ):
        errors.append(
            f"cached must equal (cached_input_tokens > 0); got cached={cached!r}, "
            f"cached_input_tokens={cit!r}"
        )

    return errors


class EventStore:

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_STORE_PATH


    def append(self, event: dict[str, Any]) -> None:
        errors = validate_envelope(event)
        if errors:
            raise ValueError(
                f"Cannot append invalid event (errors: {errors}): {event!r}"
            )
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "a", encoding="utf-8") as fh:
            with contextlib.suppress(AttributeError, OSError):
                fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                with contextlib.suppress(AttributeError, OSError):
                    fcntl.flock(fh, fcntl.LOCK_UN)


def build_ticket_completion(
    *,
    ticket_id: str,
    run_id: str,
    status: str,
    wave: int,
    created_at: str,
) -> dict[str, Any]:
    return {
        "event_type": "ticket_completion",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "status": status,
        "wave": wave,
        "created_at": created_at,
    }


def validate_ticket_completion(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "ticket_completion"):
        errors.append(
            f"event_type must be 'ticket_completion'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for ticket_completion and must be a non-empty string")
    status = event.get("status")
    if status is not None and (not isinstance(status, str) or not status):
        errors.append("status must be a non-empty string")
    wave = event.get("wave")
    if wave is not None and (isinstance(wave, bool) or not isinstance(wave, int) or wave < 1):
        errors.append(f"wave must be a positive (1-based) integer; got {wave!r}")
    return errors


def build_replanned(
    *,
    ticket_id: str,
    run_id: str,
    wave: int,
    revision: int,
    stall: int,
    max_replans_remaining: int,
    reason: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "event_type": "replanned",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "wave": wave,
        "revision": revision,
        "stall": stall,
        "max_replans_remaining": max_replans_remaining,
        "reason": reason,
        "created_at": created_at,
    }


def validate_replanned(event: dict[str, Any]) -> list[str]:
    errors = validate_envelope(event)
    if event.get("event_type") not in (None, "replanned"):
        errors.append(
            f"event_type must be 'replanned'; got {event.get('event_type')!r}"
        )
    run_id = event.get("run_id")
    if not run_id or not isinstance(run_id, str):
        errors.append("run_id is required for replanned and must be a non-empty string")
    for pos_field in ("wave", "revision"):
        v = event.get(pos_field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 1):
            errors.append(f"{pos_field!r} must be a positive (1-based) integer; got {v!r}")
    for nn_field in ("stall", "max_replans_remaining"):
        v = event.get(nn_field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            errors.append(f"{nn_field!r} must be a non-negative integer; got {v!r}")
    reason = event.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason):
        errors.append("reason must be a non-empty string")
    return errors


def iter_events(
    path: Path | str | None = None,
    *,
    ticket_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
) -> Iterator[dict[str, Any]]:
    p = Path(path) if path is not None else DEFAULT_STORE_PATH
    if not p.exists():
        return
    with open(p, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if ticket_id is not None and event.get("ticket_id") != ticket_id:
                continue
            if run_id is not None and event.get("run_id") != run_id:
                continue
            if event_type is not None and event.get("event_type") != event_type:
                continue
            yield event
