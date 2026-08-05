#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import memory_lib as ml


def _lr(
    key: str = "test-key",
    content: str = "alpha beta gamma delta",
    confidence: float = 5.0,
    scope: str = "daslab",
    date: str = "2026-07-01",
    **extra,
) -> dict:
    r = {
        "key": key,
        "content": content,
        "confidence": confidence,
        "scope": scope,
        "date": date,
        "project": scope,
        "type": "pattern",
        "source": "user-stated",
    }
    r.update(extra)
    return r


def test_cluster_identical_records_into_one_cluster():
    a = _lr("k1", "build before test always run build first")
    b = _lr("k2", "build before test always run build first")
    clusters = ml.cluster_learnings([a, b], threshold=0.60)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2


def test_cluster_dissimilar_records_into_separate_clusters():
    a = _lr("k1", "build before test run vitest")
    b = _lr("k2", "metric denominator check kpi report")
    clusters = ml.cluster_learnings([a, b], threshold=0.60)
    assert len(clusters) == 2
    assert all(len(c) == 1 for c in clusters)


def test_cluster_threshold_respected():

    a = _lr("k1", "one two three")
    b = _lr("k2", "four five six")
    clusters = ml.cluster_learnings([a, b], threshold=0.50)
    assert len(clusters) == 2


def test_cluster_empty_list():
    assert ml.cluster_learnings([]) == []


def test_cluster_single_record():
    r = _lr("k1", "singleton record")
    clusters = ml.cluster_learnings([r])
    assert clusters == [[r]]


def test_merge_cluster_raises_on_empty():
    try:
        ml.merge_cluster([])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_merge_cluster_single_no_boost():
    r = _lr("k1", content="test content", confidence=5.0)
    merged = ml.merge_cluster([r])
    assert merged["confidence"] == 5
    assert merged["source_count"] == 1


def test_merge_cluster_boosts_confidence():
    records = [
        _lr("k1", content="similar content alpha", confidence=5.0),
        _lr("k2", content="similar content beta", confidence=4.0),
        _lr("k3", content="similar content gamma", confidence=3.0),
    ]
    merged = ml.merge_cluster(records)

    assert merged["confidence"] == 7
    assert merged["source_count"] == 3


def test_merge_cluster_caps_confidence_at_10():
    records = [_lr(f"k{i}", confidence=9.0) for i in range(5)]
    merged = ml.merge_cluster(records)
    assert merged["confidence"] == 10


def test_merge_cluster_picks_most_recent_date():
    records = [
        _lr("k1", date="2026-01-01"),
        _lr("k2", date="2026-07-03"),
        _lr("k3", date="2026-03-15"),
    ]
    merged = ml.merge_cluster(records)
    assert merged["date"] == "2026-07-03"


def test_merge_cluster_narrowest_scope_wins():
    records = [
        _lr("k1", scope="org"),
        _lr("k2", scope="daslab"),
        _lr("k3", scope="org"),
    ]
    merged = ml.merge_cluster(records)
    assert merged["scope"] == "daslab"


def test_merge_cluster_all_org_scope_stays_org():
    records = [
        _lr("k1", scope="org"),
        _lr("k2", scope="org"),
    ]
    merged = ml.merge_cluster(records)
    assert merged["scope"] == "org"


def test_merge_cluster_highest_confidence_is_base():
    records = [
        _lr("k1", content="low confidence content", confidence=2.0),
        _lr("k2", content="high confidence content", confidence=8.0),
    ]
    merged = ml.merge_cluster(records)

    assert "high confidence" in merged["content"]


def test_distill_empty_records():
    assert ml.distill_learnings([], project="daslab") == []


def test_distill_filters_deny_project():
    records = [
        _lr("k1", content="platform insight alpha", scope="daslab", project="daslab"),
        _lr("k2", content="product insight beta", scope="qaqnuz", project="qaqnuz"),
    ]

    result = ml.distill_learnings(records, project="daslab", deny_projects=["qaqnuz"])
    assert len(result) == 1
    assert result[0]["key"] == "k1"


def test_distill_includes_org_scope():
    records = [
        _lr("k1", content="platform alpha beta", scope="daslab", project="daslab"),
        _lr("k2", content="universal gamma delta", scope="org", project="org"),
    ]
    result = ml.distill_learnings(records, project="daslab")
    assert len(result) == 2


def test_distill_excludes_unrelated_project():
    records = [
        _lr("k1", content="other project content", scope="other-project", project="other-project"),
    ]
    result = ml.distill_learnings(records, project="daslab")
    assert result == []


def test_distill_bound_respected():
    records = [_lr(f"k{i}", content=f"unique insight {i} foo bar baz") for i in range(20)]
    result = ml.distill_learnings(records, project="daslab", bound=5)
    assert len(result) <= 5


def test_distill_sorted_by_confidence_desc():
    records = [
        _lr("k_low", content="low conf content alpha beta", confidence=2.0),
        _lr("k_high", content="high conf content gamma delta", confidence=9.0),
        _lr("k_mid", content="mid conf content epsilon zeta", confidence=5.0),
    ]
    result = ml.distill_learnings(records, project="daslab")
    confidences = [ml._record_confidence(r) for r in result]
    assert confidences == sorted(confidences, reverse=True)


def test_distill_deny_boundary_never_crossed():

    platform_record = _lr("platform-k", content="platform only alpha beta", project="daslab", scope="daslab")
    product_record = _lr("product-k", content="product only gamma delta", project="qaqnuz", scope="qaqnuz")

    result = ml.distill_learnings([platform_record, product_record], project="daslab", deny_projects=["qaqnuz"])
    keys = [r.get("key") for r in result]
    assert "product-k" not in keys
    assert "platform-k" in keys


def test_is_org_promotion_true_when_promoted_from_present():
    r = _lr("k1", scope="org", promoted_from="daslab")
    assert ml.is_org_promotion(r) is True


def test_is_org_promotion_false_without_promoted_from():
    r = _lr("k1", scope="org")
    assert ml.is_org_promotion(r) is False


def test_is_org_promotion_false_project_scoped():
    r = _lr("k1", scope="daslab", promoted_from="daslab")
    assert ml.is_org_promotion(r) is False


def test_needs_manager_gate_true_for_promotion():
    r = _lr("k1", scope="org", promoted_from="daslab")
    assert ml.needs_manager_gate(r) is True


def test_needs_manager_gate_false_for_normal_record():
    r = _lr("k1", scope="daslab")
    assert ml.needs_manager_gate(r) is False


def test_format_learned_section_empty():
    section = ml.format_learned_section([], date="2026-07-03")
    assert section.startswith("## Learned\n")
    assert "DISTILLATION" in section
    assert "no distilled learnings" in section


def test_format_learned_section_with_records():
    records = [
        _lr("build-first", content="Always build before running tests", confidence=8.0, date="2026-07-03"),
    ]
    section = ml.format_learned_section(records, date="2026-07-03")
    assert "## Learned" in section
    assert "`build-first`" in section
    assert "confidence: 8" in section
    assert "Always build before running tests" in section
    assert "2026-07-03" in section


def test_format_learned_section_bound_in_banner():
    section = ml.format_learned_section([], date="2026-07-03", bound=5)
    assert "Bounded at 5" in section


def test_format_learned_section_date_in_banner():
    section = ml.format_learned_section([], date="2026-07-03")
    assert "2026-07-03" in section


_BARE_TEMPLATE = (
    "# Role — Example\n\n"
    "## Identity\n- **Display name:** Example\n\n"
    "## Mission\nDo the work.\n\n"
    "## Scope\n- Owns: things.\n\n"
    "## Definition of Done\nWork is done when criteria are met.\n\n"
    "## When to escalate\n- Escalate when stuck.\n"
)

_TEMPLATE_WITH_LEARNED = (
    "# Role — Example\n\n"
    "## Mission\nDo the work.\n\n"
    "## When to escalate\n- Escalate when stuck.\n\n"
    "## Learned\n"
    "<!-- DISTILLATION — old run -->\n"
    "- **2026-01-01** `old-key` (confidence: 3/10, scope: daslab): Old insight.\n"
)


def test_apply_inserts_section_when_absent():
    records = [_lr("new-key", content="New insight here", confidence=7.0, date="2026-07-03")]
    result = ml.apply_learned_to_template(_BARE_TEMPLATE, records, date="2026-07-03")
    assert "## Learned" in result
    assert "`new-key`" in result


def test_apply_replaces_existing_section():
    records = [_lr("updated-key", content="Updated insight", confidence=9.0, date="2026-07-03")]
    result = ml.apply_learned_to_template(_TEMPLATE_WITH_LEARNED, records, date="2026-07-03")
    assert "`updated-key`" in result
    assert "`old-key`" not in result


def test_apply_preserves_content_before_learned():
    records = []
    result = ml.apply_learned_to_template(_TEMPLATE_WITH_LEARNED, records, date="2026-07-03")
    assert "## Mission\nDo the work." in result
    assert "## When to escalate\n- Escalate when stuck." in result


def test_apply_idempotent_on_same_records():
    records = [_lr("stable-key", content="Stable insight content", confidence=6.0, date="2026-07-03")]
    first = ml.apply_learned_to_template(_BARE_TEMPLATE, records, date="2026-07-03")
    second = ml.apply_learned_to_template(first, records, date="2026-07-03")
    assert first == second


def test_apply_empty_distilled_emits_placeholder():
    result = ml.apply_learned_to_template(_BARE_TEMPLATE, [], date="2026-07-03")
    assert "no distilled learnings" in result


def test_apply_does_not_duplicate_learned_header():
    records = [_lr("k", content="insight content alpha", confidence=5.0, date="2026-07-03")]
    result = ml.apply_learned_to_template(_BARE_TEMPLATE, records, date="2026-07-03")
    assert result.count("## Learned") == 1


def test_apply_next_section_preserved_after_learned():
    template = (
        "## Mission\nDo work.\n\n"
        "## Learned\n<!-- old -->\n- **2026-01-01** `old` (confidence: 3/10, scope: daslab): Old.\n\n"
        "## Appendix\nExtra section preserved.\n"
    )
    records = [_lr("new", content="new insight here", confidence=8.0, date="2026-07-03")]
    result = ml.apply_learned_to_template(template, records, date="2026-07-03")
    assert "## Appendix\nExtra section preserved." in result
    assert "`new`" in result
    assert "`old`" not in result


def test_roundtrip_backend_eng1():
    feedback_records = [
        _lr(
            "build-before-test",
            content="build dependent packages before running vitest to avoid stale dist failures",
            confidence=6.0,
            scope="daslab",
            project="daslab",
            date="2026-07-01",
        ),
        _lr(
            "build-before-test-corroborate",
            content="run build before running vitest stale dist false failures",
            confidence=5.0,
            scope="daslab",
            project="daslab",
            date="2026-07-02",
        ),
        _lr(
            "full-turbo-build-gate",
            content="validate with full turbo run build not just single filter package",
            confidence=6.0,
            scope="daslab",
            project="daslab",
            date="2026-07-03",
        ),
    ]

    distilled = ml.distill_learnings(
        feedback_records, project="daslab", deny_projects=["qaqnuz"]
    )
    assert len(distilled) >= 1


    keys = [r.get("key", r.get("id", "")) for r in distilled]
    assert any("build" in str(k) for k in keys)


    bare = (
        "# Role — Backend Engineer 1\n\n"
        "## Mission\nImplementation tickets.\n\n"
        "## Scope\n- Owns: backend tickets.\n\n"
        "## Definition of Done\nGreen CI + reviewed PR.\n\n"
        "## When to escalate\n- Escalate to Backend EM.\n"
    )
    result = ml.apply_learned_to_template(bare, distilled, date="2026-07-03")

    assert "## Learned" in result
    assert "DISTILLATION" in result


    for r in distilled:
        if r.get("source_count", 1) > 1:
            assert ml._record_confidence(r) > 6.0


def test_roundtrip_product_analyst():
    feedback_records = [
        _lr(
            "metric-denominator-check",
            content="numeric errors in kpi reports insidious cross check denominator sample window",
            confidence=7.0,
            scope="daslab",
            project="daslab",
            date="2026-07-01",
        ),
        _lr(
            "metric-denominator-check-corroborate",
            content="kpi reports numeric errors denominator cross check before publishing",
            confidence=8.0,
            scope="daslab",
            project="daslab",
            date="2026-07-02",
        ),
        _lr(
            "rollback-first-policy",
            content="revert bad metrics spec before debugging data pipeline preserve integrity",
            confidence=7.0,
            scope="daslab",
            project="daslab",
            date="2026-07-03",
        ),
    ]

    distilled = ml.distill_learnings(
        feedback_records, project="daslab", deny_projects=["qaqnuz"]
    )
    assert len(distilled) >= 1

    bare = (
        "# Role — Product Analyst\n\n"
        "## Mission\nMetrics and KPI reports.\n\n"
        "## Scope\n- Owns: product analytics.\n\n"
        "## Definition of Done\nDelivered with sourced findings.\n\n"
        "## When to escalate\n- Escalate to CPO.\n"
    )
    result = ml.apply_learned_to_template(bare, distilled, date="2026-07-03")

    assert "## Learned" in result
    assert "2026-07-03" in result

    assert "qaqnuz" not in result


def test_roundtrip_deny_boundary_hard():
    platform_record = _lr(
        "platform-insight",
        content="platform unique alpha beta gamma",
        confidence=10.0,
        scope="daslab",
        project="daslab",
    )
    product_record = _lr(
        "product-insight",
        content="product unique delta epsilon zeta",
        confidence=10.0,
        scope="qaqnuz",
        project="qaqnuz",
    )

    result = ml.distill_learnings(
        [platform_record, product_record],
        project="daslab",
        deny_projects=["qaqnuz"],
    )
    keys = [r.get("key") for r in result]
    assert "product-insight" not in keys
    assert "platform-insight" in keys


def test_roundtrip_manager_gate_flagged_not_auto_promoted():
    promotion_candidate = _lr(
        "narrow-insight",
        content="This is a project insight being promoted",
        confidence=9.0,
        scope="org",
        promoted_from="daslab",
    )
    assert ml.needs_manager_gate(promotion_candidate) is True

    native_org = _lr("org-practice", content="Universal git discipline", scope="org")
    assert ml.needs_manager_gate(native_org) is False


def _assert_learned_landing_surface(role_key: str) -> None:
    import gen_agent_templates
    import org_model

    assert role_key in org_model.known_role_keys()
    seed = gen_agent_templates.build_template_for(role_key)
    assert "## Learned" in seed, f"{role_key} template has no ## Learned landing section"
    assert "DISTILLATION" not in seed, f"{role_key} seed template must start undistilled"

    distilled = ml.apply_learned_to_template(
        seed,
        [_lr("k1", "run the migration before the backfill", confidence=8.0)],
        date="2026-07-03",
    )
    assert "## Learned" in distilled
    assert "DISTILLATION" in distilled
    assert "run the migration before the backfill" in distilled
    assert distilled.count("## Learned") == 1

    again = ml.apply_learned_to_template(
        distilled,
        [_lr("k1", "run the migration before the backfill", confidence=8.0)],
        date="2026-07-03",
    )
    assert again == distilled


def test_backend_eng1_template_has_learned_landing_surface():
    _assert_learned_landing_surface("backend-eng-1")


def test_product_analyst_template_has_learned_landing_surface():
    _assert_learned_landing_surface("product-analyst")


def test_every_org_role_has_a_learned_landing_surface():
    import gen_agent_templates
    import org_model

    missing = [
        key
        for key in sorted(org_model.known_role_keys())
        if "## Learned" not in gen_agent_templates.build_template_for(key)
    ]
    assert missing == []
