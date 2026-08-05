from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gen_agent_templates as gat
import gen_subagents as gs
import org_model

HAIKU_ROLES = {"seo-specialist", "support-lead", "tech-writer"}

REQUIRED_HEADINGS = [
    "## Identity",
    "## Goal",
    "## Behavioral priors",
    "## Toolkit allowlist",
    "## Model + effort",
    "## Produces / consumes defaults",
    "## Allowed communication routes",
    "## Eval baseline",
    "## Learned",
]

_ROUTE_RE = re.compile(r"^- (?:delegation|escalation) → `([a-z0-9-]+)`", re.MULTILINE)


def _org():
    return org_model.load_org()


def _templates() -> dict[str, str]:
    org = _org()
    routes = gs.load_outbound_routes()
    return {
        role.key: gat.build_template(role, org.title_of(role.reports_to), routes)
        for role in org.roles
    }


def _template_alloc() -> dict[str, tuple[str, str | None]]:
    out: dict[str, tuple[str, str | None]] = {}
    for key, text in _templates().items():
        head = text.split("\n---", 1)[0]
        model = re.search(r"^model:\s*(opus|sonnet|haiku)\s*$", head, re.M)
        effort = re.search(r"^effort:\s*(max|xhigh|high|medium|low)\s*$", head, re.M)
        assert model is not None, key
        out[key] = (model.group(1), effort.group(1) if effort else None)
    return out


def _section(text: str, heading: str) -> str:
    m = re.search(
        rf"^##\s+{re.escape(heading)}[^\n]*\n(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else ""


def test_one_template_per_role_all_32() -> None:
    models, _ = gs.load_alloc()
    assert len(models) == 32
    assert set(_templates()) == set(models), (
        "template set must exactly match the 32 org-roster roles"
    )


def test_every_template_has_the_closed_craft_field_set() -> None:
    for key, text in _templates().items():
        for heading in REQUIRED_HEADINGS:
            assert heading in text, f"{key} missing '{heading}'"


def test_template_model_and_effort_are_verbatim_from_policy() -> None:
    models, efforts = gs.load_alloc()
    tmpl = _template_alloc()
    assert set(tmpl) == set(models)
    for key in models:
        assert tmpl[key] == (models[key], efforts[key]), key


def test_template_model_tier_counts() -> None:
    tmpl = _template_alloc()
    counts = Counter(model for model, _ in tmpl.values())
    assert counts == {"opus": 10, "sonnet": 19, "haiku": 3}


def test_no_fable_or_tier_f_in_templates() -> None:
    tmpl = _template_alloc()
    assert {model for model, _ in tmpl.values()} == {"opus", "sonnet", "haiku"}


def test_haiku_templates_omit_effort_line() -> None:
    templates = _templates()
    for role in HAIKU_ROLES:
        head = templates[role].split("\n---", 1)[0]
        assert "effort:" not in head, f"{role} template must omit effort frontmatter"
    tmpl = _template_alloc()
    for role in HAIKU_ROLES:
        assert tmpl[role][1] is None, role


def test_non_haiku_templates_carry_effort_line() -> None:
    tmpl = _template_alloc()
    for key, (model, effort) in tmpl.items():
        if model != "haiku":
            assert effort is not None, f"{key} ({model}) must carry an effort value"


def test_template_routes_match_communication_flows() -> None:
    routes = gs.load_outbound_routes()
    assert routes is not None
    for key, text in _templates().items():
        section = _section(text, "Allowed communication routes")
        in_template = set(_ROUTE_RE.findall(section))
        declared = {receiver for _, receiver in routes.get(key, [])}
        assert in_template == declared, f"{key}: {in_template} != {declared}"


def test_learned_section_is_empty_on_seed() -> None:
    for key, text in _templates().items():
        learned = _section(text, "Learned")
        for raw in learned.splitlines():
            line = raw.strip()
            if not line:
                continue
            assert not line.startswith("- "), f"{key} ## Learned not empty: {line}"


def test_every_shim_references_its_guild_template() -> None:
    org = _org()
    routes = gs.load_outbound_routes()
    for role in org.roles:
        shim = gs.build_shim(role, org, routes, template_present=True)
        assert f"governance/agent-templates/{role.key}.md" in shim, role.key


def test_shim_model_matches_template_model() -> None:
    org = _org()
    routes = gs.load_outbound_routes()
    tmpl = _template_alloc()
    for role in org.roles:
        model, _ = tmpl[role.key]
        fm = gs.build_shim(role, org, routes, template_present=True).split("\n---", 1)[0]
        assert re.search(rf"^model:\s*{model}\s*$", fm, re.M), role.key


def test_build_template_is_idempotent() -> None:
    org = _org()
    routes = gs.load_outbound_routes()
    role = org.role("backend-eng-1")
    a = gat.build_template(role, org.title_of(role.reports_to), routes)
    b = gat.build_template(role, org.title_of(role.reports_to), routes)
    assert a == b


def test_build_template_haiku_omits_effort_frontmatter() -> None:
    out = gat.build_template_for("tech-writer")
    head = out.split("\n---", 1)[0]
    assert "effort:" not in head
    assert "haiku does not support" in out


def test_build_template_names_the_reviewer_from_the_routing_table() -> None:
    org = _org()
    out = gat.build_template_for("sre-eng")
    assert org.routing_for("sre-eng").reviewer == "sre-lead"
    assert "SRE / DevOps Lead" in out


def test_load_template_alloc_absent_dir_returns_empty(tmp_path: Path) -> None:
    assert gs.load_template_alloc(tmp_path / "nope") == {}


def test_load_template_alloc_parses_effort_and_none(tmp_path: Path) -> None:
    d = tmp_path / "agent-templates"
    d.mkdir()
    (d / "cto.md").write_text("---\nrole: cto\nmodel: opus\neffort: high\n---\nbody\n")
    (d / "tech-writer.md").write_text("---\nrole: tech-writer\nmodel: haiku\n---\nbody\n")
    alloc = gs.load_template_alloc(d)
    assert alloc == {"cto": ("opus", "high"), "tech-writer": ("haiku", None)}
