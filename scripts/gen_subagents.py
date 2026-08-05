#!/usr/bin/env python3

import json
import re

import org_model
import yaml
from _paths import ROOT

OUT = ROOT / ".claude" / "agents"
SKIP = set()
DEPTS = ["governance", "engineering", "product", "design", "marketing", "operations"]


TOOL_ALLOWLIST_OUT = ROOT / "board" / ".tool-allowlist.json"


_EXTERNAL_TOOLS_RE = re.compile(
    r"^##\s+External tools\b.*?\n```ya?ml\s*\n(.*?)\n```",
    re.S | re.M | re.I,
)


FLOWS = ROOT / "governance" / "communication-flows.yaml"


ORG_CONFIG = org_model.ORG_CONFIG_PATH


EFFORT_DEFAULT_BY_MODEL = {"opus": "high", "sonnet": "medium"}


TEMPLATES = ROOT / "governance" / "agent-templates"

_TMPL_MODEL_RE = re.compile(r"^model:\s*(opus|sonnet|haiku)\s*$", re.M)
_TMPL_EFFORT_RE = re.compile(r"^effort:\s*(max|xhigh|high|medium|low)\s*$", re.M)


def load_alloc(org=None):
    org = org or org_model.load_org()
    models = {role.key: role.model.value for role in org.roles}
    efforts = {
        role.key: (role.effort.value if role.effort is not None else None)
        for role in org.roles
    }
    return models, efforts


def render_external_tools_block(role):
    if not role.tool_grants:
        return ""
    payload = {
        "external_tools": [
            {
                "server": grant.server,
                "tools": list(grant.tools),
                "egress_profile": grant.egress_profile,
            }
            for grant in role.tool_grants
        ]
    }
    body = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    return "## External tools\n```yaml\n" + body + "```\n"


def iter_overlays(depts=DEPTS, org=None):
    org = org or org_model.load_org()
    for dept in depts:
        for role in sorted(org.roles_in(dept), key=lambda r: r.key):
            if role.key in SKIP:
                continue
            yield role.key, render_external_tools_block(role)


def parse_external_tools(overlay_text):
    m = _EXTERNAL_TOOLS_RE.search(overlay_text)
    if not m:
        return []
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return []
    grants = data.get("external_tools") if isinstance(data, dict) else None
    return grants if isinstance(grants, list) else []


def compile_tool_allowlist(overlays=None):
    if overlays is None:
        return org_model.tool_allowlist()
    grant_map: dict[str, set[str]] = {}
    for role_key, text in overlays:
        for grant in parse_external_tools(text):
            if not isinstance(grant, dict):
                continue
            server = str(grant.get("server", "")).strip()
            if not server:
                continue
            tools = grant.get("tools") or []
            if not isinstance(tools, list):
                tools = [tools]
            if any(str(t).strip() == "*" for t in tools):
                grant_map.setdefault(server, set()).add(role_key)
            else:
                for t in tools:
                    t = str(t).strip()
                    if t:
                        grant_map.setdefault(f"{server}__{t}", set()).add(role_key)
    return {k: sorted(v) for k, v in sorted(grant_map.items())}


def write_tool_allowlist():
    allow = compile_tool_allowlist()
    TOOL_ALLOWLIST_OUT.write_text(json.dumps(allow, indent=2, sort_keys=True) + "\n")
    return allow


def load_template_alloc(templates_dir=TEMPLATES):
    if not templates_dir.is_dir():
        return {}
    out: dict[str, tuple[str, str | None]] = {}
    for path in sorted(templates_dir.glob("*.md")):
        head = path.read_text().split("\n---", 1)[0]
        mm = _TMPL_MODEL_RE.search(head)
        if not mm:
            continue
        me = _TMPL_EFFORT_RE.search(head)
        out[path.stem] = (mm.group(1), me.group(1) if me else None)
    return out


def load_outbound_routes(flows_path=FLOWS):
    if not flows_path.exists():
        return None
    data = yaml.safe_load(flows_path.read_text()) or {}
    routes: dict[str, list[tuple[str, str]]] = {}
    for edge in data.get("flows", []) or []:
        if not isinstance(edge, dict):
            continue
        sender = edge.get("sender")
        receiver = edge.get("receiver")
        if not sender or not receiver:
            continue
        routes.setdefault(sender, []).append((str(edge.get("kind", "")), receiver))
    for sender in routes:
        routes[sender] = sorted(set(routes[sender]))
    return routes


def format_routes_block(key, routes):
    if routes is None:
        return "- _(governance/communication-flows.yaml not yet in-tree — no routes compiled)_"
    mine = routes.get(key, [])
    if not mine:
        return "- _(none — this role originates no delegation or escalation routes)_"
    return "\n".join(f"- {kind} → `{receiver}`" for kind, receiver in mine)


def build_shim(role, org, routes, template_present):
    reviewer_title = org.title_of(role.reports_to)
    effort_line = f"\neffort: {role.effort.value}" if role.effort else ""
    template_rel = f"governance/agent-templates/{role.key}.md"
    guild_line = (
        f"> **Guild template (ADR-0029):** `{template_rel}` — the canonical per-role "
        "craft file (identity, priors, toolkit, model+effort, routes, eval baseline, "
        "`## Learned`) this shim is compiled from."
        if template_present
        else f"> **Guild template (ADR-0029):** `{template_rel}` "
        "_(not yet in-tree — compiled directly from config/org.yaml + flows)_."
    )
    routes_section = format_routes_block(role.key, routes)
    return f"""---
name: {role.key}
model: {role.model.value}{effort_line}
description: DasLab {role.dept} role — {role.title}. Spawn with exactly ONE ticket file path from board/tickets/ to execute that ticket per the org role charter. Reports to {reviewer_title}.
---

You are **{role.title}** in DasLab's {role.dept} department, running as a Claude Code subagent.
Work from the repository root — your current working directory (the folder the Claude Code session was started in).

{guild_line}

## Role charter (config/org.yaml → roles[{role.key}])
{role.charter.mission}

### Scope
{role.charter.scope}

### Definition of Done
{role.charter.definition_of_done}

### Escalation
{role.charter.escalation}

## How you work a ticket (binding)
- The *ticket* is the file in `board/tickets/` named in your prompt. Work ONLY that one (WIP = 1).
- Edit that file directly — there is no remote API to call; your edits ARE the state.
- Update the `status:` frontmatter field (and `updated:`) as the work moves.
- Append under `## Log`: `### <date> — {role.title}` + what you did / found / decided.
- This is a single run: do the ticket's next concrete step, update the file, and return.
- Dispatch pacing is the orchestrator's concern, not yours.

## Hard rules
- Engineering work in a git repo: one issue = one branch = one PR; a git worktree
  per issue; never commit to `main`; `in_review` requires a pushed branch/PR;
  `done` requires the PR merged with green CI.
- Never review your own work: when your work is ready, set `status: in_review`
  and set `assignee:` to your reviewer from the org routing table ({reviewer_title}).
- Blocked → `status: blocked` + a precise reason in the log. Never sit silent.
- A decision above your charter authority → log an escalation in the ticket,
  leave status unchanged, and say so in your report.
- You cannot spawn other agents. Anything needing another role goes in the log
  + your report so the orchestrator routes it.

## Allowed outbound routes (compiled from governance/communication-flows.yaml)
The org communication fabric is a closed graph: you may address ONLY the roles
listed below. A `(sender, receiver)` pair absent from this list is an undeclared
route — it has no place in your definition, so it is structurally unrepresentable,
and `scripts/check_comm_flows.py` fails any ticket/dispatch that references one.
This block is compiled from `governance/communication-flows.yaml` — do not hand-edit;
re-run `scripts/gen_subagents.py`.

{routes_section}

## Report
Your final message is read by the orchestrator, not a human. Return: ticket id,
what you changed, the new status, files/branches/PRs touched, and anything that
must be routed (reviews, escalations, new work discovered).
"""


def main():
    org = org_model.load_org()

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()

    models, efforts = load_alloc(org)

    import gen_agent_templates
    gen_agent_templates.generate(org=org)
    tmpl_alloc = load_template_alloc()
    for key in models:
        if key not in tmpl_alloc:
            continue
        t_model, t_effort = tmpl_alloc[key]
        if t_model != models[key] or t_effort != efforts[key]:
            raise SystemExit(
                f"FATAL: guild template governance/agent-templates/{key}.md declares "
                f"model={t_model}/effort={t_effort} but config/org.yaml says "
                f"model={models[key]}/effort={efforts[key]} — re-run "
                "scripts/gen_agent_templates.py (ADR-0029 G-3)")

    routes = load_outbound_routes()
    for dept in DEPTS:
        for role in sorted(org.roles_in(dept), key=lambda r: r.key):
            body = build_shim(role, org, routes, role.key in tmpl_alloc)
            (OUT / f"{role.key}.md").write_text(body)
            print(f"  ✓ .claude/agents/{role.key}.md")

    allow = write_tool_allowlist()
    print(f"  ✓ board/.tool-allowlist.json ({len(allow)} tool grant(s))")


if __name__ == "__main__":
    main()
