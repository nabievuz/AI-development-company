from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import claude_invoker as ci
import orchestrator as orch

_TICKET = """---
id: DAS-1001
title: Analyse the platform
status: todo
assignee: cto
project: sale-rentmarket-uz
zone: docs
---

## Acceptance criteria

- the analysis lands in the ticket log
"""


def _board(tmp_path: Path, name: str = "DAS-1001-analyse-platform-g1.md") -> Path:
    board = tmp_path / "tickets"
    board.mkdir(parents=True, exist_ok=True)
    (board / name).write_text(_TICKET, encoding="utf-8")
    return board


def _request(**overrides) -> orch.DispatchRequest:
    fields = {
        "ticket_id": "DAS-1001",
        "role": "cto",
        "model": "opus",
        "zone": "docs",
        "run_id": "run-1-DAS-1001",
        "attempt": 1,
        "goal": "analyse the platform",
    }
    fields.update(overrides)
    return orch.DispatchRequest(**fields)


def test_find_ticket_matches_on_ticket_id(tmp_path: Path) -> None:
    board = _board(tmp_path)
    assert ci.find_ticket(board, "DAS-1001").name == "DAS-1001-analyse-platform-g1.md"


def test_find_ticket_does_not_prefix_match(tmp_path: Path) -> None:
    board = _board(tmp_path, name="DAS-10011-other-g1.md")
    with pytest.raises(ci.InvokerError, match="no ticket file for DAS-1001"):
        ci.find_ticket(board, "DAS-1001")


def test_find_ticket_refuses_ambiguous_matches(tmp_path: Path) -> None:
    board = _board(tmp_path)
    (board / "DAS-1001-duplicate-g2.md").write_text(_TICKET, encoding="utf-8")
    with pytest.raises(ci.InvokerError, match="more than one ticket file"):
        ci.find_ticket(board, "DAS-1001")


def test_missing_board_directory_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ci.InvokerError, match="board directory not found"):
        ci.find_ticket(tmp_path / "absent", "DAS-1001")


def test_role_comes_from_the_ticket_assignee(tmp_path: Path) -> None:
    ticket = ci.find_ticket(_board(tmp_path), "DAS-1001")
    role, model = ci.resolve_role_and_model(ticket, "", "", _REPO_ROOT / "config" / "org.yaml")
    assert role == "cto"
    assert model


def test_unassigned_ticket_is_rejected(tmp_path: Path) -> None:
    board = tmp_path / "tickets"
    board.mkdir()
    (board / "DAS-1002-orphan-g1.md").write_text(
        "---\nid: DAS-1002\nstatus: todo\n---\n\nbody\n", encoding="utf-8"
    )
    ticket = ci.find_ticket(board, "DAS-1002")
    with pytest.raises(ci.InvokerError, match="has no assignee"):
        ci.resolve_role_and_model(ticket, "", "", _REPO_ROOT / "config" / "org.yaml")


def test_unknown_role_has_no_charter() -> None:
    with pytest.raises(ci.InvokerError, match="no agent charter"):
        ci.require_agent("not-a-real-role")


def test_every_org_role_has_a_charter() -> None:
    org = ci.load_org_roles(_REPO_ROOT / "config" / "org.yaml")
    missing = [role for role in org if not (_REPO_ROOT / ".claude" / "agents" / f"{role}.md").is_file()]
    assert missing == []


def test_build_command_carries_role_model_and_project(tmp_path: Path) -> None:
    request = _request()
    argv = ci.build_command(ci.InvokerConfig(), request, "do the thing", tmp_path / "project")
    assert argv[0] == ci.DEFAULT_CLAUDE_BIN
    assert argv[1:3] == ["-p", "do the thing"]
    assert argv[argv.index("--agent") + 1] == "cto"
    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--add-dir") + 1] == str(tmp_path / "project")
    assert "--max-turns" not in argv


def test_build_command_omits_add_dir_without_a_project() -> None:
    argv = ci.build_command(ci.InvokerConfig(), _request(), "prompt", None)
    assert "--add-dir" not in argv


def test_prompt_names_the_ticket_and_the_goal(tmp_path: Path) -> None:
    ticket = ci.find_ticket(_board(tmp_path), "DAS-1001")
    prompt = ci.build_prompt(_request(), ticket, None)
    assert str(ticket) in prompt
    assert "analyse the platform" in prompt
    assert "Do not pick up any other ticket." in prompt


def test_output_from_payload_maps_token_counts() -> None:
    result = ci.output_from_payload(
        {
            "is_error": False,
            "result": "ticket done",
            "usage": {
                "input_tokens": 120,
                "output_tokens": 45,
                "cache_read_input_tokens": 900,
            },
        }
    )
    assert result.output == "ticket done"
    assert result.input_tokens == 120
    assert result.output_tokens == 45
    assert result.cached_input_tokens == 900


def test_output_from_payload_raises_on_a_failed_run() -> None:
    with pytest.raises(ci.InvokerError, match="OAuth session expired"):
        ci.output_from_payload({"is_error": True, "result": "OAuth session expired"})


def test_output_survives_missing_usage_block() -> None:
    result = ci.output_from_payload({"result": "done"})
    assert (result.input_tokens, result.output_tokens, result.cached_input_tokens) == (0, 0, 0)


def test_orchestrator_accepts_what_the_invoker_returns() -> None:
    result = ci.output_from_payload({"result": "done", "usage": {"output_tokens": 7}})
    coerced = orch.coerce_agent_output(result)
    assert coerced.output == "done"
    assert coerced.output_tokens == 7


def test_dry_run_returns_the_command_without_running_claude(tmp_path: Path, monkeypatch) -> None:
    def _explode(*_args, **_kwargs):
        raise AssertionError("claude must not be executed in dry-run")

    monkeypatch.setattr(ci.subprocess, "run", _explode)
    config = ci.InvokerConfig(board_dir=_board(tmp_path), dry_run=True)
    result = ci.invoke_with_config(_request(), config)
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert "--agent" in payload["argv"]


def test_config_reads_the_environment(tmp_path: Path) -> None:
    config = ci.InvokerConfig.from_env(
        {
            "DASLAB_BOARD_DIR": str(tmp_path),
            "DASLAB_PERMISSION_MODE": "bypassPermissions",
            "DASLAB_AGENT_TIMEOUT": "60",
            "DASLAB_INVOKER_DRY_RUN": "1",
        }
    )
    assert config.board_dir == tmp_path.resolve()
    assert config.permission_mode == "bypassPermissions"
    assert config.timeout_seconds == 60.0
    assert config.dry_run is True


def test_config_rejects_a_non_numeric_timeout() -> None:
    with pytest.raises(ci.InvokerError, match="must be a number"):
        ci.InvokerConfig.from_env({"DASLAB_AGENT_TIMEOUT": "soon"})


def test_run_claude_reports_non_json_output(monkeypatch) -> None:
    class _Proc:
        returncode = 0
        stdout = "not json at all"
        stderr = ""

    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(ci.InvokerError, match="did not emit JSON"):
        ci.run_claude(["claude"], ci.InvokerConfig())


def test_run_claude_reports_an_empty_run(monkeypatch) -> None:
    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(ci.InvokerError, match="exited 1 with no stdout: boom"):
        ci.run_claude(["claude"], ci.InvokerConfig())


def test_missing_claude_binary_is_reported(monkeypatch) -> None:
    def _missing(*_args, **_kwargs):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(ci.subprocess, "run", _missing)
    with pytest.raises(ci.InvokerError, match="claude CLI not found"):
        ci.run_claude(["claude"], ci.InvokerConfig())


def test_dry_run_plans_a_worktree_without_creating_one(tmp_path: Path) -> None:
    board = _board(tmp_path)
    config = ci.InvokerConfig(
        board_dir=board, org_root=tmp_path, dry_run=True, worktree_isolation=True
    )
    (tmp_path / "projects" / "sale-rentmarket-uz").mkdir(parents=True)

    payload = json.loads(ci.invoke_with_config(_request(), config).output)

    assert payload["dry_run"] is True
    assert payload["branch"] == "DAS-1001-analyse-platform-g1"
    assert payload["worktree"].endswith("run-1-DAS-1001/DAS-1001")
    assert not (tmp_path / ".worktrees").exists()


def test_isolation_off_points_the_agent_at_the_shared_tree(tmp_path: Path) -> None:
    board = _board(tmp_path)
    project = tmp_path / "projects" / "sale-rentmarket-uz"
    project.mkdir(parents=True)
    config = ci.InvokerConfig(
        board_dir=board, org_root=tmp_path, dry_run=True, worktree_isolation=False
    )

    payload = json.loads(ci.invoke_with_config(_request(), config).output)

    assert payload["worktree"] == ""
    assert str(project) in payload["argv"]


def test_isolation_defaults_on_and_the_env_can_turn_it_off() -> None:
    assert ci.InvokerConfig.from_env({}).worktree_isolation is True
    assert ci.InvokerConfig.from_env({"DASLAB_WORKTREE_ISOLATION": "0"}).worktree_isolation is False


def test_an_unisolatable_project_is_refused_with_the_escape_hatch_named(tmp_path: Path) -> None:
    board = _board(tmp_path)
    project = tmp_path / "projects" / "sale-rentmarket-uz"
    project.mkdir(parents=True)
    config = ci.InvokerConfig(board_dir=board, org_root=tmp_path, worktree_isolation=True)

    with pytest.raises(ci.InvokerError, match="DASLAB_WORKTREE_ISOLATION=0"):
        ci.invoke_with_config(_request(), config)


def test_a_kept_worktree_is_announced_not_swallowed(tmp_path: Path, capsys) -> None:
    path = tmp_path / "wt"
    assert ci.report_teardown("DAS-1", path, "kept-dirty") == "kept-dirty"
    err = capsys.readouterr().err
    assert "DAS-1" in err and "uncommitted work" in err and str(path) in err

    assert ci.report_teardown("DAS-1", path, "kept-failed") == "kept-failed"
    assert "git refused" in capsys.readouterr().err


def test_a_removed_worktree_stays_quiet(tmp_path: Path, capsys) -> None:
    for outcome in ("removed", "removed-ignored", "absent"):
        ci.report_teardown("DAS-1", tmp_path / "wt", outcome)
    assert capsys.readouterr().err == ""


def test_the_isolated_prompt_warns_about_the_missing_install(tmp_path: Path) -> None:
    prompt = ci.build_prompt(_request(), tmp_path / "t.md", tmp_path / "wt", (), isolated=True)
    assert "no installed dependencies" in prompt
    assert "not a\ncode defect" in prompt or "not a code defect" in prompt.replace("\n", " ")


def test_a_taken_branch_is_diagnosed_as_taken_not_as_an_isolation_problem(tmp_path: Path) -> None:
    import run_workspace as rw

    def holding(_repo, _branch):
        return "/somewhere/else/DAS-1"

    original, rw.worktree_holding = rw.worktree_holding, holding
    try:
        message = ci.isolation_failure(_request(), tmp_path, "b1", RuntimeError("boom"))
    finally:
        rw.worktree_holding = original

    assert "already checked out at /somewhere/else/DAS-1" in message
    assert "DASLAB_WORKTREE_ISOLATION=0" not in message


def test_any_other_isolation_failure_still_names_the_escape_hatch(tmp_path: Path) -> None:
    message = ci.isolation_failure(_request(), tmp_path / "nope", "b1", RuntimeError("boom"))
    assert "DASLAB_WORKTREE_ISOLATION=0" in message


def test_verify_is_unverified_until_a_command_is_declared(tmp_path: Path) -> None:
    assert ci.run_verify("", tmp_path, 30) == ci.CI_UNVERIFIED


def test_verify_reports_what_the_command_actually_did(tmp_path: Path) -> None:
    assert ci.run_verify("true", tmp_path, 30) == ci.CI_GREEN
    assert ci.run_verify("false", tmp_path, 30) == ci.CI_RED
    assert ci.run_verify("no_such_command_xyz", tmp_path, 30) == ci.CI_RED


def test_a_merge_is_measured_from_git_not_claimed_by_the_agent(tmp_path: Path) -> None:
    import run_workspace as rw

    calls = {}

    def merged(repo, branch):
        calls["args"] = (repo, branch)
        return True

    original, rw.branch_is_merged = rw.branch_is_merged, merged
    try:
        out = ci.measured_outcome(
            orch.AgentOutput(output="I merged it, honest"), tmp_path, "b1", ci.CI_GREEN
        )
    finally:
        rw.branch_is_merged = original

    assert out.merged_pr is True
    assert out.ci_status == ci.CI_GREEN
    assert calls["args"] == (tmp_path, "b1")


def test_an_agent_claim_alone_never_moves_the_quality_fields(tmp_path: Path) -> None:
    out = ci.measured_outcome(
        orch.AgentOutput(output="merged, CI green, T7 passed"), None, "b1", ci.CI_UNVERIFIED
    )
    assert out.merged_pr is False
    assert out.ci_status == ci.CI_UNVERIFIED
    assert out.t7_pass is False
    assert out.t7_score == 0.0
