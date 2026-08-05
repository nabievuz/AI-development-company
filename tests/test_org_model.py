from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

yaml = pytest.importorskip("yaml")

import board_lint
import check_agents_sync
import check_overlay_sections
import check_precedence
import gen_subagents as gs
import org_model

GUARDRAIL_DIR = REPO_ROOT / "governance" / "guardrails"
NON_ROLE_GUARDRAIL_MODULES = {"__init__", "runner"}

OPUS_HIGH = {
    "cto", "security-lead", "ceo", "chairman", "cpo", "senior-pm",
    "backend-em", "frontend-em", "qa-lead", "sre-lead",
}
SONNET_MEDIUM = {
    "backend-eng-1", "backend-eng-2", "frontend-eng-1", "frontend-eng-2",
    "qa-eng", "security-eng", "sre-eng", "design-lead", "product-designer",
    "ux-researcher", "product-analyst", "legal-analyst", "finance-analyst",
}
SONNET_LOW = {"content-lead", "growth-marketer", "cdo", "cmo", "coo", "board-member"}
HAIKU_NONE = {"seo-specialist", "support-lead", "tech-writer"}

EXPECTED_DEPTS = {
    "governance", "engineering", "product", "design", "marketing", "operations",
}


def _raw() -> dict:
    return yaml.safe_load(org_model.ORG_CONFIG_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, doc: dict, name: str = "org.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _role_entry(doc: dict, key: str) -> dict:
    for entry in doc["roles"]:
        if entry["key"] == key:
            return entry
    raise KeyError(key)


def test_org_config_is_the_committed_ssot() -> None:
    assert org_model.ORG_CONFIG_PATH == REPO_ROOT / "config" / "org.yaml"
    assert org_model.ORG_CONFIG_PATH.is_file()


def test_roster_is_exactly_the_32_roles() -> None:
    org = org_model.load_org()
    assert len(org.roles) == 32
    assert org.role_keys() == OPUS_HIGH | SONNET_MEDIUM | SONNET_LOW | HAIKU_NONE


def test_every_role_key_has_a_bespoke_guardrail_module() -> None:
    guardrail_keys = {
        p.stem for p in GUARDRAIL_DIR.glob("*.py")
    } - NON_ROLE_GUARDRAIL_MODULES
    missing = org_model.known_role_keys() - guardrail_keys
    assert not missing, f"roles with no governance/guardrails/<role>.py: {sorted(missing)}"
    assert len(org_model.known_role_keys() & guardrail_keys) == 32


def test_departments_are_the_six_named_departments() -> None:
    org = org_model.load_org()
    assert {d.key for d in org.departments} == EXPECTED_DEPTS
    for department in org.departments:
        assert org.role(department.manager_role).dept == department.key


def test_every_role_belongs_to_a_declared_department() -> None:
    org = org_model.load_org()
    for role in org.roles:
        assert org.dept_of(role.key).key == role.dept


def test_model_split_is_ten_opus_nineteen_sonnet_three_haiku() -> None:
    org = org_model.load_org()
    assert Counter(role.model for role in org.roles) == {
        org_model.Model.OPUS: 10,
        org_model.Model.SONNET: 19,
        org_model.Model.HAIKU: 3,
    }


@pytest.mark.parametrize(
    "keys,model,effort",
    [
        (OPUS_HIGH, org_model.Model.OPUS, org_model.Effort.HIGH),
        (SONNET_MEDIUM, org_model.Model.SONNET, org_model.Effort.MEDIUM),
        (SONNET_LOW, org_model.Model.SONNET, org_model.Effort.LOW),
        (HAIKU_NONE, org_model.Model.HAIKU, None),
    ],
)
def test_effort_bands(keys, model, effort) -> None:
    for key in keys:
        role = org_model.role(key)
        assert role.model is model, key
        assert role.effort is effort, key


def test_no_role_runs_at_max_effort() -> None:
    assert org_model.Effort.MAX not in {role.effort for role in org_model.roles()}


def test_haiku_roles_do_not_support_effort() -> None:
    for key in HAIKU_NONE:
        assert org_model.role(key).supports_effort is False


def test_routing_reviewer_is_a_known_role_and_never_self() -> None:
    org = org_model.load_org()
    for row in org.routing_table():
        assert row.reviewer != row.role
        if row.reviewer is not None:
            assert org.has_role(row.reviewer)
        else:
            assert row.reviewer_title == "the Board"


def test_routing_for_resolves_the_reviewer_display_title() -> None:
    row = org_model.routing_for("sre-eng")
    assert (row.reviewer, row.reviewer_title) == ("sre-lead", "SRE / DevOps Lead")
    assert org_model.routing_for("chairman").reviewer is None


def test_escalation_chain_terminates_at_the_board() -> None:
    org = org_model.load_org()
    for role in org.roles:
        chain = org.escalation_chain(role.key)
        assert len(chain) == len(set(chain))
        if chain:
            assert org.role(chain[-1]).reports_to is None
    assert org.escalation_chain("backend-eng-1") == ("backend-em", "cto", "ceo", "chairman")


def test_escalation_ladder_matches_the_org_schema() -> None:
    schema = yaml.safe_load((REPO_ROOT / "org" / "schema.daslab.yaml").read_text())
    assert list(org_model.load_org().escalation_ladder) == schema["routing"]["escalation"]


def test_precedence_is_ordered_and_only_the_top_two_levels_are_binding() -> None:
    levels = org_model.precedence()
    assert [level.level for level in levels] == list(range(1, len(levels) + 1))
    binding = [level.key for level in levels if level.authority is org_model.Authority.BINDING]
    assert binding == ["charter", "board_policy"]
    add_only = {level.key for level in levels if level.authority is org_model.Authority.ADD_ONLY}
    assert "role_charter" in add_only


def test_role_charter_level_points_at_the_org_config() -> None:
    role_charter = next(level for level in org_model.precedence() if level.key == "role_charter")
    assert "config/org.yaml" in role_charter.paths
    assert role_charter.authority is org_model.Authority.ADD_ONLY


def test_precedence_surface_is_non_empty_and_add_only() -> None:
    files = check_precedence.collect_surface(REPO_ROOT)
    assert files
    assert org_model.ORG_CONFIG_PATH in files
    assert check_precedence.find_violations(files) == []


def test_tool_allowlist_compiles_to_the_committed_artifact() -> None:
    committed = json.loads((REPO_ROOT / "board" / ".tool-allowlist.json").read_text())
    assert org_model.tool_allowlist() == committed
    assert gs.compile_tool_allowlist() == committed


def test_tool_grants_never_compile_to_a_wildcard_role() -> None:
    for entry, granted in org_model.tool_allowlist().items():
        assert "*" not in entry
        assert "*" not in granted


def test_wildcard_tool_grant_compiles_to_the_server_entry() -> None:
    grant = org_model.ToolGrant(server="mcp__x", tools=("*",), egress_profile="p")
    assert grant.allowlist_entries() == ("mcp__x",)


def test_every_role_charter_carries_all_four_contract_sections() -> None:
    for role in org_model.roles():
        titles = tuple(name for name, _ in role.charter.sections())
        assert titles == org_model.CHARTER_SECTION_TITLES
        for name, body in role.charter.sections():
            assert len(body.strip()) >= check_overlay_sections.MIN_CHARS, (role.key, name)


def test_overlay_section_gate_passes_strict_against_the_org_model() -> None:
    assert check_overlay_sections.main(["--strict"]) == 0


def test_overlay_section_gate_flags_a_thin_role_charter() -> None:
    org = org_model.load_org()
    thin = org_model.Role(
        key="thin-role", dept="engineering", title="Thin", model=org_model.Model.SONNET,
        effort=org_model.Effort.LOW, reports_to="cto", rationale="",
        charter=org_model.RoleCharter(mission="x", scope="y", definition_of_done="z",
                                      escalation="w"),
        tool_grants=(),
    )
    tampered = org_model.Org(
        version=org.version, departments=org.departments, roles=(thin,),
        escalation_ladder=org.escalation_ladder, precedence=org.precedence,
    )
    gaps = check_overlay_sections.scan_role_charters(tampered)
    assert len(gaps) == 4
    assert all("thin" in reason for _, reason in gaps)


def test_load_known_roles_without_a_path_returns_the_org_roster() -> None:
    assert board_lint.load_known_roles() == org_model.known_role_keys()


def test_load_known_roles_ignores_an_absent_legacy_routing_table() -> None:
    gone = REPO_ROOT / "board" / "ROUTING.md"
    assert not gone.exists()
    assert board_lint.load_known_roles(gone) == org_model.known_role_keys()


def test_load_known_roles_still_reads_a_present_legacy_routing_table(tmp_path: Path) -> None:
    routing = tmp_path / "ROUTING.md"
    routing.write_text(
        "| Role key | Display name | Dept | Reports to |\n|---|---|---|---|\n"
        "| `qa-eng` | QA Engineer | engineering | QA Lead |\n",
        encoding="utf-8",
    )
    assert board_lint.load_known_roles(routing) == frozenset({"qa-eng"})


def test_board_lint_cli_defaults_to_the_org_roster() -> None:
    assert board_lint.main(["--board", str(REPO_ROOT / "board" / "tickets")]) in (0, 1)


def test_board_lint_cli_rejects_an_explicit_missing_routing_table(tmp_path: Path) -> None:
    rc = board_lint.main([
        "--board", str(REPO_ROOT / "board" / "tickets"),
        "--routing", str(tmp_path / "nope.md"),
    ])
    assert rc == 2


def test_check_agents_sync_defaults_to_the_org_roster() -> None:
    assert set(check_agents_sync.load_org_routing()) == org_model.known_role_keys()
    assert check_agents_sync.load_org_models() == {
        role.key: role.model.value for role in org_model.roles()
    }


def test_gen_subagents_load_alloc_reads_the_org_model() -> None:
    models, efforts = gs.load_alloc()
    assert models == {role.key: role.model.value for role in org_model.roles()}
    assert efforts == {
        role.key: (role.effort.value if role.effort else None)
        for role in org_model.roles()
    }


def test_unknown_department_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "cto")["dept"] = "sales"
    with pytest.raises(org_model.OrgConfigError, match="unknown department"):
        org_model.load_org(_write(tmp_path, doc))


def test_unknown_reports_to_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "cto")["reports_to"] = "nobody"
    with pytest.raises(org_model.OrgConfigError, match="unknown role"):
        org_model.load_org(_write(tmp_path, doc))


def test_self_reporting_role_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "cto")["reports_to"] = "cto"
    with pytest.raises(org_model.OrgConfigError, match="cannot report to itself"):
        org_model.load_org(_write(tmp_path, doc))


def test_haiku_role_declaring_effort_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "tech-writer")["effort"] = "high"
    with pytest.raises(org_model.OrgConfigError, match="does not support effort"):
        org_model.load_org(_write(tmp_path, doc))


def test_unknown_model_tier_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "cto")["model"] = "fable"
    with pytest.raises(org_model.OrgConfigError, match="not a valid model tier"):
        org_model.load_org(_write(tmp_path, doc))


def test_duplicate_role_key_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    doc["roles"].append(dict(_role_entry(doc, "cto")))
    with pytest.raises(org_model.OrgConfigError, match="duplicate role key"):
        org_model.load_org(_write(tmp_path, doc))


def test_unmanaged_department_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    doc["departments"][0]["manager_role"] = "nobody"
    with pytest.raises(org_model.OrgConfigError, match="manager_role"):
        org_model.load_org(_write(tmp_path, doc))


def test_out_of_order_precedence_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    doc["precedence"][0]["level"] = 99
    with pytest.raises(org_model.OrgConfigError, match="ascending order"):
        org_model.load_org(_write(tmp_path, doc))


def test_unknown_precedence_authority_is_rejected(tmp_path: Path) -> None:
    doc = _raw()
    doc["precedence"][0]["authority"] = "advisory"
    with pytest.raises(org_model.OrgConfigError, match="authority must be one of"):
        org_model.load_org(_write(tmp_path, doc))


def test_missing_org_config_raises(tmp_path: Path) -> None:
    with pytest.raises(org_model.OrgConfigError, match="org config not found"):
        org_model.load_org(tmp_path / "absent.yaml")


def test_effort_defaults_by_model_when_omitted(tmp_path: Path) -> None:
    doc = _raw()
    _role_entry(doc, "cto")["effort"] = None
    _role_entry(doc, "backend-eng-1")["effort"] = None
    org = org_model.load_org(_write(tmp_path, doc))
    assert org.role("cto").effort is org_model.Effort.HIGH
    assert org.role("backend-eng-1").effort is org_model.Effort.MEDIUM


def test_unknown_role_lookup_raises_key_error() -> None:
    with pytest.raises(KeyError):
        org_model.role("no-such-role")
