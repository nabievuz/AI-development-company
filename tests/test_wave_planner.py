from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wave_planner as wp

_ORG = wp.OrgModel(
    role_models={
        "backend-eng-1": "sonnet",
        "backend-eng-2": "sonnet",
        "cto": "opus",
        "security-lead": "opus",
    },
    gate_order=("GATE-1", "GATE-2", "GATE-3", "GATE-4", "GATE-5", "GATE-6"),
)


def _ticket(ticket_id: str, **overrides) -> wp.Ticket:
    fields = {
        "role": "backend-eng-1",
        "status": "todo",
        "zone": f"zone-{ticket_id}",
    }
    fields.update(overrides)
    return wp.Ticket(ticket_id=ticket_id, **fields)


def test_actionable_tickets_are_dispatched() -> None:
    plan = wp.plan_wave([_ticket("DAS-1")], _ORG, [])
    assert plan.ticket_ids == ("DAS-1",)
    assert plan.refused == ()


def test_non_actionable_status_is_refused() -> None:
    for status in ("in_review", "done", "blocked", ""):
        plan = wp.plan_wave([_ticket("DAS-1", status=status)], _ORG, [])
        assert plan.ticket_ids == ()
        refusal = plan.refusal_for("DAS-1")
        assert refusal is not None
        assert refusal.reason is wp.RefusalReason.NOT_ACTIONABLE


def test_backlog_is_actionable() -> None:
    plan = wp.plan_wave([_ticket("DAS-1", status="BACKLOG")], _ORG, [])
    assert plan.ticket_ids == ("DAS-1",)


def test_dependency_guard_refuses_a_ticket_with_an_open_dependency() -> None:
    tickets = [
        _ticket("DAS-1", status="in_progress", zone="a"),
        _ticket("DAS-2", depends_on=("DAS-1",), zone="b"),
    ]
    plan = wp.plan_wave(tickets, _ORG, [])
    assert "DAS-2" not in plan.ticket_ids
    refusal = plan.refusal_for("DAS-2")
    assert refusal is not None
    assert refusal.reason is wp.RefusalReason.UNMET_DEPENDENCY
    assert "DAS-1" in refusal.detail


def test_dependency_guard_allows_a_ticket_whose_dependency_is_done() -> None:
    tickets = [
        _ticket("DAS-1", status="done", zone="a"),
        _ticket("DAS-2", depends_on=("DAS-1",), zone="b"),
    ]
    plan = wp.plan_wave(tickets, _ORG, [])
    assert plan.ticket_ids == ("DAS-2",)


def test_dependency_guard_is_not_inverted() -> None:
    open_dep = _ticket("DAS-2", depends_on=("DAS-1",))
    closed_dep = _ticket("DAS-3", depends_on=("DAS-1",))

    assert wp.dependencies_satisfied(open_dep, {"DAS-1": "in_progress"}) is False
    assert wp.dependencies_satisfied(closed_dep, {"DAS-1": "done"}) is True
    assert wp.unmet_dependencies(open_dep, {"DAS-1": "todo"}) == ("DAS-1",)
    assert wp.unmet_dependencies(closed_dep, {"DAS-1": "merged"}) == ()


def test_an_unknown_dependency_counts_as_unmet() -> None:
    ticket = _ticket("DAS-2", depends_on=("DAS-404",))
    assert wp.unmet_dependencies(ticket, {}) == ("DAS-404",)
    plan = wp.plan_wave([ticket], _ORG, [])
    assert plan.ticket_ids == ()
    assert plan.refusal_for("DAS-2").reason is wp.RefusalReason.UNMET_DEPENDENCY


def test_every_unmet_dependency_is_named() -> None:
    tickets = [
        _ticket("DAS-1", status="done", zone="a"),
        _ticket("DAS-2", status="todo", zone="b"),
        _ticket("DAS-3", depends_on=("DAS-1", "DAS-2", "DAS-404"), zone="c"),
    ]
    plan = wp.plan_wave(tickets, _ORG, [])
    refusal = plan.refusal_for("DAS-3")
    assert refusal.reason is wp.RefusalReason.UNMET_DEPENDENCY
    assert "DAS-2" in refusal.detail and "DAS-404" in refusal.detail
    assert "DAS-1" not in refusal.detail


def test_open_predecessor_gate_blocks_dispatch() -> None:
    ticket = _ticket("DAS-1", gate="GATE-3")
    plan = wp.plan_wave([ticket], _ORG, [], closed_gates=["GATE-1"])
    assert plan.ticket_ids == ()
    refusal = plan.refusal_for("DAS-1")
    assert refusal.reason is wp.RefusalReason.OPEN_PREDECESSOR_GATE
    assert "GATE-2" in refusal.detail


def test_closed_predecessor_gates_release_the_ticket() -> None:
    ticket = _ticket("DAS-1", gate="GATE-3")
    plan = wp.plan_wave([ticket], _ORG, [], closed_gates=["GATE-1", "GATE-2"])
    assert plan.ticket_ids == ("DAS-1",)


def test_first_gate_has_no_predecessors() -> None:
    plan = wp.plan_wave([_ticket("DAS-1", gate="GATE-1")], _ORG, [])
    assert plan.ticket_ids == ("DAS-1",)


def test_two_tickets_never_share_a_zone_in_one_wave() -> None:
    tickets = [
        _ticket("DAS-1", zone="scripts", priority="p1"),
        _ticket("DAS-2", zone="scripts", priority="p2"),
        _ticket("DAS-3", zone="tools", priority="p2"),
    ]
    plan = wp.plan_wave(tickets, _ORG, [])
    assert plan.ticket_ids == ("DAS-1", "DAS-3")
    assert plan.refusal_for("DAS-2").reason is wp.RefusalReason.ZONE_CONFLICT
    assert len(plan.zones) == len(plan.dispatch)


def test_an_occupied_zone_is_not_re_entered() -> None:
    plan = wp.plan_wave([_ticket("DAS-1", zone="scripts")], _ORG, ["scripts"])
    assert plan.ticket_ids == ()
    assert plan.refusal_for("DAS-1").reason is wp.RefusalReason.ZONE_CONFLICT


def test_zone_falls_back_to_dept_then_ticket_id() -> None:
    by_dept = wp.Ticket("DAS-1", role="backend-eng-1", status="todo", dept="engineering")
    unzoned = wp.Ticket("DAS-2", role="backend-eng-1", status="todo")
    assert wp.effective_zone(by_dept) == "engineering"
    assert wp.effective_zone(unzoned) == "DAS-2"


def test_model_comes_from_the_org_not_the_ticket_frontmatter() -> None:
    ticket = _ticket("DAS-1", role="backend-eng-1", declared_model="opus")
    plan = wp.plan_wave([ticket], _ORG, [])
    assert plan.dispatch[0].model == "sonnet"


def test_a_role_without_a_model_allocation_is_refused() -> None:
    plan = wp.plan_wave([_ticket("DAS-1", role="ghost-role")], _ORG, [])
    assert plan.ticket_ids == ()
    assert plan.refusal_for("DAS-1").reason is wp.RefusalReason.NO_MODEL_FOR_ROLE


def test_model_for_raises_on_an_unknown_role() -> None:
    with pytest.raises(wp.UnknownRoleError):
        _ORG.model_for("ghost-role")


def test_plan_is_deterministic_regardless_of_board_order() -> None:
    tickets = [
        _ticket("DAS-3", priority="p2", zone="c"),
        _ticket("DAS-1", priority="p1", zone="a"),
        _ticket("DAS-2", priority="p1", zone="b"),
    ]
    first = wp.plan_wave(tickets, _ORG, [])
    second = wp.plan_wave(list(reversed(tickets)), _ORG, [])
    assert first == second
    assert first.ticket_ids == ("DAS-1", "DAS-2", "DAS-3")


def test_priority_orders_the_wave_before_ticket_id() -> None:
    tickets = [
        _ticket("DAS-1", priority="p3", zone="a"),
        _ticket("DAS-9", priority="p0", zone="b"),
    ]
    plan = wp.plan_wave(tickets, _ORG, [])
    assert plan.ticket_ids == ("DAS-9", "DAS-1")


def test_max_wave_size_caps_the_wave_and_names_the_reason() -> None:
    tickets = [_ticket(f"DAS-{i}", zone=f"z{i}") for i in range(1, 5)]
    plan = wp.plan_wave(tickets, _ORG, [], max_wave_size=2)
    assert len(plan.dispatch) == 2
    assert {r.reason for r in plan.refused} == {wp.RefusalReason.WAVE_FULL}


def test_duplicate_ticket_ids_are_rejected_loudly() -> None:
    with pytest.raises(wp.DuplicateTicketError):
        wp.plan_wave([_ticket("DAS-1", zone="a"), _ticket("DAS-1", zone="b")], _ORG, [])


def test_plan_wave_makes_no_wall_clock_or_random_call() -> None:
    source = (_SCRIPTS / "wave_planner.py").read_text(encoding="utf-8")
    for forbidden in ("import time", "import random", "datetime.now", "time.time"):
        assert forbidden not in source


def _write_ticket_file(board: Path, ticket_id: str, body: str) -> None:
    board.mkdir(parents=True, exist_ok=True)
    (board / f"{ticket_id}-work.md").write_text(body, encoding="utf-8")


def test_load_board_tickets_reads_frontmatter(tmp_path: Path) -> None:
    board = tmp_path / "tickets"
    _write_ticket_file(
        board,
        "DAS-1",
        textwrap.dedent(
            """\
            ---
            id: DAS-1
            status: todo
            assignee: backend-eng-1
            dept: engineering
            zone: scripts
            priority: p1
            depends_on: [DAS-0]
            gate: GATE-3
            model: opus
            ---

            body
            """
        ),
    )
    tickets = wp.load_board_tickets(board)
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.ticket_id == "DAS-1"
    assert ticket.role == "backend-eng-1"
    assert ticket.zone == "scripts"
    assert ticket.depends_on == ("DAS-0",)
    assert ticket.gate == "GATE-3"
    assert ticket.declared_model == "opus"


def test_load_org_model_reads_role_models(tmp_path: Path) -> None:
    org_file = tmp_path / "org.yaml"
    org_file.write_text(
        textwrap.dedent(
            """\
            gates: [GATE-1, GATE-2]
            roles:
              cto: {model_cap: opus}
              backend-eng-1: {model: sonnet}
            """
        ),
        encoding="utf-8",
    )
    org = wp.load_org_model(org_file)
    assert org.model_for("cto") == "opus"
    assert org.model_for("backend-eng-1") == "sonnet"
    assert org.gate_order == ("GATE-1", "GATE-2")


def test_load_org_model_refuses_an_empty_allocation(tmp_path: Path) -> None:
    org_file = tmp_path / "org.yaml"
    org_file.write_text("roles: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="allocates no models"):
        wp.load_org_model(org_file)


def test_load_org_model_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        wp.load_org_model(tmp_path / "absent.yaml")


ORG_PATH = Path(__file__).resolve().parent.parent / "config" / "org.yaml"


def _gated_board(tmp_path: Path, stage: str = "GATE-3") -> Path:
    board = tmp_path / "tickets"
    board.mkdir()
    (board / "DAS-7001-x-s3.md").write_text(
        "---\nid: DAS-7001\nstatus: todo\nassignee: backend-eng-1\ndept: engineering\n"
        f"zone: z1\nstage: {stage}\n---\n\nbody\n",
        encoding="utf-8",
    )
    return board


class TestTheGateComesFromTheStageField:
    def test_a_compiled_ticket_declares_its_gate_via_stage(self):
        assert wp.gate_of({"stage": "GATE-4"}) == "GATE-4"
        assert wp.gate_of({"stage": "Stage 4 — GATE-4"}) == "GATE-4"

    def test_a_legacy_gate_field_still_works(self):
        assert wp.gate_of({"gate": "GATE-2"}) == "GATE-2"

    def test_stage_wins_over_a_stale_gate_field(self):
        assert wp.gate_of({"stage": "GATE-5", "gate": "GATE-1"}) == "GATE-5"

    def test_no_gate_anywhere_is_empty_not_a_guess(self):
        assert wp.gate_of({}) == ""
        assert wp.gate_of({"stage": "Deployment"}) == ""

    def test_the_gate_order_is_known_even_when_the_org_file_omits_gates(self):
        org = wp.load_org_model(ORG_PATH)
        assert org.gate_order[:3] == ("GATE-1", "GATE-2", "GATE-3")
        assert org.predecessor_gates("GATE-3") == ("GATE-1", "GATE-2")


class TestOpenPredecessorGatesActuallyRefuses:
    def test_a_stage_3_ticket_is_refused_while_its_predecessors_are_open(self, tmp_path):
        board = _gated_board(tmp_path)
        org = wp.load_org_model(ORG_PATH)
        plan = wp.plan_wave(
            wp.load_board_tickets(board), org, goal="t", occupied_zones=(), closed_gates=()
        )
        assert not plan.dispatch
        assert [r.reason for r in plan.refused] == [wp.RefusalReason.OPEN_PREDECESSOR_GATE]
        assert "GATE-1, GATE-2" in plan.refused[0].detail

    def test_closing_every_predecessor_releases_the_ticket(self, tmp_path):
        board = _gated_board(tmp_path)
        org = wp.load_org_model(ORG_PATH)
        plan = wp.plan_wave(
            wp.load_board_tickets(board), org, goal="t",
            occupied_zones=(), closed_gates=("GATE-1", "GATE-2"),
        )
        assert [p.ticket_id for p in plan.dispatch] == ["DAS-7001"]

    def test_one_gate_still_open_still_refuses_and_names_only_that_gate(self, tmp_path):
        board = _gated_board(tmp_path)
        org = wp.load_org_model(ORG_PATH)
        plan = wp.plan_wave(
            wp.load_board_tickets(board), org, goal="t",
            occupied_zones=(), closed_gates=("GATE-1",),
        )
        assert not plan.dispatch
        assert plan.refused[0].detail.endswith("GATE-2")


def _t(tid, status="in_progress", parent="", zone="z", stage=""):
    return wp.Ticket(
        ticket_id=tid, role="backend-eng-1", status=status, zone=zone,
        dept="engineering", parent=parent, gate=stage,
    )


class TestWorkReturnedByReviewCanBePickedUpAgain:
    def test_in_progress_is_actionable(self):
        assert wp.is_actionable_status("in_progress") is True
        assert wp.is_actionable_status("todo") is True
        assert wp.is_actionable_status("blocked") is False
        assert wp.is_actionable_status("in_review") is False

    def test_a_reviewed_ticket_returned_to_its_author_is_dispatchable(self):
        org = wp.load_org_model(ORG_PATH)
        plan = wp.plan_wave([_t("DAS-2", parent="DAS-1")], org, goal="g", occupied_zones=())
        assert [p.ticket_id for p in plan.dispatch] == ["DAS-2"]


class TestContainersAreNotWork:
    def test_a_ticket_other_tickets_call_parent_is_refused(self):
        org = wp.load_org_model(ORG_PATH)
        tickets = [_t("DAS-1", zone="a"), _t("DAS-2", parent="DAS-1", zone="b")]
        plan = wp.plan_wave(tickets, org, goal="g", occupied_zones=())

        assert [p.ticket_id for p in plan.dispatch] == ["DAS-2"]
        refusal = plan.refusal_for("DAS-1")
        assert refusal.reason is wp.RefusalReason.NOT_ACTIONABLE
        assert "container ticket" in refusal.detail

    def test_a_leaf_that_merely_has_a_parent_is_still_work(self):
        assert wp.parent_ticket_ids([_t("DAS-2", parent="DAS-1")]) == frozenset()

    def test_a_parent_pointing_off_board_makes_nothing_a_container(self):
        tickets = [_t("DAS-2", parent="DAS-999"), _t("DAS-3", parent="DAS-999")]
        assert wp.parent_ticket_ids(tickets) == frozenset()

    def test_every_epic_on_a_compiled_board_is_recognised(self):
        tickets = [_t("DAS-1"), *[_t(f"DAS-{n}", parent="DAS-1") for n in range(2, 8)]]
        assert wp.parent_ticket_ids(tickets) == frozenset({"DAS-1"})
