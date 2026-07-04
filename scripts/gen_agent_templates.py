#!/usr/bin/env python3
"""Generate per-ROLE guild agent-templates from the DasLab org tree (ADR-0029).

For every ``<dept>/agents/<role-key>/AGENTS.md`` role overlay, emit a single
canonical craft file ``governance/agent-templates/<role-key>.md`` — the "guild
template" of the role (ADR-0029 G-1..G-5).

A guild template is the per-ROLE craft captured as one reviewable, compilable
artifact, grouped by dept, introducing NO new org unit / node / routing edge
(ADR-0029 G-1). It is SEEDED from the already-existing sources, never
hand-authored topology or a forked SSOT (G-5):

* identity / goal / behavioral-priors  ← the ``<dept>/agents/<role>/AGENTS.md``
  overlay (display name, dept, reports-to, mission, definition-of-done);
* ``model`` + ``effort``               ← VERBATIM from
  ``governance/policies/model-allocation.md`` (G-3; no Tier F / Fable 5; haiku
  omits ``effort``);
* allowed communication routes         ← ``governance/communication-flows.yaml``
  (the same outbound edge set the shim already compiles, ADR-0026);
* toolkit allowlist / produces-consumes defaults / eval-baseline reference
  (the closed craft field set, G-2);
* an empty ``## Learned`` section        ← reserved for the ``daslab-learn``
  distillation of Founder-accepted lessons (DAS-1489; the ONLY growth surface).

The overlays + policy + flows stay the single source of truth; this generator is
a pure *consumer* that composes them into one file per role. It is idempotent —
the output is fully regenerated and byte-stable across runs, so a stale template
shows up as a git diff (generate-and-diff clean).

``scripts/gen_subagents.py`` then READS these templates to compile the runtime
``.claude/agents/<role>.md`` shims (ADR-0029 G-4), guarded by
``scripts/check_agents_sync.py``.

Re-run after editing any overlay, the model-allocation table, or the flows file.
"""
from __future__ import annotations

import re
from pathlib import Path

import gen_subagents as gs
from _paths import ROOT

TEMPLATES = ROOT / "governance" / "agent-templates"

# Toolkit allowlist per department (ADR-0029 G-2). A POSITIVE craft statement of
# the tools a role characteristically reaches for — it does NOT widen any
# security boundary (the sandbox / permission layer is the boundary, not this
# list). Every role gets the read/search core; executor depts add write+shell.
_CORE_TOOLKIT = ["Read", "Grep", "Glob"]
_AUTHOR_TOOLKIT = _CORE_TOOLKIT + ["Edit", "Write"]
_FULL_TOOLKIT = _AUTHOR_TOOLKIT + ["Bash"]
DEPT_TOOLKIT: dict[str, list[str]] = {
    "governance": _FULL_TOOLKIT,   # runs validators / diagnostics on governance edits
    "engineering": _FULL_TOOLKIT,  # code + tests + shell
    "product": _FULL_TOOLKIT,      # PMs/analysts run board_lint + validators
    "operations": _FULL_TOOLKIT,   # finance/legal analysts run scripts
    "design": _AUTHOR_TOOLKIT,     # design artifacts / docs, no shell by default
    "marketing": _AUTHOR_TOOLKIT,  # copy / content authoring, no shell by default
}


def _section(text: str, heading: str) -> str:
    """Return the body of a ``## <heading>`` section from overlay *text*, trimmed.

    Reads from the heading line up to the next ``## `` heading (or EOF) and
    collapses it to a single-space-joined string. Returns "" when the section is
    absent so the caller can fall back to a default.
    """
    m = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    body = m.group(1).strip()
    return body


def _first_sentence(text: str) -> str:
    """First sentence of *text* (through the first period), or the whole string."""
    text = " ".join(text.split())
    dot = text.find(". ")
    return text[: dot + 1] if dot != -1 else text


def build_template(
    key: str,
    display: str,
    dept: str,
    reports: str,
    overlay_text: str,
    model: str,
    effort: str | None,
    routes,
) -> str:
    """Compose the ``governance/agent-templates/<key>.md`` markdown for one role."""
    mission = _section(overlay_text, "Mission") or (
        f"Own the {dept} tickets routed to `{key}`, one at a time (WIP = 1)."
    )
    dof = _section(overlay_text, "Definition of Done")
    dof = re.sub(r"^\s*[-*]\s+", "", dof)  # drop a leading bullet marker
    dof_prior = _first_sentence(dof) if dof else (
        "Deliver the assigned ticket to its Definition of Done, update the ticket "
        "file (status + `## Log`), and hand off to your reviewer."
    )

    effort_fm = f"\neffort: {effort}" if effort else ""
    effort_line = (
        f"- **effort:** {effort}"
        if effort
        else "- **effort:** _(none — haiku does not support `effort`)_"
    )

    toolkit = DEPT_TOOLKIT.get(dept, _AUTHOR_TOOLKIT)
    toolkit_block = "\n".join(f"- `{tool}`" for tool in toolkit)

    routes_block = gs.format_routes_block(key, routes)

    return f"""---
role: {key}
dept: {dept}
model: {model}{effort_fm}
---

# Guild template — {display}

<!-- GENERATED by scripts/gen_agent_templates.py (ADR-0029 G-1..G-5). SEED from
     {dept}/agents/{key}/AGENTS.md + governance/policies/model-allocation.md
     (model + effort VERBATIM) + governance/communication-flows.yaml (routes).
     Do NOT hand-edit the compiled fields — re-run the generator. The `## Learned`
     section is the ONLY growth surface (DAS-1489 daslab-learn distillation). -->

## Identity
- **Role key:** `{key}`
- **Display name:** {display}
- **Dept:** {dept}
- **Reports to:** {reports or 'the Board'}

## Goal
{mission}

## Behavioral priors
- Work one ticket at a time (WIP = 1); edit the ticket file directly — its
  `status` frontmatter and `## Log` ARE the state, there is no external API.
- Never review your own work: set `in_review` and hand off to your reviewer per
  `board/ROUTING.md` ({reports or 'the Board'}).
- A decision above your charter authority is escalated, never decided
  unilaterally; a cross-dept impact is flagged, not decided alone.
- {dof_prior}

## Toolkit allowlist
> Positive craft statement (ADR-0029 G-2) — the tools this role characteristically
> reaches for. It does NOT widen any security boundary; the sandbox/permission
> layer remains the boundary.
{toolkit_block}

## Model + effort (VERBATIM — governance/policies/model-allocation.md)
- **model:** {model}
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
- `evals/{key}/` — golden-eval harness + scorecard (WS6 O6-T04 / O6-T05); the bar
  this role's craft is measured against (target ≥80% at the assigned tier).

## Learned
<!-- RESERVED for the DAS-1489 daslab-learn distillation of Founder-accepted
     feedback: bounded, deduped, dated lessons only. Empty on seed — an agent
     never free-writes here mid-run (ADR-0029 G-5). -->
"""


def collect_roles():
    """Return ``[(key, display, dept, reports), ...]`` for every in-tree overlay.

    Mirrors ``gen_subagents.main()``'s overlay walk so the two generators see the
    exact same role set.
    """
    roles = []
    for dept in gs.DEPTS:
        agents_dir = ROOT / dept / "agents"
        if not agents_dir.is_dir():
            continue
        for d in sorted(agents_dir.iterdir()):
            key = d.name
            overlay = d / "AGENTS.md"
            if key in gs.SKIP or not overlay.exists():
                continue
            text = overlay.read_text()
            display = gs.field(text, "Display name") or key
            reports = gs.field(text, "Reports to")
            roles.append((key, display, dept, reports))
    return roles


def generate(*, verbose: bool = False) -> list[Path]:
    """Regenerate every ``governance/agent-templates/<role>.md`` file.

    Idempotent: the directory is cleared of ``*.md`` and fully rewritten, so the
    output is byte-stable across runs (generate-and-diff clean). Returns the list
    of written paths.
    """
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    for old in TEMPLATES.glob("*.md"):
        old.unlink()

    roles = collect_roles()
    models, efforts = gs.load_alloc()
    routes = gs.load_outbound_routes()

    missing = [k for k, _, _, _ in roles if k not in models]
    if missing:
        raise SystemExit(
            f"FATAL: no model row in {gs.MODEL_POLICY.name} for: {', '.join(missing)} — "
            "add them to the allocation table, then re-run")

    written: list[Path] = []
    for key, display, dept, reports in roles:
        overlay_text = (ROOT / dept / "agents" / key / "AGENTS.md").read_text()
        body = build_template(
            key, display, dept, reports, overlay_text,
            models[key], efforts[key], routes,
        )
        path = TEMPLATES / f"{key}.md"
        path.write_text(body)
        written.append(path)
        if verbose:
            print(f"  ✓ governance/agent-templates/{key}.md")
    return written


def main() -> None:
    written = generate(verbose=True)
    print(f"  ✓ {len(written)} guild templates in governance/agent-templates/")


if __name__ == "__main__":
    main()
