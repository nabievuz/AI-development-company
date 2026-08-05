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

TEMPLATES = REPO_ROOT / "governance" / "agent-templates"
SHIMS = REPO_ROOT / ".claude" / "agents"

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


def _all_template_keys() -> set[str]:
    return {p.stem for p in TEMPLATES.glob("*.md")}


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
    assert _all_template_keys() == set(models), (
        "template set must exactly match the 32 allocation-table roles"
    )


def test_every_template_has_the_closed_craft_field_set() -> None:
    for path in TEMPLATES.glob("*.md"):
        text = path.read_text()
        for heading in REQUIRED_HEADINGS:
            assert heading in text, f"{path.name} missing '{heading}'"


def test_template_model_and_effort_are_verbatim_from_policy() -> None:
    models, efforts = gs.load_alloc()
    tmpl = gs.load_template_alloc()
    assert set(tmpl) == set(models)
    for key in models:
        assert tmpl[key] == (models[key], efforts[key]), key


def test_template_model_tier_counts() -> None:
    tmpl = gs.load_template_alloc()
    counts = Counter(model for model, _ in tmpl.values())
    assert counts == {"opus": 10, "sonnet": 19, "haiku": 3}


def test_no_fable_or_tier_f_in_templates() -> None:
    tmpl = gs.load_template_alloc()
    assert {model for model, _ in tmpl.values()} == {"opus", "sonnet", "haiku"}


def test_haiku_templates_omit_effort_line() -> None:
    for role in HAIKU_ROLES:
        head = (TEMPLATES / f"{role}.md").read_text().split("\n---", 1)[0]
        assert "effort:" not in head, f"{role} template must omit effort frontmatter"
    tmpl = gs.load_template_alloc()
    for role in HAIKU_ROLES:
        assert tmpl[role][1] is None, role


def test_non_haiku_templates_carry_effort_line() -> None:
    tmpl = gs.load_template_alloc()
    for key, (model, effort) in tmpl.items():
        if model != "haiku":
            assert effort is not None, f"{key} ({model}) must carry an effort value"


def test_template_routes_match_communication_flows() -> None:
    routes = gs.load_outbound_routes()
    assert routes is not None
    for path in TEMPLATES.glob("*.md"):
        key = path.stem
        section = _section(path.read_text(), "Allowed communication routes")
        in_template = set(_ROUTE_RE.findall(section))
        declared = {receiver for _, receiver in routes.get(key, [])}
        assert in_template == declared, f"{key}: {in_template} != {declared}"


def test_learned_section_is_empty_on_seed() -> None:
    for path in TEMPLATES.glob("*.md"):
        learned = _section(path.read_text(), "Learned")

        for raw in learned.splitlines():
            line = raw.strip()
            if not line or line.startswith("<!--") or line.startswith("-->"):
                continue

            assert not line.startswith("- "), f"{path.name} ## Learned not empty: {line}"


def test_every_shim_references_its_guild_template() -> None:
    for key in _all_template_keys():
        shim = (SHIMS / f"{key}.md").read_text()
        assert f"governance/agent-templates/{key}.md" in shim, key


def test_shim_model_matches_template_model() -> None:
    tmpl = gs.load_template_alloc()
    for key, (model, _) in tmpl.items():
        fm = (SHIMS / f"{key}.md").read_text().split("\n---", 1)[0]
        assert re.search(rf"^model:\s*{model}\s*$", fm, re.M), key


def test_build_template_is_idempotent() -> None:
    routes = gs.load_outbound_routes()
    overlay = (REPO_ROOT / "engineering" / "agents" / "backend-eng-1" / "AGENTS.md").read_text()
    a = gat.build_template(
        "backend-eng-1", "Backend Engineer 1", "engineering", "Backend EM",
        overlay, "sonnet", "medium", routes,
    )
    b = gat.build_template(
        "backend-eng-1", "Backend Engineer 1", "engineering", "Backend EM",
        overlay, "sonnet", "medium", routes,
    )
    assert a == b


def test_build_template_haiku_omits_effort_frontmatter() -> None:
    overlay = (REPO_ROOT / "product" / "agents" / "tech-writer" / "AGENTS.md").read_text()
    out = gat.build_template(
        "tech-writer", "Technical Writer", "product", "CPO",
        overlay, "haiku", None, gs.load_outbound_routes(),
    )
    head = out.split("\n---", 1)[0]
    assert "effort:" not in head
    assert "haiku does not support" in out


def test_load_template_alloc_absent_dir_returns_empty(tmp_path: Path) -> None:
    assert gs.load_template_alloc(tmp_path / "nope") == {}


def test_load_template_alloc_parses_effort_and_none(tmp_path: Path) -> None:
    d = tmp_path / "agent-templates"
    d.mkdir()
    (d / "cto.md").write_text("---\nrole: cto\nmodel: opus\neffort: high\n---\nbody\n")
    (d / "tech-writer.md").write_text("---\nrole: tech-writer\nmodel: haiku\n---\nbody\n")
    alloc = gs.load_template_alloc(d)
    assert alloc == {"cto": ("opus", "high"), "tech-writer": ("haiku", None)}
