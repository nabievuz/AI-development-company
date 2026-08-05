#!/usr/bin/env python3

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import heartbeat_go_no_go as gng
import kill_switch_drill as ksd

FAIL = gng.FAIL
PASS = gng.PASS
UNKNOWN = gng.UNKNOWN


def _check(key: str, state: str, *, gating: bool = True) -> gng.Check:
    return gng.Check(key, "SI-7", key, state, "detail", "src", gating)


def _clean_day() -> dict:
    return {"t1": 0.70, "t2": 0.10, "t7_holds": True}


def _write_history(path: Path, days: int) -> Path:
    path.write_text(
        "".join(json.dumps(_clean_day()) + "\n" for _ in range(days)), encoding="utf-8"
    )
    return path


def _write_clean_events(path: Path) -> Path:
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in ksd._synthetic_event_log()), encoding="utf-8"
    )
    return path


_BUDGETS_WITH_PLAN = """\
mustaqil:
  caps:
    per_run:
      max_input_tokens: 2_000_000
      max_output_tokens: 400_000
      max_cost_usd: 5.00
    per_day:
      max_input_tokens: 20_000_000
      max_output_tokens: 4_000_000
      max_cost_usd: 15.00
  on_breach: idle_and_alert
  monthly_credit_ceiling:
    active_plan: pro
    plan_credit_usd:
      pro: 20
      max_5x: 100
      max_20x: 200
    on_exhaustion: sanctioned_pause
    metered_overflow: false
"""


_BUDGETS_STRIPPED = """\
mustaqil:
  caps:
    per_run:
      max_cost_usd: 5.00
    per_day:
      max_cost_usd: 15.00
  on_breach: idle_and_alert
  monthly_credit_ceiling:
    active_plan: max_5x
    on_exhaustion: sanctioned_pause
"""


def _write_budgets(path: Path, body: str = _BUDGETS_WITH_PLAN) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _write_interrupts(root: Path, *, answered: bool = True) -> Path:
    d = root / "interrupts"
    d.mkdir(parents=True, exist_ok=True)
    card = {"question": "flip?", "options": ["a"], "ticket": "DAS-1", "payload": {},
            "created_by": "backend-em"}
    if answered:
        card["resume"] = "approved"
    (d / "CARD-1.json").write_text(json.dumps(card), encoding="utf-8")

    (d / "schema.json").write_text(
        json.dumps({"$schema": "x", "required": ["question"]}), encoding="utf-8"
    )
    return d


def _write_features(path: Path, *, on: bool) -> Path:
    path.write_text(f"heartbeat_enabled: {'true' if on else 'false'}\n", encoding="utf-8")
    return path


def test_all_pass_is_go() -> None:
    v = gng.verdict([_check("a", PASS), _check("b", PASS)])
    assert v["go"] is True
    assert v["verdict"] == gng.GO


def test_any_fail_is_no_go() -> None:
    v = gng.verdict([_check("a", PASS), _check("b", FAIL)])
    assert v["go"] is False
    assert v["checked_and_failing"] == ["b"]


def test_unknown_never_counts_as_a_pass() -> None:
    v = gng.verdict([_check("a", PASS), _check("b", UNKNOWN)])
    assert v["go"] is False
    assert v["could_not_check"] == ["b"]
    assert "b" not in v["checked_and_clean"]


def test_empty_gate_list_is_no_go() -> None:
    assert gng.verdict([])["go"] is False


def test_a_novel_state_string_is_not_a_pass() -> None:
    assert gng.verdict([_check("a", "SKIPPED")])["go"] is False
    assert gng.verdict([_check("a", PASS), _check("b", "")])["go"] is False
    assert gng.verdict([_check("a", PASS), _check("b", "pass")])["go"] is False

    assert gng.verdict([_check("a", "SKIPPED")])["could_not_check"] == ["a"]


def test_an_unrecognised_state_still_renders_and_never_looks_like_a_pass() -> None:
    lines = gng._block("SKIPPED", "t", "d", "SI-7")
    assert "PASS" not in lines[0]
    assert "SKIPPED" in lines[0]


def test_context_lines_never_decide_the_verdict() -> None:
    gating = [_check("a", PASS)]
    assert gng.verdict(gating)["go"] is True

    assert _check("info", FAIL, gating=False).gating is False


def test_absent_event_log_is_unknown_not_pass(tmp_path: Path) -> None:
    c = gng.probe_event_log_violations(tmp_path / "nope.jsonl")
    assert c.state == UNKNOWN
    assert "ABSENT" in c.detail
    assert "NOT evidence" in c.detail


def test_empty_event_log_is_unknown_not_pass(tmp_path: Path) -> None:
    empty = tmp_path / "events.jsonl"
    empty.write_text("", encoding="utf-8")
    c = gng.probe_event_log_violations(empty)
    assert c.state == UNKNOWN
    assert "EMPTY" in c.detail


def test_event_log_with_real_clean_events_passes(tmp_path: Path) -> None:
    c = gng.probe_event_log_violations(_write_clean_events(tmp_path / "events.jsonl"))
    assert c.state == PASS
    assert "0 violations" in c.detail


def test_event_log_with_auto_approval_fails(tmp_path: Path) -> None:
    p = _write_clean_events(tmp_path / "events.jsonl")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event_type": "approval", "ticket_id": "DAS-1",
            "created_at": "2026-07-03T12:06:00Z", "approval": "auto",
            "approved_by": "heartbeat", "decision": "approved",
        }) + "\n")
    c = gng.probe_event_log_violations(p)
    assert c.state == FAIL
    assert "1 auto-approved" in c.detail


def test_absent_history_shows_absent_and_raw_zero_of_three(tmp_path: Path) -> None:
    window, _credit, _raw = gng.probe_readiness(
        tmp_path / "nope.jsonl", tmp_path / "no-budgets.yaml", tmp_path / "no-events.jsonl",
        _write_features(tmp_path / "features.yaml", on=False),
    )
    assert window.state == FAIL
    assert "0/3" in window.detail
    assert "0 history row(s)" in window.detail
    assert "ABSENT" in window.detail


def test_absent_budgets_file_is_unknown_not_fail(tmp_path: Path) -> None:
    _window, credit, _raw = gng.probe_readiness(
        tmp_path / "nope.jsonl", tmp_path / "no-budgets.yaml", tmp_path / "no-events.jsonl",
        _write_features(tmp_path / "features.yaml", on=False),
    )
    assert credit.state == UNKNOWN
    assert "COULD NOT CHECK" in credit.detail


def test_absent_interrupt_store_is_unknown(tmp_path: Path) -> None:
    c = gng.probe_interrupt_cards(tmp_path / "nope")
    assert c.state == UNKNOWN


def test_skipping_a_check_yields_unknown_never_a_pass() -> None:
    assert gng.probe_kill_switch_drill(skip=True).state == UNKNOWN
    assert gng.probe_no_daemon(skip=True).state == UNKNOWN


def test_clean_window_of_three_days_passes(tmp_path: Path) -> None:
    window, credit, _raw = gng.probe_readiness(
        _write_history(tmp_path / "h.jsonl", 3),
        _write_budgets(tmp_path / "budgets.yaml"),
        tmp_path / "no-events.jsonl",
        _write_features(tmp_path / "features.yaml", on=False),
    )
    assert window.state == PASS
    assert "3/3" in window.detail
    assert credit.state == PASS


def test_two_clean_days_is_not_enough(tmp_path: Path) -> None:
    window, _c, _raw = gng.probe_readiness(
        _write_history(tmp_path / "h.jsonl", 2),
        _write_budgets(tmp_path / "budgets.yaml"),
        tmp_path / "no-events.jsonl",
        _write_features(tmp_path / "features.yaml", on=False),
    )
    assert window.state == FAIL
    assert "2/3" in window.detail


def test_undeclared_active_plan_fails_the_credit_gate(tmp_path: Path) -> None:
    body = _BUDGETS_WITH_PLAN.replace("    active_plan: pro\n", "")
    _w, credit, _raw = gng.probe_readiness(
        _write_history(tmp_path / "h.jsonl", 3),
        _write_budgets(tmp_path / "budgets.yaml", body),
        tmp_path / "no-events.jsonl",
        _write_features(tmp_path / "features.yaml", on=False),
    )
    assert credit.state == FAIL
    assert "undeclared" in credit.detail


def test_credit_semantics_gate_reads_the_declared_ceiling(tmp_path: Path) -> None:
    p = _write_budgets(tmp_path / "budgets.yaml")
    c = gng.probe_credit_ceiling_shape(p)
    assert c.state == PASS
    import ws_b_health_check as wsb

    assert wsb.check_budget_ceiling_drift(p)["detail"] in c.detail
    assert "metered_overflow: false" in c.detail
    assert "per_run=$5.0/run" in c.detail
    assert "check_budget_ceiling_drift" in c.source


def test_credit_semantics_gate_fails_if_metered_overflow_is_on(tmp_path: Path) -> None:
    body = _BUDGETS_WITH_PLAN.replace("metered_overflow: false", "metered_overflow: true")
    c = gng.probe_credit_ceiling_shape(_write_budgets(tmp_path / "budgets.yaml", body))
    assert c.state == FAIL


def test_credit_semantics_gate_is_unknown_without_budgets(tmp_path: Path) -> None:
    assert gng.probe_credit_ceiling_shape(tmp_path / "nope.yaml").state == UNKNOWN


def test_removed_metered_overflow_key_is_not_a_pass(tmp_path: Path) -> None:
    p = _write_budgets(tmp_path / "budgets.yaml", _BUDGETS_STRIPPED)
    c = gng.probe_credit_ceiling_shape(p)
    assert c.state == FAIL, c.detail

    assert "metered_overflow=False" not in c.detail

    assert "metered_overflow is '__absent__'" in c.detail
    assert "plan_credit_usd missing" in c.detail


def test_the_credit_gate_never_disagrees_with_the_checker_that_owns_it(tmp_path: Path) -> None:
    import ws_b_health_check as wsb

    mutations = [
        _BUDGETS_WITH_PLAN,
        _BUDGETS_STRIPPED,
        _BUDGETS_WITH_PLAN.replace("metered_overflow: false",
                                   "metered_overflow: true"),
        _BUDGETS_WITH_PLAN.replace("metered_overflow: false", ""),
        _BUDGETS_WITH_PLAN.replace("on_exhaustion: sanctioned_pause",
                                   "on_exhaustion: keep_going"),
        _BUDGETS_WITH_PLAN.replace("      max_5x: 100\n", ""),
        _BUDGETS_WITH_PLAN.replace("      max_input_tokens: 2_000_000\n", ""),
        "mustaqil: {}\n",
    ]
    for i, body in enumerate(mutations):
        p = _write_budgets(tmp_path / f"budgets-{i}.yaml", body)
        owner_ok = wsb.check_budget_ceiling_drift(p)["ok"]
        gate = gng.probe_credit_ceiling_shape(p)
        assert (gate.state == PASS) is owner_ok, (i, owner_ok, gate.state, gate.detail)


def test_the_stripped_budgets_file_makes_an_otherwise_clean_state_no_go(tmp_path: Path) -> None:
    kwargs = {
        "history": _write_history(tmp_path / "history.jsonl", 3),
        "events": _write_clean_events(tmp_path / "events.jsonl"),
        "loop_config": REPO_ROOT / "config" / "loop.yaml",
        "board": REPO_ROOT / "board",
        "interrupts": _write_interrupts(tmp_path, answered=True),
        "taxonomy": REPO_ROOT / "config" / "risk_taxonomy.yaml",
        "features": _write_features(tmp_path / "features.yaml", on=False),
        "skip_daemon_scan": True,
        "skip_drill": True,
    }
    stripped = gng.build_report(
        budgets=_write_budgets(tmp_path / "stripped.yaml", _BUDGETS_STRIPPED), **kwargs)
    assert stripped["go"] is False
    assert "credit_semantics" in stripped["summary"]["checked_and_failing"]


    intact = gng.build_report(
        budgets=_write_budgets(tmp_path / "intact.yaml"), **kwargs)
    assert {g["key"]: g["state"] for g in intact["gates"]}["credit_semantics"] == PASS


def test_a_missing_cap_renders_as_MISSING_never_as_a_number(tmp_path: Path) -> None:
    body = _BUDGETS_WITH_PLAN.replace("      max_cost_usd: 5.00\n", "")
    c = gng.probe_credit_ceiling_shape(_write_budgets(tmp_path / "budgets.yaml", body))
    assert "per_run=MISSING/run" in c.detail
    assert "per_day=$15.0/day" in c.detail


def test_a_failing_kill_switch_drill_is_FAIL_not_PASS(monkeypatch) -> None:
    def failing_drill(argv=None):
        print("  pass[000] FAILED: SI-5=BREACHED")
        return 1

    monkeypatch.setattr(ksd, "main", failing_drill)
    c = gng.probe_kill_switch_drill()
    assert c.state == FAIL, c.detail
    assert gng.verdict([c])["go"] is False


def test_a_drill_usage_error_is_unknown_not_pass(monkeypatch) -> None:
    monkeypatch.setattr(ksd, "main", lambda argv=None: (print("  pass[000] x"), 2)[1])
    assert gng.probe_kill_switch_drill().state == UNKNOWN


def test_a_raising_drill_is_unknown_not_pass(monkeypatch) -> None:
    def boom(argv=None):
        raise RuntimeError("drill exploded")

    monkeypatch.setattr(ksd, "main", boom)
    assert gng.probe_kill_switch_drill().state == UNKNOWN


def test_a_failing_daemon_scan_is_FAIL_not_PASS(monkeypatch) -> None:
    import subprocess as _sp

    def failing_run(*_a, **_kw):
        return _sp.CompletedProcess(
            args=["pytest"], returncode=1,
            stdout="1 failed, 42 passed in 0.20s\n", stderr="")

    monkeypatch.setattr(gng.subprocess, "run", failing_run)
    c = gng.probe_no_daemon()
    assert c.state == FAIL, c.detail
    assert "1 failed" in c.detail
    assert gng.verdict([c])["go"] is False


def test_a_failing_never_auto_approve_scan_is_FAIL_not_PASS(monkeypatch) -> None:
    import check_never_auto_approve as naa

    def violating(argv=None):
        print("FAIL: 1 never-auto-approve violation: DAS-9999 gate5_deployment")
        return 1

    monkeypatch.setattr(naa, "main", violating)
    c = gng.probe_never_auto_approve(REPO_ROOT / "board",
                                     REPO_ROOT / "config" / "risk_taxonomy.yaml")
    assert c.state == FAIL, c.detail
    assert "never-auto-approve violation" in c.detail
    assert gng.verdict([c])["go"] is False


def test_every_exit_code_gate_blocks_GO_when_its_checker_fails(monkeypatch) -> None:
    import subprocess as _sp

    import check_never_auto_approve as naa

    monkeypatch.setattr(ksd, "main",
                        lambda argv=None: (print("  pass[000] FAILED"), 1)[1])
    monkeypatch.setattr(naa, "main", lambda argv=None: (print("FAIL: violation"), 1)[1])
    monkeypatch.setattr(gng.subprocess, "run", lambda *_a, **_kw: _sp.CompletedProcess(
        args=["pytest"], returncode=1, stdout="1 failed\n", stderr=""))
    report = gng.build_report()
    states = {g["key"]: g["state"] for g in report["gates"]}
    assert states["kill_switch_drill"] == FAIL, states
    assert states["never_auto_approve"] == FAIL, states
    assert states["no_daemon"] == FAIL, states
    assert report["go"] is False


def test_flag_already_true_fails_the_gate(tmp_path: Path) -> None:
    c = gng.probe_flag(_write_features(tmp_path / "features.yaml", on=True))
    assert c.state == FAIL
    assert "ALREADY" in c.detail


def test_flag_off_passes(tmp_path: Path) -> None:
    assert gng.probe_flag(_write_features(tmp_path / "features.yaml", on=False)).state == PASS


def test_unanswered_interrupt_card_fails(tmp_path: Path) -> None:
    c = gng.probe_interrupt_cards(_write_interrupts(tmp_path, answered=False))
    assert c.state == FAIL
    assert "CARD-1.json" in c.detail


def test_answered_cards_pass_and_schema_file_is_not_a_card(tmp_path: Path) -> None:
    c = gng.probe_interrupt_cards(_write_interrupts(tmp_path, answered=True))
    assert c.state == PASS
    assert "all 1 card(s)" in c.detail


def test_unreadable_card_counts_as_open(tmp_path: Path) -> None:
    d = _write_interrupts(tmp_path, answered=True)
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    c = gng.probe_interrupt_cards(d)
    assert c.state == FAIL
    assert "unreadable" in c.detail


def test_loop_mode_gate_reads_the_real_tripwire() -> None:
    c = gng.probe_loop_mode(REPO_ROOT / "config" / "loop.yaml")
    assert c.state == PASS
    assert "loop off" in c.detail


def test_loop_mode_gate_fails_on_a_live_loop(tmp_path: Path) -> None:
    bad = tmp_path / "loop.yaml"
    bad.write_text(
        "ladder: [shadow, measured, limited_live, full]\nmode: full\nauto_apply: true\n",
        encoding="utf-8",
    )
    assert gng.probe_loop_mode(bad).state == FAIL


def test_rc2_means_could_not_check_in_BOTH_exit_code_config_gates(tmp_path: Path) -> None:
    loop = gng.probe_loop_mode(tmp_path / "no-such-loop.yaml")
    naa = gng.probe_never_auto_approve(tmp_path / "no-board",
                                       REPO_ROOT / "config" / "risk_taxonomy.yaml")
    assert loop.state == UNKNOWN == naa.state, (loop.state, naa.state)
    assert gng.verdict([loop, naa])["could_not_check"] == ["loop_mode", "never_auto_approve"]


def test_never_auto_approve_gate_reports_the_real_ticket_count() -> None:
    c = gng.probe_never_auto_approve(REPO_ROOT / "board",
                                     REPO_ROOT / "config" / "risk_taxonomy.yaml")
    assert c.state == PASS
    assert "0 violations across" in c.detail


def test_never_auto_approve_gate_is_unknown_on_a_missing_board(tmp_path: Path) -> None:
    c = gng.probe_never_auto_approve(tmp_path / "no-board",
                                     REPO_ROOT / "config" / "risk_taxonomy.yaml")
    assert c.state == UNKNOWN


_FORBIDDEN_CALLS = {
    "write_text", "write_bytes", "mkdir", "makedirs", "unlink", "remove", "rmtree",
    "rename", "touch", "mkdtemp", "mkstemp", "NamedTemporaryFile", "TemporaryDirectory",
    "copy", "copy2", "copytree", "safe_dump", "dump",
}


def _write_calls(source: str) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in _FORBIDDEN_CALLS:
            hits.append(f"{name} @ line {node.lineno}")
        if name == "open":
            mode = next((a.value for a in node.args[1:2]
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)), "r")
            kw = next((k.value.value for k in node.keywords
                       if k.arg == "mode" and isinstance(k.value, ast.Constant)), None)
            if any(ch in (kw or mode) for ch in "wax+"):
                hits.append(f"open(mode={kw or mode!r}) @ line {node.lineno}")
    return hits


def _module_source() -> str:
    return (SCRIPTS / "heartbeat_go_no_go.py").read_text(encoding="utf-8")


def test_report_module_contains_no_filesystem_write_call() -> None:
    assert _write_calls(_module_source()) == []


def test_the_no_write_scanner_has_teeth() -> None:
    assert _write_calls(
        "from pathlib import Path\n"
        "def flip():\n"
        "    Path('config/features.yaml').write_text('heartbeat_enabled: true\\n')\n"
    ) != []
    assert _write_calls("def f(p):\n    with open(p, 'w') as fh:\n        fh.write('x')\n") != []
    assert _write_calls("def f(p):\n    with open(p, mode='a') as fh:\n        fh.write('x')\n") != []
    assert _write_calls("import shutil\ndef f(p):\n    shutil.rmtree(p)\n") != []

    assert _write_calls("def f(p):\n    return p.read_text(encoding='utf-8')\n") == []


def test_report_module_never_shells_out_with_shell_true() -> None:
    for node in ast.walk(ast.parse(_module_source())):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                assert not (kw.arg == "shell" and getattr(kw.value, "value", False) is True)


def test_report_module_has_no_feature_flag_mutation_vocabulary() -> None:
    src = (SCRIPTS / "heartbeat_go_no_go.py").read_text(encoding="utf-8")
    for banned in ("heartbeat_enabled: true", "heartbeat_enabled=True",
                   "def set_flag", "def flip", "def enable_heartbeat"):
        assert banned not in src, banned

    assert "DEFAULT_FEATURES = ROOT" in src


def test_running_the_report_does_not_touch_the_real_evidence_trail() -> None:
    events = REPO_ROOT / "board" / ".events.jsonl"
    history = REPO_ROOT / "board" / ".metrics-history.jsonl"
    before = (events.exists(), history.exists())
    features = REPO_ROOT / "config" / "features.yaml"
    flag_before = features.read_text(encoding="utf-8")
    gng.build_report(skip_drill=True, skip_daemon_scan=True)
    assert (events.exists(), history.exists()) == before
    assert features.read_text(encoding="utf-8") == flag_before


def test_the_real_repo_is_honestly_no_go_today() -> None:
    report = gng.build_report(skip_drill=True, skip_daemon_scan=True)
    assert report["go"] is False
    assert report["verdict"] == gng.NO_GO
    gates = {g["key"]: g for g in report["gates"]}
    assert gates["shadow_window"]["state"] == FAIL
    assert "0/3" in gates["shadow_window"]["detail"]


    assert gates["credit_ceiling"]["state"] == PASS


    assert gates["event_log"]["state"] in (PASS, UNKNOWN)
    assert report["is_a_recommendation"] is False


def test_rendered_no_go_says_no_plainly_and_recommends_nothing() -> None:
    text = gng.render(gng.build_report(skip_drill=True, skip_daemon_scan=True))
    assert "VERDICT:  NO-GO" in text
    assert "0/3 consecutive clean day(s)" in text
    assert "COULD NOT CHECK" in text
    assert "UNKNOWN is never a pass" in text

    assert ">= 3 CLEAN DAYS" in text
    assert ">= 7 CLEAN DAYS" in text
    assert ">= 7 ROLLING WAVES" in text
    assert "NOT a clock" in text

    assert "heartbeat_enabled: false  ->  true" in text
    assert "No agent may make that edit" in text
    for advice in ("we recommend", "you should flip", "proceed with the flip"):
        assert advice not in text.lower()


def test_a_fully_clean_scratch_state_flips_the_report_to_GO(tmp_path: Path) -> None:
    report = gng.build_report(
        history=_write_history(tmp_path / "history.jsonl", 3),
        events=_write_clean_events(tmp_path / "events.jsonl"),
        budgets=_write_budgets(tmp_path / "budgets.yaml"),
        loop_config=REPO_ROOT / "config" / "loop.yaml",
        board=REPO_ROOT / "board",
        interrupts=_write_interrupts(tmp_path, answered=True),
        taxonomy=REPO_ROOT / "config" / "risk_taxonomy.yaml",
        features=_write_features(tmp_path / "features.yaml", on=False),
    )
    states = {g["key"]: g["state"] for g in report["gates"]}
    assert report["go"] is True, states
    assert report["verdict"] == gng.GO
    assert set(states.values()) == {PASS}
    text = gng.render(report)
    assert "VERDICT:  GO" in text
    assert "NOT a recommendation to flip" in text


def test_go_flips_back_to_no_go_when_one_input_goes_missing(tmp_path: Path) -> None:
    kwargs = {
        "history": _write_history(tmp_path / "history.jsonl", 3),
        "budgets": _write_budgets(tmp_path / "budgets.yaml"),
        "loop_config": REPO_ROOT / "config" / "loop.yaml",
        "board": REPO_ROOT / "board",
        "interrupts": _write_interrupts(tmp_path, answered=True),
        "taxonomy": REPO_ROOT / "config" / "risk_taxonomy.yaml",
        "features": _write_features(tmp_path / "features.yaml", on=False),
        "skip_daemon_scan": True,
    }
    with_log = gng.build_report(events=_write_clean_events(tmp_path / "events.jsonl"), **kwargs)
    assert {g["key"]: g["state"] for g in with_log["gates"]}["event_log"] == PASS
    without_log = gng.build_report(events=tmp_path / "gone.jsonl", **kwargs)
    assert without_log["go"] is False
    assert "event_log" in without_log["summary"]["could_not_check"]


def test_cli_exit_codes(tmp_path: Path, capsys) -> None:
    assert gng.main(["--skip-drill", "--skip-daemon-scan"]) == 1
    capsys.readouterr()
    assert gng.main([
        "--history", str(_write_history(tmp_path / "history.jsonl", 3)),
        "--events", str(_write_clean_events(tmp_path / "events.jsonl")),
        "--budgets", str(_write_budgets(tmp_path / "budgets.yaml")),
        "--interrupts", str(_write_interrupts(tmp_path, answered=True)),
        "--features", str(_write_features(tmp_path / "features.yaml", on=False)),
        "--skip-daemon-scan",
    ]) == 1
    out = capsys.readouterr().out
    assert "COULD NOT CHECK — skipped by operator" in out


def test_json_output_is_machine_readable() -> None:
    report = gng.build_report(skip_drill=True, skip_daemon_scan=True)
    payload = json.loads(json.dumps(report, default=str))
    assert payload["verdict"] == gng.NO_GO
    assert payload["the_founder_act"].startswith("config/features.yaml")
    assert {g["key"] for g in payload["gates"]} >= {
        "flag_state", "shadow_window", "credit_ceiling", "credit_semantics",
        "kill_switch_drill", "loop_mode", "never_auto_approve", "event_log",
        "interrupt_cards", "no_daemon",
    }
