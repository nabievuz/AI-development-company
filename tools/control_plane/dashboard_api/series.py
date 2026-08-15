from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from . import engine
from .readers import NO_DATA, panel

TRACK_TITLES = {
    "T1": "Busy fraction",
    "T2": "Idle waves",
    "T3": "Concurrency",
    "T4": "Model mix",
    "T5": "Recovery reliability",
    "T6": "Review efficiency",
    "T7": "Quality rubric",
}


def _events() -> tuple[list[dict[str, Any]], str]:
    wave_kpi, error = engine.try_load("wave_kpi")
    if wave_kpi is None:
        return [], error
    try:
        return wave_kpi.read_events(str(engine.events_path())), ""
    except Exception as exc:
        return [], f"event store unreadable: {exc}"


def _waves() -> tuple[list[dict[str, Any]], str]:
    metrics, error = engine.try_load("metrics_lib")
    if metrics is None:
        return [], error
    try:
        return metrics.read_waves(str(engine.wave_log_path())), ""
    except Exception as exc:
        return [], f"wave log unreadable: {exc}"


def _track(code: str, value: float | None, unit: str, detail: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "code": code,
        "title": TRACK_TITLES.get(code, code),
        "value": value,
        "unit": unit,
        "available": value is not None,
        "reason": "" if value is not None else NO_DATA,
        "detail": detail or {},
    }


def health_tracks() -> dict[str, Any]:
    events, event_error = _events()
    waves, wave_error = _waves()
    metrics, metrics_error = engine.try_load("metrics_lib")
    wave_kpi, kpi_error = engine.try_load("wave_kpi")
    errors = [e for e in (event_error, wave_error, metrics_error, kpi_error) if e]
    if metrics is None or wave_kpi is None:
        return panel(False, "; ".join(errors) or "metric engine unavailable", tracks=[])

    busy = None
    busy_stats: dict[str, Any] = {}
    try:
        busy, busy_stats = wave_kpi.busy_fraction_from_events(events)
    except Exception as exc:
        errors.append(f"T1 failed: {exc}")

    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            errors.append(f"{getattr(fn, '__name__', 'metric')} failed: {exc}")
            return None

    idle = _safe(metrics.idle_wave_rates, waves)
    concurrency = _safe(metrics.concurrency_stats, events)
    mix = _safe(metrics.model_mix, events)
    recovery = _safe(metrics.recovery_reliability, events)
    review = _safe(metrics.review_efficiency, events)
    rubric = engine.config_dir() / "t7_rubric.yaml"

    tracks = [
        _track("T1", busy, "ratio", dict(busy_stats or {})),
        _track("T2", (idle or {}).get("t2a_rate") if idle else None, "ratio", idle),
        _track("T3", (concurrency or {}).get("median") if concurrency else None, "count", concurrency),
        _track("T4", (mix or {}).get("ratio") if mix else None, "ratio", mix),
        _track("T5", (recovery or {}).get("ratio") if recovery else None, "ratio", recovery),
        _track("T6", (review or {}).get("rework_rate") if review else None, "ratio", review),
        {
            "code": "T7",
            "title": TRACK_TITLES["T7"],
            "value": None,
            "unit": "rubric",
            "available": rubric.is_file(),
            "reason": "" if rubric.is_file() else f"missing {engine.rel(rubric)}",
            "detail": {"rubric": engine.rel(rubric), "immutable": True, "hard_blocker": True},
        },
    ]
    return panel(
        True,
        "; ".join(errors),
        tracks=tracks,
        events=len(events),
        waves=len(waves),
        degraded=[t["code"] for t in tracks if not t["available"]],
    )


def throughput() -> dict[str, Any]:
    trends, error = engine.try_load("trends")
    if trends is None:
        return panel(False, error)
    events, event_error = _events()
    if event_error:
        return panel(False, event_error)
    try:
        series = trends.throughput_series(events, 7)
        trend = trends.classify_trend(series, higher_is_better=True)
    except Exception as exc:
        return panel(False, f"trend computation failed: {exc}")
    direction = str(trend.get("direction") or "insufficient")
    if direction == "insufficient":
        return panel(False, NO_DATA, series=list(series), direction=direction)
    return panel(
        True,
        "",
        series=[float(v) for v in series],
        direction=direction,
        slope=float(trend.get("slope") or 0.0),
    )


def _group(group: Any) -> dict[str, Any]:
    return {
        "key": str(getattr(group, "key", "")),
        "input_tokens": int(getattr(group, "input_tokens", 0)),
        "cached_input_tokens": int(getattr(group, "cached_input_tokens", 0)),
        "output_tokens": int(getattr(group, "output_tokens", 0)),
        "span_count": int(getattr(group, "span_count", 0)),
        "estimated_cost_usd": float(getattr(group, "estimated_cost_usd", 0.0)),
    }


def cost_ledger() -> dict[str, Any]:
    try:
        module = engine.load_file("dashboard_cost_ledger", "scripts/cost/cost_ledger.py")
    except engine.EngineUnavailable as exc:
        return panel(False, str(exc))
    try:
        ledger = module.aggregate_spans(store_path=engine.events_path())
    except Exception as exc:
        return panel(False, f"cost aggregation failed: {exc}")
    if ledger is None:
        return panel(False, NO_DATA)
    return panel(
        True,
        "",
        totals={
            "spans": int(ledger.raw_span_count),
            "input_tokens": int(ledger.raw_input_tokens),
            "cached_input_tokens": int(ledger.raw_cached_input_tokens),
            "output_tokens": int(ledger.raw_output_tokens),
            "estimated_cost_usd": float(ledger.raw_estimated_cost_usd),
            "dropped_undated": int(getattr(ledger, "dropped_undated", 0)),
        },
        by_tier=[_group(g) for g in ledger.by_tier.values()],
        by_agent=[_group(g) for g in ledger.by_agent.values()],
        by_ticket=[_group(g) for g in ledger.by_ticket.values()],
        unpriced_tiers=sorted(str(t) for t in (ledger.unknown_tiers or set())),
    )


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _tier(model: str) -> str:
    lowered = model.lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in lowered:
            return tier
    return lowered or "(unknown)"


def agent_usage() -> dict[str, Any]:
    events, error = _events()
    if error:
        return panel(False, error)
    rollup: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") != "span":
            continue
        name = str(event.get("gen_ai.agent.name") or "(unknown agent)")
        row = rollup.setdefault(
            name,
            {"agent": name, "spans": 0, "ok": 0, "input_tokens": 0, "output_tokens": 0, "tiers": set()},
        )
        row["spans"] += 1
        if str(event.get("status", "")).lower() == "ok":
            row["ok"] += 1
        row["input_tokens"] += _safe_int(event.get("gen_ai.usage.input_tokens"))
        row["output_tokens"] += _safe_int(event.get("gen_ai.usage.output_tokens"))
        model = str(event.get("gen_ai.request.model") or "")
        if model:
            row["tiers"].add(_tier(model))
    if not rollup:
        return panel(False, NO_DATA)
    rows = []
    for row in rollup.values():
        spans = int(row["spans"])
        rows.append(
            {
                "agent": row["agent"],
                "spans": spans,
                "ok": int(row["ok"]),
                "success_rate": (row["ok"] / spans) if spans else 0.0,
                "input_tokens": int(row["input_tokens"]),
                "output_tokens": int(row["output_tokens"]),
                "tiers": sorted(row["tiers"]),
            }
        )
    rows.sort(key=lambda r: -r["spans"])
    return panel(True, "", agents=rows, total=len(rows))


def tool_usage() -> dict[str, Any]:
    events, error = _events()
    if error:
        return panel(False, error)
    tools: dict[str, int] = {}
    kinds: dict[str, int] = {}
    unavailable = 0
    for event in events:
        kind = event.get("event_type")
        if kind == "tool_call":
            name = str(event.get("tool") or event.get("tool_name") or event.get("name") or "(unnamed)")
            tools[name] = tools.get(name, 0) + 1
        elif kind == "span":
            key = str(event.get("kind") or "?")
            kinds[key] = kinds.get(key, 0) + 1
        elif kind == "tool_unavailable":
            unavailable += 1
    if not tools and not kinds and not unavailable:
        return panel(False, NO_DATA)
    return panel(
        True,
        "",
        tools=[{"tool": k, "calls": v} for k, v in sorted(tools.items(), key=lambda kv: -kv[1])],
        span_kinds=[{"kind": k, "count": v} for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])],
        unavailable=unavailable,
    )


def gate6_records() -> dict[str, Any]:
    yaml_mod, error = engine.try_load("yaml")
    if yaml_mod is None:
        return panel(False, error)
    directory = engine.experiments_dir()
    counts = {"applied": 0, "reverted": 0, "deferred": 0, "failed": 0}
    records: list[dict[str, Any]] = []
    if directory.is_dir():
        candidates = sorted(list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml")))
        for path in candidates:
            if "TEMPLATE" in path.name.upper():
                continue
            try:
                doc = yaml_mod.safe_load(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            record = doc.get("gate_6_record", doc) if isinstance(doc, dict) else None
            if not isinstance(record, dict):
                continue
            status = str((record.get("result") or {}).get("status", "")).lower()
            if status in counts:
                counts[status] += 1
            records.append(
                {
                    "file": engine.rel(path),
                    "status": status or "(unset)",
                    "change_type": str(record.get("change_type") or ""),
                }
            )
    events, _ = _events()
    tuning = sum(1 for e in events if e.get("event_type") == "gate6_tuning" or e.get("change_type"))
    if not records and not tuning:
        return panel(
            False,
            "no tuning changes — the self-optimizing loop is OFF (shadow mode)",
            counts=counts,
            tuning_events=0,
        )
    return panel(True, "", counts=counts, records=records, tuning_events=tuning)


def memory_health() -> dict[str, Any]:
    memory_lib, error = engine.try_load("memory_lib")
    if memory_lib is None:
        return panel(False, error)
    yaml_mod, _ = engine.try_load("yaml")
    store = engine.board() / ".arcrift-outbox.jsonl"
    if not store.is_file():
        return panel(False, "no memory store yet (ArcRift is the live backend)")
    from .readers import _read_jsonl

    memories = _read_jsonl(store)
    if not memories:
        return panel(False, "no memory store yet (ArcRift is the live backend)")
    config: dict[str, Any] = {}
    config_path = engine.config_dir() / "memory_governance.yaml"
    if yaml_mod is not None and config_path.is_file():
        try:
            loaded = yaml_mod.safe_load(config_path.read_text(encoding="utf-8"))
            config = loaded if isinstance(loaded, dict) else {}
        except Exception:
            config = {}
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    try:
        recallable = memory_lib.recallable(memories, now, config)
        score = memory_lib.memory_health(memories, now, config)
    except Exception as exc:
        return panel(False, f"memory evaluation failed: {exc}")
    return panel(
        True,
        "",
        total=len(memories),
        recallable=len(recallable),
        health=float(score),
    )
