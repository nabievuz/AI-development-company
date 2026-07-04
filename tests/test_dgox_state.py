"""Tests for scripts/dgox/state.py — DGO-X Phase-1 graph_state module.

Coverage matrix:
    - Field group membership and GROUP_WRITER mapping
    - Derived-reconstruction basics (GraphState defaults)
    - Invariant 1: cannot-skip-AADL-stage (pass + violation cases)
    - Invariant 2: role-cannot-self-route (pass + violation cases)
    - Invariant 3: severity-up-only (pass + violation + review_authorized bypass)
    - Invariant 4: flat-ArcRift-scope (pass + violation cases)
    - Wrong-group-writer rejection (StateInvariantError with rule=wrong_group_writer)
    - Enum coercion (plain strings accepted for enum fields)
    - apply_group unknown group raises ValueError (not StateInvariantError)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on the path so dgox.state can import _paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dgox.state import (  # noqa: E402
    AADL_ORDER,
    FIELD_GROUPS,
    GROUP_WRITER,
    AadlStage,
    GraphState,
    Severity,
    StateInvariantError,
    apply_group,
)  # fmt: skip

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fresh_state(ticket_id: str = "DAS-0001") -> GraphState:
    """Return a blank GraphState for the given ticket."""
    return GraphState(ticket_id=ticket_id)


# ---------------------------------------------------------------------------
# 1. Structural / metadata
# ---------------------------------------------------------------------------


class TestFieldGroups:
    def test_all_seven_groups_present(self) -> None:
        expected = {"identity", "lifecycle", "routing", "execution", "risk", "artifacts", "memory"}
        assert set(FIELD_GROUPS) == expected

    def test_identity_fields(self) -> None:
        assert set(FIELD_GROUPS["identity"]) == {"ticket_id", "goal", "parent", "project", "dept"}

    def test_lifecycle_fields(self) -> None:
        assert set(FIELD_GROUPS["lifecycle"]) == {"aadl_stage", "gate_status", "predecessor_gate"}

    def test_routing_fields(self) -> None:
        assert set(FIELD_GROUPS["routing"]) == {
            "assignee",
            "reviewer",
            "routing_reason",
            "confidence",
        }

    def test_execution_fields(self) -> None:
        assert set(FIELD_GROUPS["execution"]) == {
            "run_id",
            "workspace_id",
            "branch",
            "pr_url",
        }

    def test_risk_fields(self) -> None:
        assert set(FIELD_GROUPS["risk"]) == {"severity", "security_class", "approval_required"}

    def test_artifacts_fields(self) -> None:
        assert set(FIELD_GROUPS["artifacts"]) == {
            "files_changed",
            "docs_changed",
            "test_results",
            "trace_ids",
        }

    def test_memory_fields(self) -> None:
        assert set(FIELD_GROUPS["memory"]) == {"recall_id", "store_id", "memory_scope"}

    def test_group_writers_declared(self) -> None:
        assert set(GROUP_WRITER) == set(FIELD_GROUPS)

    def test_aadl_order_complete(self) -> None:
        assert len(AADL_ORDER) == 6
        assert AADL_ORDER[0] == AadlStage.planning
        assert AADL_ORDER[-1] == AadlStage.maintenance


# ---------------------------------------------------------------------------
# 2. Derived-reconstruction basics
# ---------------------------------------------------------------------------


class TestGraphStateDefaults:
    def test_blank_state_has_ticket_id(self) -> None:
        state = fresh_state("DAS-9999")
        assert state.ticket_id == "DAS-9999"

    def test_all_optional_fields_none_or_empty(self) -> None:
        state = fresh_state()
        assert state.aadl_stage is None
        assert state.severity is None
        assert state.memory_scope is None
        assert state.files_changed == []
        assert state.trace_ids == []
        assert state.test_results == {}

    def test_apply_identity_group(self) -> None:
        state = fresh_state("DAS-0010")
        apply_group(state, "identity", {"goal": "ship-v1", "dept": "engineering"})
        assert state.goal == "ship-v1"
        assert state.dept == "engineering"
        # ticket_id unchanged
        assert state.ticket_id == "DAS-0010"

    def test_apply_execution_group(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "execution",
            {
                "run_id": "run-abc123",
                "branch": "feat/dgox-p1-state",
                "pr_url": "https://github.com/example/repo/pull/42",
            },
        )
        assert state.run_id == "run-abc123"
        assert state.branch == "feat/dgox-p1-state"

    def test_apply_artifacts_group(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "artifacts",
            {
                "files_changed": ["scripts/dgox/state.py"],
                "docs_changed": ["docs/adr/0011.md"],
                "trace_ids": ["evt-001", "evt-002"],
            },
        )
        assert state.files_changed == ["scripts/dgox/state.py"]
        assert state.trace_ids == ["evt-001", "evt-002"]


# ---------------------------------------------------------------------------
# 3. Invariant 1 — cannot skip AADL stage
# ---------------------------------------------------------------------------


class TestAadlStageInvariant:
    def test_first_write_any_stage_accepted(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        assert state.aadl_stage == AadlStage.planning

    def test_advance_one_step_with_closed_gate(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "design", "predecessor_gate": "closed"},
        )
        assert state.aadl_stage == AadlStage.design

    def test_advance_full_sequence(self) -> None:
        state = fresh_state()
        stages = [s.value for s in AADL_ORDER]
        apply_group(
            state, "lifecycle", {"aadl_stage": stages[0], "predecessor_gate": "closed"}
        )
        for stage in stages[1:]:
            apply_group(
                state,
                "lifecycle",
                {"aadl_stage": stage, "predecessor_gate": "closed"},
            )
        assert state.aadl_stage == AadlStage.maintenance

    def test_noop_same_stage_always_allowed(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "development", "predecessor_gate": "closed"},
        )
        # Rewriting the same stage is always OK (no gate check needed).
        apply_group(state, "lifecycle", {"aadl_stage": "development"})
        assert state.aadl_stage == AadlStage.development

    def test_skip_stage_raises(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(
                state,
                "lifecycle",
                {"aadl_stage": "development", "predecessor_gate": "closed"},
            )
        assert exc_info.value.violation["rule"] == "cannot_skip_aadl_stage"
        assert exc_info.value.violation["field"] == "aadl_stage"
        assert exc_info.value.violation["proposed"] == "development"

    def test_advance_with_open_gate_raises(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(
                state,
                "lifecycle",
                {"aadl_stage": "design", "predecessor_gate": "open"},
            )
        violation = exc_info.value.violation
        assert violation["rule"] == "cannot_skip_aadl_stage"
        assert "predecessor" in violation["reason"].lower()

    def test_advance_without_gate_field_when_state_gate_open_raises(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "open"},
        )
        with pytest.raises(StateInvariantError):
            # No predecessor_gate in update dict; state has it as "open"
            apply_group(state, "lifecycle", {"aadl_stage": "design"})

    def test_unknown_stage_raises(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(
                state,
                "lifecycle",
                {"aadl_stage": "unknown_stage", "predecessor_gate": "closed"},
            )
        assert exc_info.value.violation["rule"] == "cannot_skip_aadl_stage"

    def test_enum_coercion_string_input(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "lifecycle",
            {"aadl_stage": "planning", "predecessor_gate": "closed"},
        )
        assert isinstance(state.aadl_stage, AadlStage)
        assert state.aadl_stage == AadlStage.planning


# ---------------------------------------------------------------------------
# 4. Invariant 2 — role cannot self-route
# ---------------------------------------------------------------------------


class TestSelfRouteInvariant:
    def test_reviewer_different_from_author_accepted(self) -> None:
        state = fresh_state()
        state.set_author("backend-eng-1")
        apply_group(
            state,
            "routing",
            {"assignee": "backend-eng-1", "reviewer": "backend-em"},
        )
        assert state.reviewer == "backend-em"

    def test_reviewer_equals_author_raises(self) -> None:
        state = fresh_state()
        state.set_author("backend-eng-1")
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(
                state,
                "routing",
                {"reviewer": "backend-eng-1"},
            )
        violation = exc_info.value.violation
        assert violation["rule"] == "role_cannot_self_route"
        assert violation["field"] == "reviewer"
        assert "author" in violation["reason"]

    def test_reviewer_equals_assignee_raises(self) -> None:
        state = fresh_state()
        state.set_author("ceo")
        apply_group(state, "routing", {"assignee": "backend-eng-2"})
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "routing", {"reviewer": "backend-eng-2"})
        violation = exc_info.value.violation
        assert violation["rule"] == "role_cannot_self_route"
        assert "assignee" in violation["reason"]

    def test_reviewer_none_always_accepted(self) -> None:
        state = fresh_state()
        state.set_author("backend-eng-1")
        apply_group(state, "routing", {"reviewer": None})
        assert state.reviewer is None

    def test_no_author_set_reviewer_equals_assignee_raises(self) -> None:
        state = fresh_state()
        apply_group(state, "routing", {"assignee": "frontend-eng-1"})
        with pytest.raises(StateInvariantError):
            apply_group(state, "routing", {"reviewer": "frontend-eng-1"})

    def test_no_author_no_assignee_any_reviewer_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "routing", {"reviewer": "backend-em"})
        assert state.reviewer == "backend-em"

    def test_routing_reason_and_confidence_accepted(self) -> None:
        state = fresh_state()
        state.set_author("ceo")
        apply_group(
            state,
            "routing",
            {
                "assignee": "backend-eng-1",
                "reviewer": "backend-em",
                "routing_reason": "Stage 3 backend implementation",
                "confidence": 0.91,
            },
        )
        assert state.confidence == 0.91
        assert state.routing_reason == "Stage 3 backend implementation"


# ---------------------------------------------------------------------------
# 5. Invariant 3 — severity up-only
# ---------------------------------------------------------------------------


class TestSeverityUpOnlyInvariant:
    def test_first_write_any_severity_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "medium"})
        assert state.severity == Severity.medium

    def test_increase_severity_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "low"})
        apply_group(state, "risk", {"severity": "medium"})
        apply_group(state, "risk", {"severity": "high"})
        apply_group(state, "risk", {"severity": "critical"})
        assert state.severity == Severity.critical

    def test_same_severity_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "high"})
        apply_group(state, "risk", {"severity": "high"})
        assert state.severity == Severity.high

    def test_lower_severity_raises(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "high"})
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "risk", {"severity": "low"})
        violation = exc_info.value.violation
        assert violation["rule"] == "severity_up_only"
        assert violation["current"] == "high"
        assert violation["proposed"] == "low"

    def test_lower_severity_with_review_authorized(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "critical"})
        # An explicit security/gate review allows downgrading.
        apply_group(state, "risk", {"severity": "low"}, review_authorized=True)
        assert state.severity == Severity.low

    def test_unknown_severity_raises(self) -> None:
        state = fresh_state()
        apply_group(state, "risk", {"severity": "low"})
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "risk", {"severity": "extreme"})
        assert exc_info.value.violation["rule"] == "severity_up_only"

    def test_security_class_and_approval_accepted(self) -> None:
        state = fresh_state()
        apply_group(
            state, "risk", {"security_class": "internal", "approval_required": True}
        )
        assert state.security_class == "internal"
        assert state.approval_required is True


# ---------------------------------------------------------------------------
# 6. Invariant 4 — flat ArcRift memory scope
# ---------------------------------------------------------------------------


class TestFlatArcRiftScope:
    def test_daslab_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "memory", {"memory_scope": "daslab"})
        assert state.memory_scope == "daslab"

    def test_daslab_project_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "memory", {"memory_scope": "daslab-example"})
        assert state.memory_scope == "daslab-example"

    def test_daslab_project_with_underscore_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "memory", {"memory_scope": "daslab-my_project"})
        assert state.memory_scope == "daslab-my_project"

    def test_none_scope_accepted(self) -> None:
        state = fresh_state()
        apply_group(state, "memory", {"memory_scope": None})
        assert state.memory_scope is None

    def test_scope_with_slash_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "memory", {"memory_scope": "daslab/example"})
        violation = exc_info.value.violation
        assert violation["rule"] == "flat_arcrift_scope"
        assert "/" in violation["proposed"]
        assert "slash" in violation["reason"].lower()

    def test_nested_slash_scope_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "memory", {"memory_scope": "daslab-project/sub"})
        assert exc_info.value.violation["rule"] == "flat_arcrift_scope"

    def test_wrong_prefix_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "memory", {"memory_scope": "myorg-project"})
        assert exc_info.value.violation["rule"] == "flat_arcrift_scope"

    def test_recall_and_store_ids_accepted(self) -> None:
        state = fresh_state()
        apply_group(
            state,
            "memory",
            {"recall_id": "mem-abc", "store_id": "mem-xyz", "memory_scope": "daslab"},
        )
        assert state.recall_id == "mem-abc"
        assert state.store_id == "mem-xyz"


# ---------------------------------------------------------------------------
# 7. Wrong-group-writer rejection
# ---------------------------------------------------------------------------


class TestWrongGroupWriter:
    def test_writing_routing_field_via_identity_group_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "identity", {"reviewer": "backend-em"})
        violation = exc_info.value.violation
        assert violation["rule"] == "wrong_group_writer"
        assert violation["field"] == "reviewer"

    def test_writing_lifecycle_field_via_risk_group_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "risk", {"aadl_stage": "planning"})
        assert exc_info.value.violation["rule"] == "wrong_group_writer"

    def test_unknown_group_raises_value_error(self) -> None:
        state = fresh_state()
        with pytest.raises(ValueError, match="Unknown field group"):
            apply_group(state, "nonexistent_group", {"ticket_id": "DAS-0001"})

    def test_nonexistent_field_in_correct_group_raises(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "identity", {"made_up_field": "value"})
        assert exc_info.value.violation["rule"] == "wrong_group_writer"


# ---------------------------------------------------------------------------
# 8. StateInvariantError carries machine-readable violation
# ---------------------------------------------------------------------------


class TestStateInvariantErrorStructure:
    def test_violation_has_required_keys(self) -> None:
        state = fresh_state()
        apply_group(
            state, "lifecycle", {"aadl_stage": "planning", "predecessor_gate": "closed"}
        )
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(
                state,
                "lifecycle",
                {"aadl_stage": "testing", "predecessor_gate": "closed"},
            )
        violation = exc_info.value.violation
        for key in ("rule", "field", "current", "proposed"):
            assert key in violation, f"Missing key {key!r} in violation dict"

    def test_violation_rule_is_string(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "memory", {"memory_scope": "invalid/scope"})
        assert isinstance(exc_info.value.violation["rule"], str)

    def test_str_representation_is_violation_dict(self) -> None:
        state = fresh_state()
        with pytest.raises(StateInvariantError) as exc_info:
            apply_group(state, "memory", {"memory_scope": "bad/scope"})
        err = exc_info.value
        assert "flat_arcrift_scope" in str(err)
