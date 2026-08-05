
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import consolidate_memory as cm

_CONFIG = {
    "recall": {"min_trust": 0.3},
    "ttl_days": {"fact": 180, "default": 120},
    "ranking": {"w_sim": 0.5, "w_recency": 0.3, "w_importance": 0.2, "half_life_days": 30},
}
_NOW = dt.datetime(2026, 7, 1, 12, 0, 0)


def _store(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "outbox.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def test_normalize_maps_memory_and_fact_keys() -> None:
    m = cm.normalize({"memory": "hello", "ts": "2026-07-01T00:00:00Z", "project": "daslab"}, 0)
    assert m["content"] == "hello" and m["id"] == "outbox-0" and m["mem_type"] == "fact"
    f = cm.normalize({"fact": "world", "ts": "2026-07-01", "project": "daslab"}, 1)
    assert f["content"] == "world" and f["id"] == "outbox-1"


def test_load_outbox_tolerates_bad_lines(tmp_path: Path) -> None:
    p = tmp_path / "outbox.jsonl"
    p.write_text(
        '{"memory":"ok","project":"x"}\n\nnot-json\n{"fact":"y","project":"x"}\n',
        encoding="utf-8",
    )
    assert len(cm.load_outbox(p)) == 2


def test_consolidate_ranks_and_is_read_only() -> None:
    memories = [
        cm.normalize({"memory": "the alpha ranking recall memory", "ts": "2026-07-01T00:00:00Z"}, 0),
        cm.normalize({"fact": "unrelated beta note about something else", "ts": "2026-06-15T00:00:00Z"}, 1),
    ]
    report = cm.consolidate(memories, query="ranking recall", now=_NOW, config=_CONFIG, top_k=2)
    assert report["store_size"] == 2
    assert report["mutations"] == []
    comps = [r["composite"] for r in report["ranked"]]
    assert comps == sorted(comps, reverse=True)
    assert report["ranked"][0]["id"] == "outbox-0"
    assert report["ranking_weights"]["w_sim"] == 0.5


def test_recallable_excludes_low_trust() -> None:
    memories = [
        cm.normalize({"memory": "x", "ts": "2026-07-01T00:00:00Z", "trust_score": 0.1}, 0),
        cm.normalize({"memory": "y", "ts": "2026-07-01T00:00:00Z", "trust_score": 0.9}, 1),
    ]
    report = cm.consolidate(memories, query="x", now=_NOW, config=_CONFIG)
    assert report["recallable"] == 1 and report["excluded"] == 1


def test_empty_store_is_safe() -> None:
    report = cm.consolidate([], query="x", now=_NOW, config=_CONFIG)
    assert report["store_size"] == 0 and report["ranked"] == [] and report["mutations"] == []


def test_main_writes_log_and_never_mutates_store(tmp_path: Path) -> None:
    store = _store(tmp_path, [{"memory": "alpha", "ts": "2026-07-01T00:00:00Z", "project": "daslab"}])
    before = store.read_text(encoding="utf-8")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(_CONFIG), encoding="utf-8")
    out = tmp_path / "runs" / "consolidation.json"
    rc = cm.main(
        ["--store", str(store), "--config", str(cfg), "--query", "alpha",
         "--now", "2026-07-01T12:00:00Z", "--out", str(out)]
    )
    assert rc == 0
    assert store.read_text(encoding="utf-8") == before
    log = json.loads(out.read_text(encoding="utf-8"))
    assert log["read_only"] is True and log["mutations"] == []
    assert log["store_size"] == 1


def test_real_config_has_ranking_block() -> None:

    cfg = yaml.safe_load((_REPO_ROOT / "config" / "memory_governance.yaml").read_text())
    assert "ranking" in cfg
    for key in ("w_sim", "w_recency", "w_importance", "half_life_days"):
        assert key in cfg["ranking"], f"ranking.{key} missing from memory_governance.yaml"


def test_microsecond_timestamp_recency_not_collapsed() -> None:


    recent = cm.normalize({"memory": "alpha recall note", "ts": "2026-07-01T11:59:00.614434Z"}, 0)
    old = cm.normalize({"memory": "alpha recall note", "ts": "2026-01-01T00:00:00.123456Z"}, 1)
    assert recent["created_at"] == "2026-07-01T11:59:00Z"
    rep = cm.consolidate([recent, old], query="alpha recall note", now=_NOW, config=_CONFIG, top_k=2)
    comp = {r["id"]: r["composite"] for r in rep["ranked"]}
    assert comp["outbox-0"] > comp["outbox-1"]


def test_offset_timestamp_normalized() -> None:
    m = cm.normalize({"memory": "x", "ts": "2026-06-24T19:56:15+00:00"}, 0)
    assert m["created_at"] == "2026-06-24T19:56:15Z"


def test_unparseable_now_errors(tmp_path: Path) -> None:
    store = _store(tmp_path, [{"memory": "x", "ts": "2026-07-01T00:00:00Z"}])
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(_CONFIG), encoding="utf-8")
    with pytest.raises(SystemExit):
        cm.main(["--store", str(store), "--config", str(cfg), "--now", "not-a-timestamp"])


def test_null_trust_score_does_not_crash() -> None:
    m = cm.normalize({"memory": "x", "ts": "2026-07-01T00:00:00Z", "trust_score": None}, 0)
    assert m["trust_score"] == 0.5
    cm.consolidate([m], query="x", now=_NOW, config=_CONFIG)
