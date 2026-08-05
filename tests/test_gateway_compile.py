#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import board_lint
import gateway_compile as gc

_MANIFEST = """\
name: {slug}
mission: >
  An AI support agent that resolves tier-1 billing questions in-chat for {slug}
  customers, deflecting tickets from the human queue while never fabricating state.
constraints:
  - "PII: mask account numbers before any model call (tightens org data baseline)"
  - "p95 response latency <= 3s"
stack:
  languages: [python]
  frameworks: [claude-agent-sdk]
  model_providers: [anthropic]
budget:
  money: "USD 1200 / month ceiling"
  tokens: "15M in / 5M out per month"
success_metrics:
  - metric: "tier-1 containment rate"
    target: ">= 55%"
"""

_DISCOVERY = "# Founder Discovery\n\n" + "".join(
    f"Q{i}: discovery question number {i}?\nA{i}: the founder answer number {i}.\n\n"
    for i in range(1, 12)
)

_QUEUE = """\
# APPROVED-GOAL-QUEUE — {slug}

STATUS: TASDIQLANDI 2026-07-03 (Founder approved)

| order | goal_slug | outcome | why_now | research_basis | owner | status | ticket_refs |
|---|---|---|---|---|---|---|---|
| 1 | billing-agent | Deflect 55% of tier-1 billing tickets in-chat | launch window | market scan | cpo | founder_approved | - |
"""

_STAGE_DIRS = (
    "01-planning", "02-design", "03-development",
    "04-testing", "05-deployment", "06-maintenance",
)


def build_pack(tmp_path: Path, slug: str = "acme-helpdesk", **overrides: str) -> Path:
    root = tmp_path / "projects" / slug
    for d in _STAGE_DIRS:
        (root / "docs" / d).mkdir(parents=True, exist_ok=True)
    (root / "PROJECT-OS.yaml").write_text(
        overrides.get("manifest", _MANIFEST.format(slug=slug)), encoding="utf-8")
    (root / "docs" / "01-planning" / "discovery.md").write_text(
        overrides.get("discovery", _DISCOVERY), encoding="utf-8")
    (root / "APPROVED-GOAL-QUEUE.md").write_text(
        overrides.get("queue", _QUEUE.format(slug=slug)), encoding="utf-8")
    (root / "README.md").write_text(f"# {slug}\n\nCharter + stage board.\n", encoding="utf-8")
    return root


def test_valid_pack_compiles_end_to_end(tmp_path):
    root = build_pack(tmp_path)
    res = gc.run_pipeline(root)

    assert res.ok, [str(e) for e in res.errors]
    assert res.rejected_stage is None

    assert len(res.tickets) == 7
    board = root / "board-tickets"
    assert board.is_dir()

    for p in res.tickets:
        text = p.read_text(encoding="utf-8")
        assert "project: acme-helpdesk" in text
    stage_tickets = [p for p in res.tickets if "epic" not in p.name]
    assert len(stage_tickets) == 6
    for p in stage_tickets:
        text = p.read_text(encoding="utf-8")

        assert "Embedded context" in text
        assert "## Acceptance criteria" in text
        assert "## Produces / Consumes" in text
        assert "AADL stage:" in text
        assert "GATE-" in text

    assert res.research_path is not None
    assert res.research_path.is_file()
    assert (root / "docs" / "01-planning") in res.research_path.parents


def test_compiled_tickets_are_board_lint_clean(tmp_path):
    root = build_pack(tmp_path)
    res = gc.run_pipeline(root)
    assert res.ok

    known_roles = board_lint.load_known_roles(REPO_ROOT / "board" / "ROUTING.md")
    tickets = board_lint.load_tickets(root / "board-tickets")
    errors = board_lint.lint_tickets(tickets, known_roles)
    assert errors == [], errors

    assert all(
        "board/tickets/" not in str(p).replace("\\", "/") for p, _ in tickets
    )


def test_stage_tags_cover_all_six_aadl_gates(tmp_path):
    root = build_pack(tmp_path)
    res = gc.run_pipeline(root)
    gates = {
        line.split("stage:", 1)[1].strip()
        for p in res.tickets
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.startswith("stage: GATE-")
    }
    assert gates == {f"GATE-{i}" for i in range(1, 7)}


def test_broken_pack_missing_required_key_rejected(tmp_path):
    bad_manifest = _MANIFEST.format(slug="acme-helpdesk").replace("budget:", "budgetX:")
    root = build_pack(tmp_path, manifest=bad_manifest)
    res = gc.run_pipeline(root)

    assert not res.ok
    assert res.rejected_stage == "validate"
    assert not (root / "board-tickets").exists()
    budget_errs = [e for e in res.errors if e.field == "budget"]
    assert budget_errs, [str(e) for e in res.errors]
    e = budget_errs[0]
    assert e.file == "PROJECT-OS.yaml" and e.problem and e.fix


def test_broken_pack_placeholder_and_deadlink_rejected(tmp_path):
    root = build_pack(tmp_path)
    (root / "docs" / "01-planning" / "objectives.md").write_text(
        "# Objectives\n\nTODO: write the objectives.\n\nSee [design](../02-design/missing.md).\n",
        encoding="utf-8",
    )
    res = gc.run_pipeline(root)
    assert not res.ok
    assert res.rejected_stage == "validate"
    problems = " ".join(e.problem for e in res.errors)
    assert "placeholder" in problems.lower()
    assert "does not resolve" in problems


def test_name_folder_mismatch_rejected(tmp_path):
    root = build_pack(tmp_path, slug="acme-helpdesk",
                      manifest=_MANIFEST.format(slug="wrong-name"))
    res = gc.run_pipeline(root)
    assert not res.ok and res.rejected_stage == "validate"
    assert any(e.field == "name" for e in res.errors)


def test_noncanonical_doctree_rejected(tmp_path):
    root = build_pack(tmp_path)
    (root / "docs" / "02-prd").mkdir()
    res = gc.run_pipeline(root)
    assert not res.ok and res.rejected_stage == "validate"
    assert any("non-canonical" in e.problem for e in res.errors)


def test_unknown_manifest_key_is_a_warning_not_reject(tmp_path):
    manifest = _MANIFEST.format(slug="acme-helpdesk") + "\nmascot: penguin\n"
    root = build_pack(tmp_path, manifest=manifest)
    res = gc.run_pipeline(root)
    assert res.ok
    assert any("mascot" in w for w in res.warnings)


def test_discovery_gate_blocks_and_generates_questions(tmp_path):
    thin = "# Discovery\n\nQ1: only one question?\nA1: only one answer.\n"
    root = build_pack(tmp_path, discovery=thin)
    res = gc.run_pipeline(root)

    assert not res.ok
    assert res.rejected_stage == "discovery-gate"
    assert len(res.questions) >= 10

    assert res.tickets == []
    assert not (root / "board-tickets").exists()
    stage_names = [s.name for s in res.stages]
    assert "approved-check" not in stage_names
    assert "compile" not in stage_names


def test_discovery_waiver_passes_gate(tmp_path):
    root = build_pack(tmp_path, discovery="# Discovery\n\nDISCOVERY-WAIVED by Founder 2026-07-03.\n")
    res = gc.run_pipeline(root)
    assert res.ok


def test_unapproved_queue_blocks_compilation(tmp_path):


    unapproved = (
        "# Goal queue (draft)\n\nawaiting Founder sign-off\n\n"
        "| order | goal_slug | outcome | why_now | research_basis | owner | status | ticket_refs |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | billing-agent | deflect tier-1 tickets | soon | scan | cpo | candidate | - |\n"
    )
    root = build_pack(tmp_path, queue=unapproved)
    res = gc.run_pipeline(root)
    assert not res.ok
    assert res.rejected_stage == "approved-check"
    assert res.tickets == []


def test_approved_check_uses_wired_module(tmp_path, monkeypatch):
    root = build_pack(tmp_path)
    calls: list[str] = []
    real = gc.approved_queue._queue_approved

    def spy(projects_dir, slug):
        calls.append(slug)
        return real(projects_dir, slug)

    monkeypatch.setattr(gc.approved_queue, "_queue_approved", spy)
    res = gc.run_pipeline(root)
    assert res.ok
    assert calls == ["acme-helpdesk"]


def test_constraint_that_relaxes_org_law_rejected(tmp_path):
    manifest = _MANIFEST.format(slug="acme-helpdesk").replace(
        '  - "p95 response latency <= 3s"',
        '  - "waive the GATE-4 testing gate for launch"',
    )
    root = build_pack(tmp_path, manifest=manifest)
    res = gc.run_pipeline(root)
    assert not res.ok and res.rejected_stage == "validate"
    assert any(e.field == "constraints" and "RELAX" in e.problem for e in res.errors)


def test_constraint_that_tightens_org_law_passes(tmp_path):
    manifest = _MANIFEST.format(slug="acme-helpdesk").replace(
        '  - "p95 response latency <= 3s"',
        '  - "require an extra security-lead sign-off beyond org baseline"',
    )
    root = build_pack(tmp_path, manifest=manifest)
    res = gc.run_pipeline(root)
    assert res.ok, [str(e) for e in res.errors]


def test_second_different_pack_compiles_with_no_code_change(tmp_path):
    root = build_pack(tmp_path, slug="fleet-router")
    res = gc.run_pipeline(root)
    assert res.ok, [str(e) for e in res.errors]
    assert len(res.tickets) == 7
    assert all("project: fleet-router" in p.read_text(encoding="utf-8") for p in res.tickets)


def test_cli_returns_1_on_rejection(tmp_path, capsys):
    root = build_pack(tmp_path, discovery="# Discovery\n\nnothing here\n")
    rc = gc.main([str(root)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "discovery" in out.lower()


def test_cli_returns_0_on_compile(tmp_path, capsys):
    root = build_pack(tmp_path)
    rc = gc.main([str(root)])
    assert rc == 0
    assert "COMPILED" in capsys.readouterr().out
