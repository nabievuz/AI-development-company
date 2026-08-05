#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path

import gen_subagents as gs
import org_model
from _paths import ROOT

TEMPLATES = ROOT / "governance" / "agent-templates"


_CORE_TOOLKIT = ["Read", "Grep", "Glob"]
_AUTHOR_TOOLKIT = _CORE_TOOLKIT + ["Edit", "Write"]
_FULL_TOOLKIT = _AUTHOR_TOOLKIT + ["Bash"]
DEPT_TOOLKIT: dict[str, list[str]] = {
    "governance": _FULL_TOOLKIT,
    "engineering": _FULL_TOOLKIT,
    "product": _FULL_TOOLKIT,
    "operations": _FULL_TOOLKIT,
    "design": _AUTHOR_TOOLKIT,
    "marketing": _AUTHOR_TOOLKIT,
}

REQUIRED_HEADINGS: tuple[str, ...] = (
    "## Identity",
    "## Goal",
    "## Behavioral priors",
    "## Toolkit allowlist",
    "## Model + effort",
    "## Produces / consumes defaults",
    "## Allowed communication routes",
    "## Eval baseline",
    "## Learned",
)


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    dot = text.find(". ")
    return text[: dot + 1] if dot != -1 else text


def build_template(role, reviewer_title: str, routes) -> str:
    mission = role.charter.mission or (
        f"Own the {role.dept} tickets routed to `{role.key}`, one at a time (WIP = 1)."
    )
    dof = re.sub(r"^\s*[-*]\s+", "", role.charter.definition_of_done)
    dof_prior = _first_sentence(dof) if dof else (
        "Deliver the assigned ticket to its Definition of Done, update the ticket "
        "file (status + `## Log`), and hand off to your reviewer."
    )

    effort = role.effort.value if role.effort is not None else None
    effort_fm = f"\neffort: {effort}" if effort else ""
    effort_line = (
        f"- **effort:** {effort}"
        if effort
        else "- **effort:** _(none — haiku does not support `effort`)_"
    )

    toolkit = DEPT_TOOLKIT.get(role.dept, _AUTHOR_TOOLKIT)
    toolkit_block = "\n".join(f"- `{tool}`" for tool in toolkit)

    routes_block = gs.format_routes_block(role.key, routes)

    return f"""---
role: {role.key}
dept: {role.dept}
model: {role.model.value}{effort_fm}
---

# Guild template — {role.title}

## Identity
- **Role key:** `{role.key}`
- **Display name:** {role.title}
- **Dept:** {role.dept}
- **Reports to:** {reviewer_title}

## Goal
{mission}

## Behavioral priors
- Work one ticket at a time (WIP = 1); edit the ticket file directly — its
  `status` frontmatter and `## Log` ARE the state, there is no external API.
- Never review your own work: set `in_review` and hand off to your reviewer from
  the org routing table ({reviewer_title}).
- A decision above your charter authority is escalated, never decided
  unilaterally; a cross-dept impact is flagged, not decided alone.
- {dof_prior}

## Toolkit allowlist
> Positive craft statement (ADR-0029 G-2) — the tools this role characteristically
> reaches for. It does NOT widen any security boundary; the sandbox/permission
> layer remains the boundary.
{toolkit_block}

## Model + effort (VERBATIM — config/org.yaml)
- **model:** {role.model.value}
{effort_line}

## Produces / consumes defaults
> Role-level typed-artifact defaults (ADR-0029 G-2 / DAS-1467). A ticket may
> override; names resolve to `governance/schemas/<name>.yaml`.
- **produces:** _(none by default — set per ticket)_
- **consumes:** _(none by default — set per ticket)_

## Allowed communication routes (governance/communication-flows.yaml)
> The role's outbound `(delegation | escalation) → receiver` edges, compiled from
> the flows graph (ADR-0026) — never hand-authored topology.
{routes_block}

## Eval baseline
- `evals/{role.key}/` — golden-eval harness + scorecard (WS6 O6-T05); the bar
  this role's craft is measured against (target ≥80% at the assigned tier).

## Learned
"""


def build_template_for(key: str, org=None, routes=None) -> str:
    org = org or org_model.load_org()
    role = org.role(key)
    if routes is None:
        routes = gs.load_outbound_routes()
    return build_template(role, org.title_of(role.reports_to), routes)


def generate(*, verbose: bool = False, org=None) -> list[Path]:
    org = org or org_model.load_org()
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    for old in TEMPLATES.glob("*.md"):
        old.unlink()

    routes = gs.load_outbound_routes()
    written: list[Path] = []
    for dept in gs.DEPTS:
        for role in sorted(org.roles_in(dept), key=lambda r: r.key):
            body = build_template(role, org.title_of(role.reports_to), routes)
            path = TEMPLATES / f"{role.key}.md"
            path.write_text(body)
            written.append(path)
            if verbose:
                print(f"  ✓ governance/agent-templates/{role.key}.md")
    return written


def main() -> None:
    written = generate(verbose=True)
    print(f"  ✓ {len(written)} guild templates in governance/agent-templates/")


if __name__ == "__main__":
    main()
