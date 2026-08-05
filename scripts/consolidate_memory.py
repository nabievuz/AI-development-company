#!/usr/bin/env python3


from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import memory_lib as ml
import yaml

DEFAULT_STORE = _ROOT / "board" / ".arcrift-outbox.jsonl"
DEFAULT_CONFIG = _ROOT / "config" / "memory_governance.yaml"


DEFAULT_TRUST = 0.5


def _utcnow_naive() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC).replace(tzinfo=None)


def _normalize_ts(raw: object) -> str:
    if not raw:
        return ""
    s = str(raw).strip()
    if ml.parse_iso(s) is not None:
        return s
    try:
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(dt.UTC).replace(tzinfo=None)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_config(path: str | Path) -> dict:
    p = Path(path)
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}


def load_outbox(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def normalize(record: dict, index: int, default_trust: float = DEFAULT_TRUST) -> dict:
    content = record.get("content") or record.get("memory") or record.get("fact") or ""
    return {
        "id": str(record.get("id") or f"outbox-{index}"),
        "content": str(content),
        "project": record.get("project", ""),
        "created_at": _normalize_ts(record.get("created_at") or record.get("ts") or ""),
        "trust_score": float(
            default_trust if record.get("trust_score") is None else record.get("trust_score")
        ),
        "importance": record.get("importance"),
        "status": record.get("status", ""),
        "mem_type": record.get("mem_type") or record.get("type") or "fact",
    }


def _similarity_order(memories: list[dict], query: str) -> list[dict]:
    return sorted(
        memories,
        key=lambda m: ml.jaccard(query, str(m.get("content", ""))),
        reverse=True,
    )


def consolidate(
    memories: list[dict], query: str, now: dt.datetime, config: dict, top_k: int = 3
) -> dict:
    ranking_cfg = config.get("ranking", {}) or {}
    recallable = ml.recallable(memories, now, config)
    ranked = ml.rank_memories(memories, query, now, config)
    ranked_recallable = ml.rank_memories(recallable, query, now, config)
    baseline = _similarity_order(memories, query)
    prune = ml.prune_hygiene_candidates(memories, now, config)

    def scored(mems: list[dict]) -> list[dict]:
        return [
            {
                "id": m["id"],
                "composite": round(ml.composite_score(m, query, now, ranking_cfg), 6),
                "similarity": round(ml.jaccard(query, str(m.get("content", ""))), 6),
            }
            for m in mems
        ]

    ranked_topk = [m["id"] for m in ranked[:top_k]]
    baseline_topk = [m["id"] for m in baseline[:top_k]]
    return {
        "store_size": len(memories),
        "recallable": len(recallable),
        "excluded": len(memories) - len(recallable),
        "ranking_weights": {
            k: ranking_cfg.get(k)
            for k in ("w_sim", "w_recency", "w_importance", "half_life_days")
        },
        "ranked": scored(ranked),
        "ranked_recallable": scored(ranked_recallable),
        "prune_candidates": [{"id": i, "reason": r} for i, r in prune],
        "ab_parity": {
            "top_k": top_k,
            "ranked_top_k": ranked_topk,
            "baseline_similarity_top_k": baseline_topk,
            "overlap": len(set(ranked_topk) & set(baseline_topk)),
            "unit_proof": (
                "ranker precision@3 >= filter-only baseline is proven in "
                "tests/test_memory_governance.py::test_rank_memories_ab_vs_filter_baseline"
            ),
        },

        "mutations": [],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only idle-time memory consolidation (R10) — evaluates + logs, mutates nothing."
    )
    ap.add_argument("--store", default=str(DEFAULT_STORE))
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--query", default="", help="recall query the ranking scores against")
    ap.add_argument("--now", default=None, help="ISO-8601 UTC (naive) for deterministic runs; default: current time")
    ap.add_argument("--default-trust", type=float, default=DEFAULT_TRUST)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--json", action="store_true", help="emit the full run log as JSON to stdout")
    ap.add_argument("--out", default=None, help="write the run log (JSON) to this path")
    args = ap.parse_args(argv)

    config = load_config(args.config)
    raw = load_outbox(args.store)
    memories = [normalize(r, i, args.default_trust) for i, r in enumerate(raw)]
    if args.now:
        now = ml.parse_iso(_normalize_ts(args.now))
        if now is None:
            ap.error(f"--now is not a parseable ISO-8601 timestamp: {args.now!r}")
    else:
        now = _utcnow_naive()

    report = consolidate(memories, args.query, now, config, top_k=args.top_k)
    report["generated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    report["store"] = str(args.store)
    report["read_only"] = True

    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
    if args.json or not args.out:
        print(payload)
    else:
        print(
            f"consolidation run log -> {args.out}  "
            f"(store={report['store_size']}, recallable={report['recallable']}, "
            f"prune_candidates={len(report['prune_candidates'])}, mutations=0)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
