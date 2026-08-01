"""tests/test_board_lint.py — pytest suite for scripts/board_lint.py.

Each test builds a minimal in-memory board (a dict mapping ticket ID ->
frontmatter dict) or a temporary directory of .md files, then asserts that
the linter fires exactly the expected error(s).

Rules under test
----------------
R1  bad status enum
R2  unknown assignee
R3  unknown author
R4  missing parent (dangling parent reference)
R5  orphan subtask (has parent, no goal)
R6  in_review self-review
R7  required field missing
R8  invalid priority
R9  project: field forbidden on the org board/tickets/ (platform-only)
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Make sure the scripts/ directory is importable regardless of how pytest is
# invoked.
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from board_lint import (  # noqa: E402
    _schema_names_of,
    lint_tickets,
    load_known_roles,
    load_tickets,
    same_zone_pair_allowed,
    zone_wave_conflicts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KNOWN_ROLES = frozenset(
    {
        "qa-eng",
        "qa-lead",
        "cto",
        "backend-eng-1",
        "backend-em",
        "senior-pm",
        "ceo",
        "sre-lead",
    }
)

_BASE_FM: dict[str, str] = {
    "id": "DAS-9001",
    "title": "Fixture ticket",
    "status": "todo",
    "assignee": "qa-eng",
    "author": "ceo",
    "dept": "engineering",
    "priority": "p1",
    "created": "2026-06-18",
    "updated": "2026-06-18",
    "parent": "",
    "goal": "",
}


def make_ticket(**overrides: str) -> dict[str, str]:
    """Return a valid frontmatter dict with the given fields overridden."""
    fm = dict(_BASE_FM)
    fm.update(overrides)
    return fm


def run_lint(tickets: list[dict[str, str]]) -> list[str]:
    """Run lint_tickets with a Path placeholder and return the error list."""
    fake_path = Path("board/tickets/DAS-FAKE.md")
    pairs = [(fake_path, t) for t in tickets]
    return lint_tickets(pairs, _KNOWN_ROLES)


def make_ticket_file(tmp_path: Path, fm: dict[str, str]) -> Path:
    """Write a full ticket .md file to *tmp_path* and return its path."""
    ticket_id = fm["id"]
    # load_tickets uses glob "DAS-*.md" — keep the DAS- prefix uppercase
    path = tmp_path / f"{ticket_id}-fixture.md"
    lines = ["---"]
    for k, v in fm.items():
        # Skip keys with empty values so parent/goal absence is explicit
        lines.append(f"{k}: {v}")
    lines += ["---", "", "## Description", "Fixture.", "", "## Log"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# R1 — bad status enum
# ---------------------------------------------------------------------------


def test_bad_status_fires() -> None:
    ticket = make_ticket(status="shipped")
    errors = run_lint([ticket])
    assert any("invalid status" in e for e in errors), errors
    assert any("shipped" in e for e in errors), errors


def test_valid_statuses_are_accepted() -> None:
    valid = (
        "backlog", "todo", "in_progress", "blocked", "in_review", "done",
        "interrupted",
    )
    for s in valid:
        ticket = make_ticket(status=s, assignee="qa-lead", author="ceo")
        errors = run_lint([ticket])
        status_errors = [e for e in errors if "invalid status" in e]
        assert not status_errors, f"Status '{s}' unexpectedly flagged: {errors}"


# ---------------------------------------------------------------------------
# R1 (interrupted) — new 'interrupted' status (DAS-1446)
# ---------------------------------------------------------------------------


def test_interrupted_status_accepted() -> None:
    """A well-formed 'interrupted' ticket must lint clean (DAS-1446 positive)."""
    ticket = make_ticket(status="interrupted", assignee="backend-eng-1", author="ceo")
    errors = run_lint([ticket])
    assert not errors, errors


def test_interrupted_not_subject_to_self_review_r8() -> None:
    """R8 is scoped to in_review; an 'interrupted' ticket with assignee == author
    must NOT be flagged as self-review (DAS-1446 consumer sweep, R8 untouched)."""
    ticket = make_ticket(status="interrupted", assignee="qa-eng", author="qa-eng")
    errors = run_lint([ticket])
    assert not any("self-review" in e for e in errors), errors


def test_unknown_status_still_rejected() -> None:
    """The enum stays closed: an unknown status is still rejected (DAS-1446
    negative — 'interrupted' did not open the gate to arbitrary values)."""
    ticket = make_ticket(status="interupted")  # typo, not the real value
    errors = run_lint([ticket])
    assert any("invalid status" in e for e in errors), errors


def test_load_tickets_interrupted_file(tmp_path: Path) -> None:
    """An 'interrupted' ticket written to disk lints clean via load_tickets —
    exercises the real linter end-to-end (DAS-1446 acceptance)."""
    fm = make_ticket(
        id="DAS-9004", status="interrupted", assignee="backend-eng-1", author="ceo"
    )
    make_ticket_file(tmp_path, fm)
    loaded = load_tickets(tmp_path)
    errors = lint_tickets(loaded, _KNOWN_ROLES)
    assert not errors, errors


# ---------------------------------------------------------------------------
# R2 — unknown assignee
# ---------------------------------------------------------------------------


def test_unknown_assignee_fires() -> None:
    ticket = make_ticket(assignee="ghost-user")
    errors = run_lint([ticket])
    assert any("unknown assignee" in e for e in errors), errors
    assert any("ghost-user" in e for e in errors), errors


def test_empty_assignee_is_accepted() -> None:
    """Empty assignee means 'needs routing' — that is valid per board rules."""
    ticket = make_ticket(assignee="")
    errors = run_lint([ticket])
    assignee_errors = [e for e in errors if "unknown assignee" in e]
    assert not assignee_errors, errors


# ---------------------------------------------------------------------------
# R3 — unknown author
# ---------------------------------------------------------------------------


def test_unknown_author_fires() -> None:
    ticket = make_ticket(author="nobody")
    errors = run_lint([ticket])
    assert any("unknown author" in e for e in errors), errors
    assert any("nobody" in e for e in errors), errors


# ---------------------------------------------------------------------------
# R4 — dangling parent reference
# ---------------------------------------------------------------------------


def test_dangling_parent_fires() -> None:
    """A parent ID that doesn't exist in the board should be flagged."""
    ticket = make_ticket(parent="DAS-9999", goal="v1-release")
    errors = run_lint([ticket])
    assert any("does not exist" in e for e in errors), errors
    assert any("DAS-9999" in e for e in errors), errors


def test_valid_parent_is_accepted() -> None:
    """When the parent ticket is in the same board, no error should fire."""
    parent_ticket = make_ticket(id="DAS-9000", status="done", parent="", goal="v1-release")
    child_ticket = make_ticket(
        id="DAS-9001", parent="DAS-9000", goal="v1-release"
    )
    fake_path = Path("board/tickets/DAS-FAKE.md")
    pairs = [(fake_path, parent_ticket), (fake_path, child_ticket)]
    errors = lint_tickets(pairs, _KNOWN_ROLES)
    parent_errors = [e for e in errors if "does not exist" in e]
    assert not parent_errors, errors


# ---------------------------------------------------------------------------
# R5 — orphan subtask (parent set but goal missing)
# ---------------------------------------------------------------------------


def test_orphan_subtask_fires() -> None:
    """Subtask with parent but no goal is an orphan — must be flagged."""
    parent_ticket = make_ticket(id="DAS-9000", parent="", goal="v1-release")
    orphan = make_ticket(id="DAS-9001", parent="DAS-9000", goal="")
    fake_path = Path("board/tickets/DAS-FAKE.md")
    pairs = [(fake_path, parent_ticket), (fake_path, orphan)]
    errors = lint_tickets(pairs, _KNOWN_ROLES)
    assert any("no 'goal'" in e or "goal" in e for e in errors), errors


# ---------------------------------------------------------------------------
# R6 — in_review self-review
# ---------------------------------------------------------------------------


def test_in_review_self_review_fires() -> None:
    ticket = make_ticket(status="in_review", assignee="qa-eng", author="qa-eng")
    errors = run_lint([ticket])
    assert any("self-review" in e for e in errors), errors


def test_in_review_different_reviewer_accepted() -> None:
    ticket = make_ticket(status="in_review", assignee="qa-lead", author="qa-eng")
    errors = run_lint([ticket])
    self_review_errors = [e for e in errors if "self-review" in e]
    assert not self_review_errors, errors


# ---------------------------------------------------------------------------
# R7 — required field missing
# ---------------------------------------------------------------------------


def test_missing_required_field_fires() -> None:
    ticket = make_ticket()
    del ticket["priority"]
    errors = run_lint([ticket])
    assert any("missing required field" in e for e in errors), errors
    assert any("priority" in e for e in errors), errors


def test_all_required_fields_accepted() -> None:
    ticket = make_ticket()
    errors = run_lint([ticket])
    required_errors = [e for e in errors if "missing required field" in e]
    assert not required_errors, errors


# ---------------------------------------------------------------------------
# R8 — invalid priority
# ---------------------------------------------------------------------------


def test_invalid_priority_fires() -> None:
    ticket = make_ticket(priority="critical")
    errors = run_lint([ticket])
    assert any("invalid priority" in e for e in errors), errors
    assert any("critical" in e for e in errors), errors


def test_valid_priorities_accepted() -> None:
    for p in ("p0", "p1", "p2"):
        ticket = make_ticket(priority=p)
        errors = run_lint([ticket])
        prio_errors = [e for e in errors if "invalid priority" in e]
        assert not prio_errors, f"Priority '{p}' unexpectedly flagged: {errors}"


# ---------------------------------------------------------------------------
# R9 — project: field forbidden on the org board (platform-only)
# ---------------------------------------------------------------------------


def test_project_field_on_org_board_fires() -> None:
    """A board/tickets/ ticket that declares project: must be flagged —
    project tickets belong in projects/<slug>/board-tickets/."""
    ticket = make_ticket(project="acme-app")
    errors = run_lint([ticket])  # run_lint uses a board/tickets/ path
    assert any("project tickets belong in" in e for e in errors), errors
    assert any("acme-app" in e for e in errors), errors


def test_no_project_field_on_org_board_ok() -> None:
    """An org-engine ticket (no project: field) on board/tickets/ is fine."""
    ticket = make_ticket()
    errors = run_lint([ticket])
    project_errors = [e for e in errors if "project tickets belong in" in e]
    assert not project_errors, errors


def test_project_field_on_project_board_is_exempt() -> None:
    """The same project: field on a project's own board (…/board-tickets/) is
    valid and must NOT fire R9."""
    ticket = make_ticket(project="acme-app")
    project_path = Path("projects/acme-app/board-tickets/DAS-7001-x.md")
    pairs = [(project_path, ticket)]
    errors = lint_tickets(pairs, _KNOWN_ROLES)
    project_errors = [e for e in errors if "project tickets belong in" in e]
    assert not project_errors, errors


# ---------------------------------------------------------------------------
# R10 — merge_policy grammar + zone anchor (DAS-1448)
# ---------------------------------------------------------------------------


def test_merge_policy_valid_forms_accepted() -> None:
    for pol in ("append-only", "owner-exclusive", "aggregate:sum", "aggregate:union"):
        ticket = make_ticket(zone="scripts/x", merge_policy=pol)
        errors = run_lint([ticket])
        mp_errors = [e for e in errors if "merge_policy" in e]
        assert not mp_errors, f"policy '{pol}' unexpectedly flagged: {errors}"


def test_merge_policy_empty_value_fires() -> None:
    ticket = make_ticket(zone="scripts/x", merge_policy="")
    errors = run_lint([ticket])
    assert any("merge_policy is present but empty" in e for e in errors), errors


def test_merge_policy_unknown_value_fires() -> None:
    ticket = make_ticket(zone="scripts/x", merge_policy="aggregate:max")
    errors = run_lint([ticket])
    assert any("invalid merge_policy" in e for e in errors), errors


def test_merge_policy_without_zone_fires() -> None:
    ticket = make_ticket(merge_policy="append-only")  # no zone anchor
    errors = run_lint([ticket])
    assert any("merge_policy declared without a zone" in e for e in errors), errors


def test_no_merge_policy_is_clean() -> None:
    """Additive: a ticket without merge_policy lints exactly as before."""
    ticket = make_ticket(zone="scripts/x")
    errors = run_lint([ticket])
    assert not any("merge_policy" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Wave correctness guard — same-zone pair decision (DAS-1448, SAFETY)
# ---------------------------------------------------------------------------


def test_same_zone_pair_forbidden_without_policy() -> None:
    """DEFAULT: two same-zone tickets with no merge_policy may NOT co-dispatch."""
    a = make_ticket(id="DAS-9001", zone="scripts/board_lint")
    b = make_ticket(id="DAS-9002", zone="scripts/board_lint")
    assert same_zone_pair_allowed(a, b) is False


def test_same_zone_pair_permitted_with_shared_policy() -> None:
    """OPT-IN: same zone + same valid permitting policy → co-dispatch allowed."""
    a = make_ticket(id="DAS-9001", zone="scripts/log", merge_policy="append-only")
    b = make_ticket(id="DAS-9002", zone="scripts/log", merge_policy="append-only")
    assert same_zone_pair_allowed(a, b) is True


def test_same_zone_pair_forbidden_with_mismatched_policy() -> None:
    """Fail-closed: the two tickets must declare the SAME policy."""
    a = make_ticket(id="DAS-9001", zone="scripts/log", merge_policy="append-only")
    b = make_ticket(id="DAS-9002", zone="scripts/log", merge_policy="owner-exclusive")
    assert same_zone_pair_allowed(a, b) is False


def test_same_zone_pair_forbidden_with_invalid_policy() -> None:
    """Fail-closed: an invalid policy on both never widens the guard."""
    a = make_ticket(id="DAS-9001", zone="scripts/log", merge_policy="aggregate:max")
    b = make_ticket(id="DAS-9002", zone="scripts/log", merge_policy="aggregate:max")
    assert same_zone_pair_allowed(a, b) is False


def test_different_zones_not_a_same_zone_pair() -> None:
    """Guard is silent for different (or absent) zones — pair allowed."""
    a = make_ticket(id="DAS-9001", zone="scripts/a")
    b = make_ticket(id="DAS-9002", zone="scripts/b")
    assert same_zone_pair_allowed(a, b) is True
    c = make_ticket(id="DAS-9003")  # no zone at all
    d = make_ticket(id="DAS-9004")
    assert same_zone_pair_allowed(c, d) is True


def test_zone_wave_conflicts_rejects_unpermitted_pair() -> None:
    fake = Path("board/tickets/DAS-FAKE.md")
    a = make_ticket(id="DAS-9001", zone="scripts/board_lint")
    b = make_ticket(id="DAS-9002", zone="scripts/board_lint")
    conflicts = zone_wave_conflicts([(fake, a), (fake, b)])
    assert len(conflicts) == 1
    assert "same-zone wave conflict" in conflicts[0]
    assert "scripts/board_lint" in conflicts[0]


def test_zone_wave_conflicts_allows_permitted_pair() -> None:
    fake = Path("board/tickets/DAS-FAKE.md")
    a = make_ticket(id="DAS-9001", zone="scripts/log", merge_policy="append-only")
    b = make_ticket(id="DAS-9002", zone="scripts/log", merge_policy="append-only")
    assert zone_wave_conflicts([(fake, a), (fake, b)]) == []


def test_zone_wave_conflicts_ignores_singletons_and_zoneless() -> None:
    fake = Path("board/tickets/DAS-FAKE.md")
    a = make_ticket(id="DAS-9001", zone="scripts/a")
    b = make_ticket(id="DAS-9002", zone="scripts/b")
    c = make_ticket(id="DAS-9003")  # no zone
    assert zone_wave_conflicts([(fake, a), (fake, b), (fake, c)]) == []


# ---------------------------------------------------------------------------
# Integration — file-system round-trip via load_tickets
# ---------------------------------------------------------------------------


def test_load_tickets_roundtrip(tmp_path: Path) -> None:
    """Write a ticket to disk, load it, lint it — no violations expected."""
    fm = make_ticket(id="DAS-9001")
    make_ticket_file(tmp_path, fm)
    loaded = load_tickets(tmp_path)
    assert len(loaded) == 1
    errors = lint_tickets(loaded, _KNOWN_ROLES)
    assert not errors, errors


def test_load_tickets_bad_status_file(tmp_path: Path) -> None:
    """Ticket file with bad status must surface a violation after load."""
    fm = make_ticket(id="DAS-9002", status="wontfix")
    make_ticket_file(tmp_path, fm)
    loaded = load_tickets(tmp_path)
    errors = lint_tickets(loaded, _KNOWN_ROLES)
    assert any("invalid status" in e for e in errors), errors


def test_load_tickets_self_review_file(tmp_path: Path) -> None:
    """in_review ticket with self-review must be caught via load_tickets."""
    fm = make_ticket(
        id="DAS-9003", status="in_review", assignee="qa-eng", author="qa-eng"
    )
    make_ticket_file(tmp_path, fm)
    loaded = load_tickets(tmp_path)
    errors = lint_tickets(loaded, _KNOWN_ROLES)
    assert any("self-review" in e for e in errors), errors


# ---------------------------------------------------------------------------
# R14 — ticket ids are unique
# ---------------------------------------------------------------------------


def _write_ticket_as(tmp_path: Path, fm: dict[str, str], filename: str) -> Path:
    """Like make_ticket_file but with the filename chosen by the caller — needed
    here because a duplicate id is by definition two files the id cannot name."""
    path = tmp_path / filename
    lines = ["---"] + [f"{k}: {v}" for k, v in fm.items()]
    lines += ["---", "", "## Description", "Fixture.", "", "## Log"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_duplicate_ticket_id_fires(tmp_path: Path) -> None:
    """Two files claiming one id is the merge-collision case: each branch
    allocated the next free number off the same base, and git saw no conflict
    because the filenames differ."""
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), "DAS-9100-first.md")
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), "DAS-9100-second.md")
    errors = lint_tickets(load_tickets(tmp_path), _KNOWN_ROLES)
    dupes = [e for e in errors if "duplicate ticket id" in e]
    assert len(dupes) == 1, errors
    # Both offenders must be named — reporting only one leaves the operator
    # hunting for the other half of a collision they cannot see from the id.
    assert "DAS-9100-first.md" in dupes[0] and "DAS-9100-second.md" in dupes[0]


def test_distinct_ticket_ids_do_not_fire(tmp_path: Path) -> None:
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), "DAS-9100-a.md")
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9101"), "DAS-9101-b.md")
    errors = lint_tickets(load_tickets(tmp_path), _KNOWN_ROLES)
    assert not [e for e in errors if "duplicate ticket id" in e], errors


def test_duplicate_id_is_fatal_not_a_warning(tmp_path: Path) -> None:
    """R14 must land in the error list (non-zero exit), not the WARN channel —
    a collision silently collapses `known_ids`, so R7 parent references resolve
    to "exists" while pointing at an ambiguity."""
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), "DAS-9100-first.md")
    _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), "DAS-9100-second.md")
    errors = lint_tickets(load_tickets(tmp_path), _KNOWN_ROLES)
    assert errors, "duplicate id produced no violation"


def test_three_way_duplicate_reports_once_naming_all_three(tmp_path: Path) -> None:
    for suffix in ("a", "b", "c"):
        _write_ticket_as(tmp_path, make_ticket(id="DAS-9100"), f"DAS-9100-{suffix}.md")
    errors = lint_tickets(load_tickets(tmp_path), _KNOWN_ROLES)
    dupes = [e for e in errors if "duplicate ticket id" in e]
    assert len(dupes) == 1, dupes
    assert "3 files" in dupes[0]
    assert all(f"DAS-9100-{s}.md" in dupes[0] for s in ("a", "b", "c"))


# ---------------------------------------------------------------------------
# load_known_roles — verify ROUTING.md parsing
# ---------------------------------------------------------------------------


def test_load_known_roles_parses_routing(tmp_path: Path) -> None:
    """load_known_roles should return a set of role keys from a ROUTING.md stub."""
    routing_md = textwrap.dedent(
        """\
        # Role routing

        | Role key | Display name | Dept | Reports to |
        |---|---|---|---|
        | `qa-eng` | QA Engineer | engineering | QA Lead |
        | `cto` | CTO | engineering | CEO |
        | `backend-eng-1` | Backend Engineer 1 | engineering | Backend EM |
        """
    )
    routing_path = tmp_path / "ROUTING.md"
    routing_path.write_text(routing_md, encoding="utf-8")

    roles = load_known_roles(routing_path)
    assert "qa-eng" in roles
    assert "cto" in roles
    assert "backend-eng-1" in roles
    assert "nonexistent-role" not in roles


# ---------------------------------------------------------------------------
# R11 — produces / consumes artifact-schema contracts (DAS-1467)
# ---------------------------------------------------------------------------

_SCHEMA_YAML = """\
name: {name}
description: A test artifact.
fields:
  - name: x
    type: string
    required: true
"""


def _make_schemas_dir(tmp_path: Path, *names: str) -> Path:
    d = tmp_path / "schemas"
    d.mkdir()
    for n in names:
        (d / f"{n}.yaml").write_text(_SCHEMA_YAML.format(name=n), encoding="utf-8")
    return d


def _r11_errors(fm: dict[str, str], schemas_dir: Path) -> list[str]:
    fake = Path("board/tickets/DAS-FAKE.md")
    return lint_tickets([(fake, fm)], _KNOWN_ROLES, schemas_dir=schemas_dir)


def test_produces_valid_schema_ok(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger")
    fm = make_ticket(produces="task-ledger")
    assert _r11_errors(fm, d) == []


def test_consumes_valid_schema_ok(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger")
    fm = make_ticket(consumes="task-ledger")
    assert _r11_errors(fm, d) == []


def test_produces_bracketed_list_ok(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "a", "b")
    fm = make_ticket(produces="[a, b]")
    assert _r11_errors(fm, d) == []


def test_produces_unknown_schema_fires(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "known")
    fm = make_ticket(produces="ghost")
    errors = _r11_errors(fm, d)
    assert any("unknown artifact schema 'ghost'" in e for e in errors)


def test_consumes_unknown_in_list_fires(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "a")
    fm = make_ticket(consumes="[a, missing]")
    errors = _r11_errors(fm, d)
    assert any("unknown artifact schema 'missing'" in e for e in errors)
    assert not any("'a'" in e for e in errors)  # the valid one is fine


def test_produces_malformed_schema_fires(tmp_path: Path) -> None:
    d = tmp_path / "schemas"
    d.mkdir()
    # name present but no description / fields -> malformed
    (d / "bad.yaml").write_text("name: bad\n", encoding="utf-8")
    fm = make_ticket(produces="bad")
    errors = _r11_errors(fm, d)
    assert any("malformed" in e for e in errors)


def test_produces_empty_value_fires(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "a")
    fm = make_ticket(produces="")
    errors = _r11_errors(fm, d)
    assert any("present but names no artifact schema" in e for e in errors)


def test_no_produces_consumes_is_additive_noop(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "a")
    fm = make_ticket()  # no produces/consumes at all
    assert _r11_errors(fm, d) == []


def test_produces_ok_even_if_dir_missing_and_field_absent(tmp_path: Path) -> None:
    # A ticket without the fields lints clean even when the schemas dir is absent.
    missing = tmp_path / "nope"
    fm = make_ticket()
    assert _r11_errors(fm, missing) == []


# ---------------------------------------------------------------------------
# R13 — FINALE program tickets require typed contracts (fail-closed for
# `program: finale`; every other ticket is unaffected). DAS FINALE / R3.
# ---------------------------------------------------------------------------


def test_finale_missing_both_contracts_fires(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger", "typed-contracts")
    fm = make_ticket(program="finale")  # FINALE marker, no produces/consumes
    errors = _r11_errors(fm, d)
    assert any("program: finale requires a non-empty 'produces:'" in e for e in errors)
    assert any("program: finale requires a non-empty 'consumes:'" in e for e in errors)


def test_finale_with_both_contracts_ok(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger", "typed-contracts")
    fm = make_ticket(program="finale", produces="task-ledger", consumes="typed-contracts")
    assert _r11_errors(fm, d) == []


def test_finale_missing_consumes_only_fires(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger")
    fm = make_ticket(program="finale", produces="task-ledger")  # consumes absent
    errors = _r11_errors(fm, d)
    assert any("program: finale requires a non-empty 'consumes:'" in e for e in errors)
    assert not any("'produces:'" in e for e in errors)  # produces is satisfied


def test_finale_marker_is_case_insensitive(tmp_path: Path) -> None:
    d = _make_schemas_dir(tmp_path, "task-ledger")
    fm = make_ticket(program="FINALE")  # upper-case marker still fires the gate
    errors = _r11_errors(fm, d)
    assert any("program: finale requires" in e for e in errors)


def test_non_finale_missing_contracts_is_noop(tmp_path: Path) -> None:
    # Regression guard: a non-FINALE ticket (or one with a different program
    # value) missing produces/consumes lints exactly as before — the current
    # green board must stay green.
    d = _make_schemas_dir(tmp_path, "task-ledger")
    assert _r11_errors(make_ticket(), d) == []
    assert _r11_errors(make_ticket(program="qaqnuz"), d) == []


def test_finale_marker_inline_comment_and_quote_still_fire(tmp_path: Path) -> None:
    # The confirmed bypass: a trailing inline YAML comment or a stray quote must NOT
    # let a FINALE ticket lint clean without contracts (the permissive frontmatter
    # parser keeps the comment in the raw value, so exact-equality silently missed it).
    d = _make_schemas_dir(tmp_path, "task-ledger")
    for marker in ("finale  # gated build", '"finale', "finale extra"):
        errors = _r11_errors(make_ticket(program=marker), d)
        assert any("program: finale requires" in e for e in errors), f"bypass via {marker!r}"


def test_distinct_program_token_is_noop(tmp_path: Path) -> None:
    # A genuinely different single-token program stays fail-open (only `finale` fires).
    d = _make_schemas_dir(tmp_path, "task-ledger")
    assert not any(
        "program: finale requires" in e for e in _r11_errors(make_ticket(program="finale-v2"), d)
    )


# ---------------------------------------------------------------------------
# W11 — a `status: <status>` line in the ticket BODY (DAS-1507); non-fatal warning
# ---------------------------------------------------------------------------


def test_body_status_line_warns(tmp_path: Path) -> None:
    from board_lint import warn_body_status_lines

    fm = make_ticket()
    p = make_ticket_file(tmp_path, fm)
    # a line in the BODY that mimics the frontmatter field with a real status value.
    p.write_text(p.read_text(encoding="utf-8") + "\nstatus: done\n", encoding="utf-8")
    warns = warn_body_status_lines([(p, fm)])
    assert len(warns) == 1 and "DAS-1507" in warns[0]


def test_body_prose_without_status_value_no_warn(tmp_path: Path) -> None:
    from board_lint import warn_body_status_lines

    fm = make_ticket()
    p = make_ticket_file(tmp_path, fm)
    # not a line-start status field, and not a valid status value -> no warn.
    p.write_text(
        p.read_text(encoding="utf-8") + "\nThe rollout status: some free prose here\n",
        encoding="utf-8",
    )
    assert warn_body_status_lines([(p, fm)]) == []


def test_body_status_warning_is_non_fatal(tmp_path: Path) -> None:
    # W11 must never change the exit code — it is informational only.
    import board_lint

    board = tmp_path / "tickets"
    board.mkdir()
    p = make_ticket_file(board, make_ticket())
    p.write_text(p.read_text(encoding="utf-8") + "\nstatus: done\n", encoding="utf-8")
    routing = tmp_path / "ROUTING.md"
    routing.write_text(
        "# Role routing\n\n| Role key | Display | Dept | Reports to |\n|---|---|---|---|\n"
        "| `qa-eng` | QA Engineer | engineering | QA Lead |\n"
        "| `ceo` | CEO | governance | Chairman |\n",
        encoding="utf-8",
    )
    rc = board_lint.main(["--board", str(board), "--routing", str(routing)])
    assert rc == 0  # the body-status WARNING must not fail the lint


# ---------------------------------------------------------------------------
# Tolerant reader — _schema_names_of
# ---------------------------------------------------------------------------


def test_schema_names_single() -> None:
    assert _schema_names_of({"produces": "task-ledger"}, "produces") == ["task-ledger"]


def test_schema_names_bracketed_list() -> None:
    assert _schema_names_of({"consumes": "[a, b, c]"}, "consumes") == ["a", "b", "c"]


def test_schema_names_strips_quotes_and_ws() -> None:
    assert _schema_names_of({"produces": '  "a" , b  '}, "produces") == ["a", "b"]


def test_schema_names_absent_is_empty() -> None:
    assert _schema_names_of({}, "produces") == []


def test_schema_names_empty_and_bracket_empty() -> None:
    assert _schema_names_of({"produces": ""}, "produces") == []
    assert _schema_names_of({"produces": "[]"}, "produces") == []


# ---------------------------------------------------------------------------
# R12 — stage-gate FAIL-CLOSED (audit remediation FIX-B)
# ---------------------------------------------------------------------------
# The R12 stage-gate check enforces GATE-5's no-deploy law and the AADL gate
# order. It used to be wrapped in `except Exception: pass`, so any import/config
# error in stage_gate silently disabled the org's most safety-critical rule
# while the linter still reported a green board. These tests pin the fail-closed
# contract: a broken stage_gate is surfaced as a violation, never swallowed.


def test_r12_broken_stage_gate_is_surfaced_not_bypassed(monkeypatch) -> None:
    """A stage_gate that raises must produce a lint violation (fail-closed)."""
    import stage_gate

    def _boom(*_args, **_kwargs):
        raise RuntimeError("stage_gate config exploded")

    monkeypatch.setattr(stage_gate, "stage_gate_violations", _boom)

    errors = run_lint([make_ticket()])

    # The failure is surfaced as an R12 violation instead of being swallowed.
    assert any("R12" in e and "stage-gate" in e for e in errors), errors
    # The underlying cause is preserved for debuggability.
    assert any("stage_gate config exploded" in e for e in errors), errors


def test_r12_healthy_stage_gate_stays_additive_noop(monkeypatch) -> None:
    """When stage_gate reports no violations, R12 adds nothing (additive)."""
    import stage_gate

    monkeypatch.setattr(stage_gate, "stage_gate_violations", lambda *_a, **_k: [])

    # A fully valid ticket must lint clean — R12 introduces no false positive.
    assert run_lint([make_ticket()]) == []
