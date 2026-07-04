#!/usr/bin/env python3
"""tests/test_memory_governance.py — ArcRift memory governance (R-5 / ADR-005)."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_memory_governance as cmg  # noqa: E402  (import after path manipulation)
import memory_lib as ml  # noqa: E402

REAL_CONFIG = REPO_ROOT / "config" / "memory_governance.yaml"
NOW = dt.datetime(2026, 6, 21, 0, 0, 0)
CFG = {
    "schema": {"required_fields": ["id", "content", "project", "provenance", "trust_score", "created_at"]},
    "trust_tiers": {"verified_pr": 1.0, "review_validated": 0.7, "cited_source": 0.5, "unverified_claim": 0.2},
    "recall": {"min_trust": 0.3, "dedupe_similarity": 0.85},
    "ttl_days": {"fact": 180, "default": 120},
    "health": {"decay_per_bad": 0.05},
}


def _mem(mid="m1", provenance="verified_pr", trust=1.0, content="alpha beta gamma",
         created="2026-06-20T00:00:00Z", **extra) -> dict:
    m = {"id": mid, "content": content, "project": "daslab", "provenance": provenance,
         "trust_score": trust, "created_at": created, "mem_type": "fact"}
    m.update(extra)
    return m


# --------------------------------------------------------------------------- #
# Library controls
# --------------------------------------------------------------------------- #

def test_trust_for():
    assert ml.trust_for("verified_pr", CFG["trust_tiers"]) == 1.0
    assert ml.trust_for("unknown", CFG["trust_tiers"]) == 0.2  # unverified default


def test_is_expired():
    old = _mem(created="2020-01-01T00:00:00Z")
    fresh = _mem(created="2026-06-20T00:00:00Z")
    assert ml.is_expired(old, NOW, CFG["ttl_days"]) is True
    assert ml.is_expired(fresh, NOW, CFG["ttl_days"]) is False


def test_jaccard_and_duplicates():
    assert ml.jaccard("alpha beta", "alpha beta") == 1.0
    dupes = ml.duplicate_pairs([_mem("a", content="alpha beta gamma"), _mem("b", content="alpha beta gamma")])
    assert ("a", "b") in dupes


def test_quarantined_detection():
    assert ml.is_quarantined(_mem(status="quarantined")) is True
    assert ml.is_quarantined(_mem(contradicts=["m9"])) is True
    assert ml.is_quarantined(_mem()) is False


def test_recallable_excludes_bad_memories():
    good = _mem("good")
    low_trust = _mem("low", provenance="unverified_claim", trust=0.2)
    quarantined = _mem("q", status="quarantined")
    expired = _mem("old", created="2020-01-01T00:00:00Z")
    recall = ml.recallable([good, low_trust, quarantined, expired], NOW, CFG)
    assert [m["id"] for m in recall] == ["good"]


def test_memory_health_decays():
    assert ml.memory_health([], NOW, CFG) == 1.0
    mems = [_mem("good"), _mem("q", status="quarantined"), _mem("old", created="2020-01-01T00:00:00Z")]
    assert ml.memory_health(mems, NOW, CFG) == 0.9  # 2 bad * 0.05 decay


# --------------------------------------------------------------------------- #
# CLI validator
# --------------------------------------------------------------------------- #

def _store(tmp_path: Path, mems: list[dict]) -> Path:
    p = tmp_path / ".arcrift-outbox.jsonl"
    p.write_text("".join(json.dumps(m) + "\n" for m in mems), encoding="utf-8")
    return p


def _run(tmp_path: Path, mems: list[dict]) -> int:
    return cmg.main([
        "--store", str(_store(tmp_path, mems)),
        "--config", str(REAL_CONFIG), "--now", "2026-06-21T00:00:00Z",
    ])


def test_cli_inert_without_store(tmp_path):
    assert cmg.main(["--store", str(tmp_path / "nope.jsonl"), "--config", str(REAL_CONFIG)]) == 0


def test_cli_clean_store_exit_0(tmp_path):
    assert _run(tmp_path, [_mem("m1"), _mem("m2", provenance="review_validated", trust=0.7, content="distinct words here")]) == 0


def test_cli_missing_trust_score_exit_1(tmp_path):
    bad = _mem("m1")
    del bad["trust_score"]
    assert _run(tmp_path, [bad]) == 1


def test_cli_trust_mismatch_exit_1(tmp_path):
    # provenance verified_pr should be 1.0, not 0.5
    assert _run(tmp_path, [_mem("m1", provenance="verified_pr", trust=0.5)]) == 1


def test_cli_contradicted_not_quarantined_exit_1(tmp_path):
    mems = [_mem("m1"), _mem("m2", contradicts=["m1"], status="active")]
    assert _run(tmp_path, mems) == 1


def test_cli_contradicted_and_quarantined_exit_0(tmp_path):
    mems = [_mem("m1"), _mem("m2", provenance="review_validated", trust=0.7,
                              content="totally different content", contradicts=["m1"], status="quarantined")]
    assert _run(tmp_path, mems) == 0


def test_zero_trust_tier_is_consistent():
    # a 0.0 provenance tier with trust_score 0.0 must NOT false-fail (review-found `or -1` bug)
    cfg = dict(CFG, trust_tiers=dict(CFG["trust_tiers"], rumor=0.0))
    assert cmg.violations([_mem("m1", provenance="rumor", trust=0.0)], cfg, NOW) == []


def test_unparseable_created_at_flagged():
    assert any("unparseable created_at" in p for p in cmg.violations([_mem("m1", created="yesterday")], CFG, NOW))


# --------------------------------------------------------------------------- #
# P21 — recall ranking (DAS-1490)
# --------------------------------------------------------------------------- #

RANKING_CFG = dict(CFG, ranking={"w_sim": 0.5, "w_recency": 0.3, "w_importance": 0.2, "half_life_days": 30})


def test_composite_score_high_sim_wins():
    """A memory whose content closely matches the query scores higher than a distant one."""
    query = "arcrift memory governance trust"
    near = _mem("near", content="arcrift memory governance trust score", created="2026-06-20T00:00:00Z")
    far = _mem("far", content="unrelated topic about database sharding", created="2026-06-20T00:00:00Z")
    ranking_cfg = RANKING_CFG.get("ranking", {})
    s_near = ml.composite_score(near, query, NOW, ranking_cfg)
    s_far = ml.composite_score(far, query, NOW, ranking_cfg)
    assert s_near > s_far, f"near={s_near:.4f} far={s_far:.4f}"


def test_composite_score_recent_beats_old_same_content():
    """Given equal content, a fresh memory scores higher than a stale one."""
    query = "arcrift recall path"
    recent = _mem("recent", content="arcrift recall path upgrade", created="2026-06-20T00:00:00Z")
    old = _mem("old_m", content="arcrift recall path upgrade", created="2024-01-01T00:00:00Z")
    ranking_cfg = RANKING_CFG.get("ranking", {})
    s_recent = ml.composite_score(recent, query, NOW, ranking_cfg)
    s_old = ml.composite_score(old, query, NOW, ranking_cfg)
    assert s_recent > s_old, f"recent={s_recent:.4f} old={s_old:.4f}"


def test_rank_memories_orders_by_composite():
    """rank_memories returns candidates in descending composite-score order."""
    query = "arcrift memory recall"
    mems = [
        _mem("low",  content="unrelated database indexing topic",        created="2026-06-20T00:00:00Z"),
        _mem("high", content="arcrift memory recall trust governance",   created="2026-06-20T00:00:00Z"),
        _mem("mid",  content="memory governance trust",                  created="2026-06-15T00:00:00Z"),
    ]
    ranked = ml.rank_memories(mems, query, NOW, RANKING_CFG)
    ids = [m["id"] for m in ranked]
    assert ids[0] == "high", f"expected 'high' first, got {ids}"
    assert ids[-1] == "low", f"expected 'low' last, got {ids}"


def test_rank_memories_stable_on_empty():
    """rank_memories handles an empty list without error."""
    assert ml.rank_memories([], "any query", NOW, RANKING_CFG) == []


def test_rank_memories_importance_field_used():
    """Explicit importance field is preferred over trust_score as importance proxy."""
    query = "topic"
    # Two otherwise equal memories; one has importance=1.0
    high_imp = _mem("hi_imp", content="topic", created="2026-06-20T00:00:00Z", importance=1.0)
    low_imp = _mem("lo_imp", content="topic", created="2026-06-20T00:00:00Z", importance=0.0)
    ranked = ml.rank_memories([low_imp, high_imp], query, NOW, RANKING_CFG)
    assert ranked[0]["id"] == "hi_imp"


def test_rank_memories_ab_vs_filter_baseline():
    """A/B: ranking precision@k >= filter-only (insertion order) precision@k.

    Setup: 6 memories — 3 are relevant to the query (high jaccard), 3 are not.
    Filter-only (recallable) returns them in insertion order (irrelevant first).
    rank_memories must surface all relevant notes in the top-3 positions.
    Precision@3 for ranker must be >= precision@3 for filter-only baseline.
    """
    NOW_AB = dt.datetime(2026, 6, 21, 0, 0, 0)
    query = "arcrift memory recall trust score"

    # Irrelevant notes first (simulates worst-case insertion order for baseline)
    irrelevant = [
        _mem("ir1", content="network packet routing bgp protocol", created="2026-06-20T00:00:00Z"),
        _mem("ir2", content="kubernetes helm chart deployment",    created="2026-06-20T00:00:00Z"),
        _mem("ir3", content="sql query optimisation index scan",   created="2026-06-20T00:00:00Z"),
    ]
    relevant = [
        _mem("rel1", content="arcrift memory recall trust score governance", created="2026-06-20T00:00:00Z"),
        _mem("rel2", content="arcrift trust recall score management",        created="2026-06-20T00:00:00Z"),
        _mem("rel3", content="memory trust score recall arcrift",            created="2026-06-20T00:00:00Z"),
    ]
    all_mems = irrelevant + relevant  # insertion order: irrelevant appear first

    # Filter-only baseline (recallable keeps insertion order)
    baseline = ml.recallable(all_mems, NOW_AB, CFG)
    baseline_top3_ids = {m["id"] for m in baseline[:3]}
    relevant_ids = {"rel1", "rel2", "rel3"}
    baseline_precision = len(baseline_top3_ids & relevant_ids) / 3

    # Ranked path
    eligible = ml.recallable(all_mems, NOW_AB, CFG)
    ranked = ml.rank_memories(eligible, query, NOW_AB, RANKING_CFG)
    ranked_top3_ids = {m["id"] for m in ranked[:3]}
    ranked_precision = len(ranked_top3_ids & relevant_ids) / 3

    assert ranked_precision >= baseline_precision, (
        f"ranker precision@3={ranked_precision:.2f} < baseline {baseline_precision:.2f}"
    )
    # Ranker must put ALL relevant notes in top 3
    assert ranked_top3_ids == relevant_ids, f"top-3 from ranker: {ranked_top3_ids}"


# --------------------------------------------------------------------------- #
# P21 — prune hygiene callable (DAS-1490)
# --------------------------------------------------------------------------- #

def test_prune_hygiene_identifies_expired():
    old = _mem("expired_m", created="2020-01-01T00:00:00Z")
    good = _mem("good_m")
    candidates = ml.prune_hygiene_candidates([old, good], NOW, CFG)
    ids = [c[0] for c in candidates]
    assert "expired_m" in ids
    assert "good_m" not in ids


def test_prune_hygiene_identifies_quarantined():
    q = _mem("q_m", status="quarantined")
    good = _mem("good_m2")
    candidates = ml.prune_hygiene_candidates([q, good], NOW, CFG)
    ids = [c[0] for c in candidates]
    assert "q_m" in ids
    assert "good_m2" not in ids


def test_prune_hygiene_identifies_low_trust():
    low = _mem("low_t", provenance="unverified_claim", trust=0.1)
    good = _mem("good_m3")
    candidates = ml.prune_hygiene_candidates([low, good], NOW, CFG)
    ids = [c[0] for c in candidates]
    assert "low_t" in ids
    assert "good_m3" not in ids


def test_prune_hygiene_no_live_loop():
    """prune_hygiene_candidates is a pure callable — calling it returns a list, not a generator/coroutine."""
    result = ml.prune_hygiene_candidates([], NOW, CFG)
    assert isinstance(result, list)


def test_prune_hygiene_empty_store():
    assert ml.prune_hygiene_candidates([], NOW, CFG) == []
