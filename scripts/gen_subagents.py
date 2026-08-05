#!/usr/bin/env python3

import json
import re

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


MODEL_POLICY = ROOT / "governance" / "policies" / "model-allocation.md"


ROW_RE = re.compile(
    r"^\|\s*`?([a-z0-9-]+)`?\s*\|\s*(opus|sonnet|haiku)\s*\|"
    r"\s*(max|xhigh|high|medium|low)?\s*\|",
    re.M,
)


EFFORT_DEFAULT_BY_MODEL = {"opus": "high", "sonnet": "medium"}


TEMPLATES = ROOT / "governance" / "agent-templates"

_TMPL_MODEL_RE = re.compile(r"^model:\s*(opus|sonnet|haiku)\s*$", re.M)
_TMPL_EFFORT_RE = re.compile(r"^effort:\s*(max|xhigh|high|medium|low)\s*$", re.M)


def load_alloc():
    if not MODEL_POLICY.exists():
        raise SystemExit(f"FATAL: {MODEL_POLICY} missing — model allocation is board policy")
    models, efforts = {}, {}
    for role, model, effort in ROW_RE.findall(MODEL_POLICY.read_text()):
        models[role] = model
        efforts[role] = None if model == "haiku" else (effort or EFFORT_DEFAULT_BY_MODEL[model])
    return models, efforts


def field(text, name):
    m = re.search(rf"^\-\s*\*\*{name}:\*\*\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def iter_overlays(depts=DEPTS):
    for dept in depts:
        agents_dir = ROOT / dept / "agents"
        if not agents_dir.is_dir():
            continue
        for d in sorted(agents_dir.iterdir()):
            key = d.name
            overlay = d / "AGENTS.md"
            if key in SKIP or not overlay.exists():
                continue
            yield key, overlay.read_text()


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
        overlays = iter_overlays()
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()

    roles = []
    for dept in DEPTS:
        for d in sorted((ROOT / dept / "agents").iterdir()):
            key = d.name
            overlay = d / "AGENTS.md"
            if key in SKIP or not overlay.exists():
                continue
            text = overlay.read_text()
            display = field(text, "Display name") or key
            reports = field(text, "Reports to")
            roles.append((key, display, dept, reports))

    models, efforts = load_alloc()
    routes = load_outbound_routes()
    missing = [k for k, _, _, _ in roles if k not in models]
    if missing:
        raise SystemExit(
            f"FATAL: no model row in {MODEL_POLICY.name} for: {', '.join(missing)} — "
            "add them to the allocation table, then re-run")


    import gen_agent_templates
    gen_agent_templates.generate()
    tmpl_alloc = load_template_alloc()
    for key, _, _, _ in roles:
        if key not in tmpl_alloc:
            continue
        t_model, t_effort = tmpl_alloc[key]
        if t_model != models[key] or t_effort != efforts[key]:
            raise SystemExit(
                f"FATAL: guild template governance/agent-templates/{key}.md declares "
                f"model={t_model}/effort={t_effort} but model-allocation.md says "
                f"model={models[key]}/effort={efforts[key]} — re-run "
                "scripts/gen_agent_templates.py (ADR-0029 G-3)")

        models[key], efforts[key] = t_model, t_effort

    for key, display, dept, reports in roles:
        overlay_rel = f"{dept}/agents/{key}/AGENTS.md"
        template_rel = f"governance/agent-templates/{key}.md"
        template_present = key in tmpl_alloc
        effort = efforts[key]
        effort_line = f"\neffort: {effort}" if effort else ""
        routes_section = format_routes_block(key, routes)
        guild_line = (
            f"> **Guild template (ADR-0029):** `{template_rel}` — the canonical per-role "
            "craft file (identity, priors, toolkit, model+effort, routes, eval baseline, "
            "`## Learned`) this shim is compiled from."
            if template_present
            else f"> **Guild template (ADR-0029):** `{template_rel}` "
            "_(not yet in-tree — compiled directly from overlay + policy + flows)_."
        )
        body = f"""---
name: {key}
model: {models[key]}{effort_line}
description: DasLab {dept} role — {display}. Spawn with exactly ONE ticket file path from board/tickets/ to execute that ticket per the role overlay. Reports to {reports or 'the Board'}.
---

You are **{display}** in DasLab's {dept} department, running as a Claude Code subagent.
Work from the repository root — your current working directory (the folder the Claude Code session was started in).

{guild_line}

## Read first (one parallel batch — Read all three in a single message)
Issue these three Reads together as parallel tool calls, not one-by-one — they
have no dependency on each other, so reading them serially only adds latency:
- `{dept}/CLAUDE.md` — dept charter: what you may and may not decide.
- `{overlay_rel}` — YOUR role overlay: identity, mission, definition of done.
- `board/README.md` — the ticket schema and board rules.
Then read the ticket file named in your prompt and start work.

## How you work a ticket (binding)
- The *ticket* is the file in `board/tickets/` named in your prompt. Work ONLY that one (WIP = 1).
- Edit that file directly — there is no remote API to call; your edits ARE the state.
- Update the `status:` frontmatter field (and `updated:`) as the work moves.
- Append under `## Log`: `### <date> — {display}` + what you did / found / decided.
- This is a single run: do the ticket's next concrete step, update the file, and return.
- Dispatch pacing is the orchestrator's concern, not yours.

## Hard rules (AGENTS.md §6, unchanged in spirit)
- Engineering work in a git repo: one issue = one branch = one PR; a git worktree
  per issue; never commit to `main`; `in_review` requires a pushed branch/PR;
  `done` requires the PR merged with green CI.
- Never review your own work: when your work is ready, set `status: in_review`
  and set `assignee:` to your reviewer per `board/ROUTING.md` (your manager{': ' + reports if reports else ''}).
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
        (OUT / f"{key}.md").write_text(body)
        print(f"  ✓ .claude/agents/{key}.md")

    routing = ["# Role routing — reviewer/manager per role", "",
               "> Generated by scripts/gen_subagents.py — do not edit by hand.",
               "> `in_review` tickets are assigned to the author's manager below;",
               "> if the manager IS the author, escalate one level (ultimately CTO/CEO).", "",
               "| Role key | Display name | Dept | Reports to (reviewer) |",
               "|---|---|---|---|"]
    for key, display, dept, reports in roles:
        routing.append(f"| `{key}` | {display} | {dept} | {reports or '—'} |")
    (ROOT / "board" / "ROUTING.md").write_text("\n".join(routing) + "\n")
    print(f"  ✓ board/ROUTING.md ({len(roles)} roles)")


    allow = write_tool_allowlist()
    print(f"  ✓ board/.tool-allowlist.json ({len(allow)} tool grant(s))")


if __name__ == "__main__":
    main()
