
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import agent_eval as ae

EVALS = REPO_ROOT / "evals"
_TS = "2026-07-03T12:00:00Z"


def test_clamp01_bounds() -> None:
    assert ae.clamp01(-1.0) == 0.0
    assert ae.clamp01(2.0) == 1.0
    assert ae.clamp01(0.5) == 0.5


def test_discover_roles_includes_examples() -> None:
    roles = ae.discover_roles(EVALS)
    assert "qa-eng" in roles
    assert "tech-writer" in roles

    assert "README.md" not in roles


def test_discover_tasks_qa_eng() -> None:
    tasks = [t.name for t in ae.discover_tasks("qa-eng", EVALS)]

    assert tasks == ["boundary-values", "coverage-gap", "detect-flaky-assertion"]


def test_score_task_detect_flaky() -> None:
    result = ae.score_task(EVALS / "qa-eng" / "detect-flaky-assertion")
    assert result.k == 3
    assert not result.rubric

    assert [round(a.credit, 4) for a in result.attempts] == [1.0, 1.0, 0.5]
    assert result.accuracy == pytest.approx(0.8333, abs=1e-3)


def test_score_task_coverage_gap() -> None:
    result = ae.score_task(EVALS / "qa-eng" / "coverage-gap")
    assert [round(a.credit, 4) for a in result.attempts] == [1.0, 0.5, 0.5]
    assert result.accuracy == pytest.approx(0.6667, abs=1e-3)


def test_evaluate_role_qa_eng_end_to_end(inert_store_path: Path) -> None:


    card = ae.evaluate_role("qa-eng", "sonnet", EVALS, store_path=inert_store_path)
    assert card.task_count == 3

    assert card.accuracy == pytest.approx(0.8333, abs=1e-3)
    assert card.meets_bar()

    assert card.cost_usd is None


def test_k_limits_attempts() -> None:
    result = ae.score_task(EVALS / "qa-eng" / "detect-flaky-assertion", k=1)
    assert result.k == 1
    assert result.accuracy == pytest.approx(1.0)


def test_k_must_be_positive() -> None:
    with pytest.raises(ae.EvalError):
        ae.score_task(EVALS / "qa-eng" / "coverage-gap", k=0)


def test_rubric_task_reuses_t7() -> None:
    result = ae.score_task(EVALS / "tech-writer" / "release-note")
    assert result.rubric

    assert [round(a.credit, 4) for a in result.attempts] == [0.9, 0.8, 0.7]
    assert result.accuracy == pytest.approx(0.8, abs=1e-6)


def test_rubric_credit_matches_check_t7_weighted_score() -> None:
    import check_t7_quality

    rubric = check_t7_quality.load_rubric(ae.DEFAULT_RUBRIC_PATH)
    scores = {
        "correctness": 1.0,
        "evidence_factuality": 0.5,
        "tests": 0.0,
        "security": 1.0,
        "completeness": 0.0,
        "maintainability": 1.0,
    }
    expected = check_t7_quality.weighted_score(rubric, scores)
    assert ae._rubric_credit(rubric, scores) == pytest.approx(expected)


def test_rubric_clamps_out_of_range_judge() -> None:
    import check_t7_quality

    rubric = check_t7_quality.load_rubric(ae.DEFAULT_RUBRIC_PATH)

    inflated = dict.fromkeys(check_t7_quality.EXPECTED_DIMENSIONS, 5.0)
    assert ae._rubric_credit(rubric, inflated) == pytest.approx(1.0)


def test_shipped_tasks_reject_degenerate_submission() -> None:
    for task_dir in ae.discover_all_tasks(EVALS):
        assert ae.degenerate_credit(task_dir) == 0.0, task_dir


def test_gaming_findings_clean_on_shipped_tree() -> None:
    assert ae.gaming_findings(EVALS) == []


def _write_task(root: Path, role: str, task: str, verify_src: str) -> Path:
    task_dir = root / role / task
    (task_dir / "fixtures").mkdir(parents=True)
    (task_dir / "verify.py").write_text(verify_src, encoding="utf-8")
    subs = task_dir / "submissions"
    subs.mkdir()
    (subs / "attempt-1.json").write_text("{}", encoding="utf-8")
    return task_dir


def test_gameable_task_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    _write_task(
        root,
        "backend-eng-1",
        "always-pass",
        "def verify(submission, fixtures):\n    return 1.0\n",
    )
    findings = ae.gaming_findings(root)
    assert len(findings) == 1
    assert "gameable" in findings[0]


def test_non_gameable_tmp_task_passes(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    _write_task(
        root,
        "backend-eng-1",
        "needs-answer",
        "def verify(submission, fixtures):\n"
        "    return 1.0 if submission.get('answer') == 42 else 0.0\n",
    )
    assert ae.gaming_findings(root) == []


_ANSWER_VERIFY = (
    "def verify(submission, fixtures):\n"
    "    return 1.0 if submission.get('answer') == 42 else 0.0\n"
)


def test_prompt_leak_task_md_answer_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    task_dir = _write_task(root, "backend-eng-1", "leaky", _ANSWER_VERIFY)
    (task_dir / "task.md").write_text(
        '# Task\n\nRequired submission:\n```json\n{"answer": 42}\n```\n', encoding="utf-8"
    )
    findings = ae.prompt_leak_findings(root)
    assert len(findings) == 1 and "prompt-leak" in findings[0]

    assert any("prompt-leak" in f for f in ae.gaming_findings(root))


def test_prompt_leak_partial_overlap_is_flagged(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    verify = (
        "def verify(submission, fixtures):\n"
        "    want = {'a': 1, 'b': 2}\n"
        "    got = submission.get('ans', {})\n"
        "    hits = sum(1 for k, v in want.items() if got.get(k) == v)\n"
        "    return hits / len(want)\n"
    )
    task_dir = _write_task(root, "backend-eng-1", "partial", verify)

    (task_dir / "task.md").write_text(
        '# Task\n\n```json\n{"ans": {"a": 1}}\n```\n', encoding="utf-8"
    )
    findings = ae.prompt_leak_findings(root)
    assert len(findings) == 1 and "prompt-leak" in findings[0]


def test_prompt_leak_placeholder_task_md_passes(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    task_dir = _write_task(root, "backend-eng-1", "clean", _ANSWER_VERIFY)
    (task_dir / "task.md").write_text(
        '# Task\n\nRequired submission:\n```json\n{"answer": <int>}\n```\n', encoding="utf-8"
    )
    assert ae.prompt_leak_findings(root) == []


def test_prompt_leak_missing_task_md_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    _write_task(root, "backend-eng-1", "no-md", _ANSWER_VERIFY)
    assert ae.prompt_leak_findings(root) == []


def test_json_candidates_extracts_literals_skips_placeholders() -> None:
    cands = ae._json_candidates('```json\n{"a": 1}\n``` and [2, 3] and {"b": <int>}')
    assert {"a": 1} in cands
    assert [2, 3] in cands
    assert {"b": "<int>"} not in cands


def test_prompt_leak_findings_clean_on_shipped_tree() -> None:
    assert ae.prompt_leak_findings(EVALS) == []


def test_prompt_leak_scan_reports_its_own_coverage_on_the_shipped_tree() -> None:
    scan = ae.prompt_leak_scan(EVALS)
    assert scan.tasks_total > 0
    assert scan.findings == ()
    if scan.binds_nothing:
        assert "binds\nNOTHING".replace("\n", " ") in scan.coverage_line()
        assert "proves nothing was checked" in scan.coverage_line()
    else:
        assert f"{scan.tasks_with_a_prompt} of {scan.tasks_total}" in scan.coverage_line()


def test_a_corpus_with_no_agent_facing_prompts_reports_that_it_binds_nothing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evals"
    _write_task(root, "backend-eng-1", "no-md", _ANSWER_VERIFY)
    scan = ae.prompt_leak_scan(root)
    assert scan.tasks_total == 1
    assert scan.tasks_with_a_prompt == 0
    assert scan.binds_nothing is True
    assert "binds NOTHING" in scan.coverage_line()


def test_a_corpus_with_prompts_is_not_reported_as_binding_nothing(tmp_path: Path) -> None:
    root = tmp_path / "evals"
    _write_task(root, "backend-eng-1", "has-md", _ANSWER_VERIFY)
    (root / "backend-eng-1" / "has-md" / "task.md").write_text(
        "Answer with a JSON object; no example is given.\n", encoding="utf-8"
    )
    scan = ae.prompt_leak_scan(root)
    assert scan.binds_nothing is False
    assert "1 of 1 task(s) scanned" in scan.coverage_line()


def test_check_gaming_cli_always_states_the_prompt_leak_coverage(capsys) -> None:
    rc = ae.main(["--check-gaming"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "prompt-leak scan:" in err


def _span(agent: str, model: str, in_tok: int, out_tok: int) -> dict:
    return {
        "event_type": "span",
        "ticket_id": "DAS-1487",
        "trace_id": "DAS-1487",
        "span_id": f"span-{agent}",
        "parent_span_id": None,
        "kind": "invoke_agent",
        "gen_ai.agent.name": agent,
        "gen_ai.request.model": model,
        "start": _TS,
        "end": _TS,
        "duration_ms": 0,
        "gen_ai.usage.input_tokens": in_tok,
        "gen_ai.usage.output_tokens": out_tok,
        "gen_ai.usage.cached_input_tokens": 0,
        "cached": False,
        "status": "ok",
        "created_at": _TS,
        "run_id": "run-eval",
    }


def test_role_cost_inert_without_store(inert_store_path: Path) -> None:


    assert ae.role_cost("qa-eng", store_path=inert_store_path) is None


def test_role_cost_from_spans(tmp_path: Path) -> None:
    store = tmp_path / "board" / ".events.jsonl"
    store.parent.mkdir(parents=True)
    spans = [
        _span("qa-eng", "sonnet", 1000, 200),
        _span("frontend-eng-1", "opus", 500, 50),
    ]
    store.write_text("\n".join(json.dumps(s) for s in spans) + "\n", encoding="utf-8")

    cost = ae.role_cost("qa-eng", store_path=store)
    assert cost == pytest.approx(0.006, abs=1e-9)


def test_evaluate_role_pairs_accuracy_with_cost(tmp_path: Path) -> None:
    store = tmp_path / "board" / ".events.jsonl"
    store.parent.mkdir(parents=True)
    store.write_text(json.dumps(_span("qa-eng", "sonnet", 1000, 200)) + "\n", encoding="utf-8")
    card = ae.evaluate_role("qa-eng", "sonnet", EVALS, store_path=store)
    assert card.accuracy == pytest.approx(0.8333, abs=1e-3)
    assert card.cost_usd == pytest.approx(0.006, abs=1e-9)


def test_scorecard_markdown_has_rows(inert_store_path: Path) -> None:
    cards = ae.evaluate_all("sonnet", EVALS, store_path=inert_store_path)
    md = ae.scorecard_markdown(cards)
    assert "| Role | Tier | Tasks | Replay accuracy | Pass (>=80%) | Est. cost (USD) |" in md
    assert "`qa-eng`" in md
    assert "`tech-writer`" in md
    assert "PASS" in md
    assert "n/a (inert)" in md


def test_scorecard_to_dict_shape(inert_store_path: Path) -> None:
    card = ae.evaluate_role("qa-eng", "sonnet", EVALS, store_path=inert_store_path)
    d = card.to_dict()
    assert d["role"] == "qa-eng"
    assert d["tier"] == "sonnet"
    assert d["accuracy"] == 0.8333
    assert d["bar"] == ae.PASS_BAR
    assert d["passed"] is True
    assert d["cost_usd"] is None
    assert {t["task_id"] for t in d["tasks"]} == {
        "boundary-values", "coverage-gap", "detect-flaky-assertion",
    }


def test_no_store_path_none_literal_in_this_file() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    guarded = {"role_cost", "evaluate_role", "evaluate_all"}
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name not in guarded:
            continue


        for kw in node.keywords:
            if kw.arg == "store_path" and _is_none(kw.value):
                offenders.append(node.lineno)
    assert not offenders, (
        f"store_path=None passed to {sorted(guarded)} at line(s) {offenders} — "
        "use the inert_store_path fixture instead (DAS-1651); None reads the "
        "real ambient board/.events.jsonl, not an inert store."
    )


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def test_pass_bar_default_is_80pct() -> None:
    assert ae.PASS_BAR == 0.80


def test_meets_bar_uses_custom_threshold(inert_store_path: Path) -> None:
    card = ae.RoleScorecard(role="x", tier="sonnet", tasks=[])
    assert not card.meets_bar()
    empty = ae.RoleScorecard(role="y", tier="sonnet", tasks=[])
    assert empty.accuracy == 0.0


    qa = ae.evaluate_role("qa-eng", "sonnet", EVALS, store_path=inert_store_path)
    assert qa.meets_bar(0.80)
    assert not qa.meets_bar(0.90)


def test_all_covered_roles_meet_bar(inert_store_path: Path) -> None:
    cards = ae.evaluate_all("sonnet", EVALS, store_path=inert_store_path)
    covered = {"qa-eng", "tech-writer", "backend-eng-1", "security-eng",
               "product-analyst", "sre-eng"}
    scored = {c.role for c in cards}
    assert covered <= scored
    for c in cards:
        assert c.meets_bar(), f"{c.role} below bar at {c.accuracy:.3f}"


def test_scorecard_markdown_flags_failing_role() -> None:
    passing = ae.RoleScorecard(
        role="good", tier="sonnet",
        tasks=[ae.TaskResult(role="good", task_id="t",
                             attempts=[ae.AttemptResult(0, 1.0)])],
    )
    failing = ae.RoleScorecard(role="bad", tier="sonnet", tasks=[])
    md = ae.scorecard_markdown([passing, failing])
    assert "PASS" in md
    assert "FAIL" in md


def test_cli_role(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--role", "qa-eng", "--tier", "sonnet", "--evals", str(EVALS)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "qa-eng" in out
    assert "accuracy=0.833" in out


def test_cli_roster(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--roster", "--evals", str(EVALS)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Role | Tier | Tasks | Replay accuracy | Pass (>=80%) | Est. cost (USD) |" in out


def test_cli_check_gaming_clean(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--check-gaming", "--evals", str(EVALS)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_check_gaming_flags_gameable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "evals"
    _write_task(
        root, "backend-eng-1", "always-pass",
        "def verify(submission, fixtures):\n    return 1.0\n",
    )
    rc = ae.main(["--check-gaming", "--evals", str(root)])
    assert rc == 1


def test_cli_enforce_passes_on_covered_tree(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--all", "--tier", "sonnet", "--evals", str(EVALS), "--enforce"])
    assert rc == 0


def test_cli_enforce_fails_below_bar(tmp_path: Path) -> None:
    root = tmp_path / "evals"


    _write_task(
        root, "backend-eng-1", "needs-answer",
        "def verify(submission, fixtures):\n"
        "    return 1.0 if submission.get('answer') == 42 else 0.0\n",
    )
    rc = ae.main(["--all", "--evals", str(root), "--enforce"])
    assert rc == 1


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ae.main(["--all", "--tier", "sonnet", "--evals", str(EVALS), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    roles = {rec["role"] for rec in payload}
    assert {"qa-eng", "tech-writer"} <= roles


def test_harness_declares_that_no_model_is_invoked() -> None:
    assert ae.LIVE_MODEL_INVOKED is False
    assert ae.HARNESS_KIND == "deterministic_submission_replay"
    summary = ae.HARNESS_SUMMARY.lower()
    assert "no model is invoked" in summary
    assert "no agent is run" in summary


def test_harness_imports_no_model_client() -> None:
    source = (SCRIPTS / "agent_eval.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "anthropic", "openai", "httpx", "requests", "urllib", "http",
        "aiohttp", "socket", "litellm",
    }
    assert not (imported & forbidden), (
        f"agent_eval imports {sorted(imported & forbidden)} — it claims no model "
        "is invoked, so it must not carry a network or model client"
    )


def test_scorecard_dict_states_the_harness_kind(inert_store_path: Path) -> None:
    card = ae.evaluate_role("qa-eng", "sonnet", EVALS, store_path=inert_store_path)
    d = card.to_dict()
    assert d["live_model_invoked"] is False
    assert d["harness_kind"] == ae.HARNESS_KIND
    assert d["tier_source"] == ae.TIER_FROM_OVERRIDE


def test_cli_help_states_plainly_that_no_model_is_invoked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        ae.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out.lower()
    assert "no model is invoked" in out
    assert "replays" in out


def test_tier_defaults_to_the_org_allocation_not_free_text(
    inert_store_path: Path,
) -> None:
    import org_model

    for role in ("qa-eng", "tech-writer", "cto"):
        card = ae.evaluate_role(role, None, EVALS, store_path=inert_store_path)
        assert card.tier == str(org_model.model_for(role))
        assert card.tier_source == ae.TIER_FROM_ORG
        assert card.tier != "unspecified"


def test_org_allocation_is_not_uniform_across_roles(inert_store_path: Path) -> None:
    cards = ae.evaluate_all(None, EVALS, store_path=inert_store_path)
    tiers = {c.tier for c in cards}
    assert tiers <= set(ae.KNOWN_TIERS)
    assert len(tiers) > 1


def test_known_tiers_are_exactly_the_org_model_tiers() -> None:
    import org_model

    assert set(ae.KNOWN_TIERS) == {str(m) for m in org_model.Model}
    assert "unspecified" not in ae.KNOWN_TIERS


@pytest.mark.parametrize("bogus", ["unspecified", "premium", "fable", "SONNET", ""])
def test_free_text_tier_is_refused(bogus: str) -> None:
    with pytest.raises(ae.EvalError):
        ae.validate_tier(bogus)
    with pytest.raises(ae.EvalError):
        ae.evaluate_role("qa-eng", bogus, EVALS)


def test_role_outside_the_org_model_is_refused_not_labelled_unspecified() -> None:
    with pytest.raises(ae.EvalError) as excinfo:
        ae.allocated_tier("not-a-real-role")
    assert "not-a-real-role" in str(excinfo.value)


def test_cli_refuses_an_unknown_tier(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        ae.main(["--role", "qa-eng", "--tier", "unspecified", "--evals", str(EVALS)])
    assert excinfo.value.code == 2
    assert "unspecified" in capsys.readouterr().err


def test_cli_refuses_a_role_with_no_org_allocation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "evals"
    _write_task(
        root, "invented-role", "needs-answer",
        "def verify(submission, fixtures):\n"
        "    return 1.0 if submission.get('answer') == 42 else 0.0\n",
    )
    rc = ae.main(["--all", "--evals", str(root)])
    assert rc == 2
    assert "invented-role" in capsys.readouterr().err


def test_cli_plain_output_labels_the_tier_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = ae.main(["--role", "qa-eng", "--evals", str(EVALS)])
    assert rc == 0
    out = capsys.readouterr().out
    assert ae.SCORECARD_BANNER in out
    assert f"tier sonnet <- {ae.TIER_FROM_ORG}" in out
    assert "replayed accuracy=0.833" in out


def test_scorecard_markdown_carries_the_no_model_banner(
    inert_store_path: Path,
) -> None:
    cards = ae.evaluate_all("sonnet", EVALS, store_path=inert_store_path)
    md = ae.scorecard_markdown(cards)
    assert md.splitlines()[0] == ae.SCORECARD_BANNER
    assert "no model was invoked" in md


_RESTORED_TASKS: tuple[tuple[str, str], ...] = (
    ("backend-em", "api-design-review"),
    ("backend-em", "escalate-or-delegate"),
    ("backend-em", "merge-decision"),
    ("backend-eng-1", "idempotency"),
    ("backend-eng-2", "diagnose-500"),
    ("board-member", "adr-signoff-check"),
    ("chairman", "adr-ratify-gate"),
    ("content-lead", "consistency-audit"),
    ("content-lead", "style-guide-violations"),
    ("legal-analyst", "missing-clause-check"),
    ("legal-analyst", "regulatory-flag-scan"),
    ("tech-writer", "doc-link-check"),
)


@pytest.mark.parametrize(("role", "task"), _RESTORED_TASKS)
def test_restored_task_scores_its_committed_submissions(role: str, task: str) -> None:
    result = ae.score_task(EVALS / role / task)
    assert result.k == 3
    assert result.accuracy > 0.0, f"{role}/{task} grades every committed answer wrong"
    assert ae.degenerate_credit(EVALS / role / task) == 0.0


def test_no_shipped_task_depends_on_a_markdown_fixture() -> None:
    stragglers = sorted(
        str(p.relative_to(EVALS))
        for task_dir in ae.discover_all_tasks(EVALS)
        for p in (task_dir / "fixtures").rglob("*.md")
    )
    assert stragglers == []


def test_every_shipped_task_has_a_readable_fixture_set() -> None:
    broken: list[str] = []
    for task_dir in ae.discover_all_tasks(EVALS):
        try:
            ae.score_task(task_dir)
        except ae.EvalError as exc:
            broken.append(f"{task_dir.parent.name}/{task_dir.name}: {exc}")
    assert broken == []


def test_consistency_audit_grades_the_restored_documents() -> None:
    task = EVALS / "content-lead" / "consistency-audit"
    module = ae.load_verifier(task)
    assert ae.score_submission(
        module, {"inconsistent_docs": ["doc-b.md", "doc-c.md"]}, task
    ) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"inconsistent_docs": ["doc-a.md", "doc-d.md"]}, task
    ) == pytest.approx(0.0)


def test_doc_link_check_grades_the_restored_document() -> None:
    task = EVALS / "tech-writer" / "doc-link-check"
    module = ae.load_verifier(task)
    assert ae.score_submission(
        module, {"broken_links": ["docs/legacy.md", "docs/removed.md"]}, task
    ) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"broken_links": ["docs/setup.md"]}, task
    ) == pytest.approx(0.0)


def test_adr_ratify_gate_grades_the_restored_draft() -> None:
    task = EVALS / "chairman" / "adr-ratify-gate"
    module = ae.load_verifier(task)
    assert ae.score_submission(
        module, {"missing_sections": ["Decision", "Consequences"]}, task
    ) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"missing_sections": ["Context"]}, task
    ) == pytest.approx(0.0)


def test_missing_clause_check_grades_the_restored_msa() -> None:
    task = EVALS / "legal-analyst" / "missing-clause-check"
    module = ae.load_verifier(task)
    expected = [
        "indemnification", "limitation_of_liability", "data_breach_notification",
        "assignment", "termination",
    ]
    assert ae.score_submission(module, {"missing_clauses": expected}, task) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"missing_clauses": ["confidentiality", "governing_law"]}, task
    ) == pytest.approx(0.0)


def test_idempotency_expectation_comes_from_the_restored_endpoint() -> None:
    task = EVALS / "backend-eng-1" / "idempotency"
    module = ae.load_verifier(task)
    assert ae.score_submission(
        module, {"idempotent": True, "mechanism": "idempotency_key"}, task
    ) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"idempotent": False, "mechanism": "idempotency_key"}, task
    ) == pytest.approx(0.5)


def test_diagnose_500_expectation_comes_from_the_restored_incident() -> None:
    task = EVALS / "backend-eng-2" / "diagnose-500"
    module = ae.load_verifier(task)
    assert ae.score_submission(
        module, {"root_cause": "null_reference", "fix": "null_check"}, task
    ) == pytest.approx(1.0)
    assert ae.score_submission(
        module, {"root_cause": "deadlock", "fix": "null_check"}, task
    ) == pytest.approx(0.5)


def _copy_fixture_task(src: Path, dest_root: Path, role: str, task: str) -> Path:
    import shutil

    dest = dest_root / role / task
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return dest


def test_emptied_document_fixture_raises_instead_of_scoring_zero(tmp_path: Path) -> None:
    task = _copy_fixture_task(
        EVALS / "content-lead" / "consistency-audit",
        tmp_path / "evals", "content-lead", "consistency-audit",
    )
    (task / "fixtures" / "docs.json").write_text(
        json.dumps({"documents": {}}), encoding="utf-8"
    )
    module = ae.load_verifier(task)
    with pytest.raises(ae.EvalError):
        ae.score_submission(module, {"inconsistent_docs": ["doc-b.md"]}, task)


def test_a_task_whose_fixture_grades_nothing_is_reported_as_a_finding(
    tmp_path: Path,
) -> None:
    task = _copy_fixture_task(
        EVALS / "tech-writer" / "doc-link-check",
        tmp_path / "evals", "tech-writer", "doc-link-check",
    )
    (task / "fixtures" / "files.json").write_text(
        json.dumps({"files": ["docs/setup.md", "docs/api.md",
                              "docs/legacy.md", "docs/removed.md"]}),
        encoding="utf-8",
    )
    findings = ae.gaming_findings(tmp_path / "evals")
    assert len(findings) == 1
    assert "no broken links" in findings[0]


def test_deleted_document_fixture_is_reported_not_silently_zero(tmp_path: Path) -> None:
    task = _copy_fixture_task(
        EVALS / "legal-analyst" / "missing-clause-check",
        tmp_path / "evals", "legal-analyst", "missing-clause-check",
    )
    (task / "fixtures" / "msa.json").unlink()
    module = ae.load_verifier(task)
    with pytest.raises(ae.EvalError):
        ae.score_submission(module, {"missing_clauses": ["termination"]}, task)
