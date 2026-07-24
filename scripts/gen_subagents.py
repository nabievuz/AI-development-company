#!/usr/bin/env python3
"""Generate Claude Code subagent definitions from the DasLab org tree.

For every <dept>/agents/<role-key>/AGENTS.md role overlay, emit
.claude/agents/<role-key>.md (the Claude Code subagent definition) plus
board/ROUTING.md (role -> reviewer/manager table used for in_review routing).

The overlays stay the single source of truth for each role's mission; the
generated subagent is a thin shim that (a) points the subagent at its overlay
and dept charter, and (b) states the file-based board protocol directly — edit the
ticket file; its `status`/`## Log` ARE the state, and there is no external API.

Re-run after editing any overlay. Idempotent — output is fully regenerated.
Runtime pilots tied to non-Claude runtimes are skipped (they were adapter
experiments, not Claude roles).
"""
import json
import re

import yaml
from _paths import ROOT

OUT = ROOT / ".claude" / "agents"
SKIP = set()  # (no external-runtime pilots)
DEPTS = ["governance", "engineering", "product", "design", "marketing", "operations"]

# WS-A (ADR-0033 TB-2): compile each overlay's `## External tools` YAML block into
# board/.tool-allowlist.json — the compiled least-privilege grant map the PreToolUse
# hook (tools/mcp_bridges/audit_external_tool.py) reads. TRACKED + generate-and-diff
# (C1): a hand-edit of the JSON diverges from this compile and the drift test reddens.
TOOL_ALLOWLIST_OUT = ROOT / "board" / ".tool-allowlist.json"
# Capture the fenced YAML block that immediately follows a `## External tools`
# heading (the section may carry an HTML comment before the fence).
_EXTERNAL_TOOLS_RE = re.compile(
    r"^##\s+External tools\b.*?\n```ya?ml\s*\n(.*?)\n```",
    re.S | re.M | re.I,
)

# Communication fabric (ADR-0026): the closed set of allowed (sender -> receiver)
# routes, authored/validated by DAS-1465. Each role's OUTBOUND routes are compiled
# into its generated shim below, so a route the role is not granted has no place in
# its definition — structurally unrepresentable (DAS-1466, §5 row 9).
FLOWS = ROOT / "governance" / "communication-flows.yaml"

# Binding model allocation (board policy). The table in that file is the single
# source of truth: | `role` | opus/sonnet/haiku | effort | rationale | (ADR 0013).
# (Fable 5 is retired/disabled — Tier F runs on opus; there is no fable tier.)
MODEL_POLICY = ROOT / "governance" / "policies" / "model-allocation.md"
# Capture role, model, and the OPTIONAL Effort cell (col 3); rationale (col 4) is
# ignored. A 3-col row (no effort cell) fails this regex, so the table edit and
# this generator change land together (ADR 0013). Haiku's effort cell is blank.
ROW_RE = re.compile(
    r"^\|\s*`?([a-z0-9-]+)`?\s*\|\s*(opus|sonnet|haiku)\s*\|"
    r"\s*(max|xhigh|high|medium|low)?\s*\|",
    re.M,
)
# An explicit per-role Effort cell wins; this is the fallback for a blank cell.
# Haiku takes NO effort parameter (400 error) — its frontmatter omits the line.
EFFORT_DEFAULT_BY_MODEL = {"opus": "high", "sonnet": "medium"}

# Guild agent-templates (ADR-0029): the per-ROLE craft file that is the canonical
# source-of-truth for a role. `scripts/gen_agent_templates.py` seeds each template
# from the overlay + this same model-allocation table + communication-flows; the
# shim below is COMPILED FROM the template (ADR-0029 G-4). model+effort in a
# template are copied VERBATIM from the allocation table (G-3), so the generator
# cross-checks them against load_alloc() and fails loudly on any drift. When a
# template is absent (sparse worktree) the compile falls back to the direct
# sources, mirroring the flows-absent tolerance.
TEMPLATES = ROOT / "governance" / "agent-templates"
# Parse `model:` / `effort:` out of a template's YAML frontmatter block.
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
    """Yield ``(role_key, overlay_text)`` for every role overlay in the org tree.

    Shared by the shim generator and the tool-allowlist compiler so both read the
    exact same SSOT set (no drift between "who has a shim" and "who has a grant").
    """
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
    """Return the ``external_tools`` list from an overlay's `## External tools` block.

    Absent section (the common case) → ``[]``. Malformed YAML → ``[]`` (the overlay
    grants nothing rather than crashing the whole compile; a bad block simply grants
    no reach — deny-by-default).
    """
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
    """Compile overlay `## External tools` grants → the TB-2 allow-list map.

    Shape (exactly what ``audit_external_tool.decide()`` reads)::

        { "mcp__<server>": ["role-a", "role-b"],           # server-level grant
          "mcp__<server>__<tool>": ["role-c"] }             # tool-level grant

    The value is ALWAYS a sorted list of EXPLICIT role keys — never ``"*"`` (C2):
    a server-wide ``tools: ["*"]`` overlay grant compiles to the explicit list of
    roles that declared it, so "any-role" is structurally unrepresentable in the
    compiled map. A role appears under a key only if its overlay declared it
    (union of declarations; no default entry, no wildcard role).
    """
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
                # Server-wide grant → the SERVER key, mapped to the EXPLICIT role
                # (never the literal "*"). C2: no "*" value is ever emitted.
                grant_map.setdefault(server, set()).add(role_key)
            else:
                for t in tools:
                    t = str(t).strip()
                    if t:
                        grant_map.setdefault(f"{server}__{t}", set()).add(role_key)
    return {k: sorted(v) for k, v in sorted(grant_map.items())}


def write_tool_allowlist():
    """Write the compiled TB-2 allow-list to the tracked artifact (idempotent)."""
    allow = compile_tool_allowlist()
    TOOL_ALLOWLIST_OUT.write_text(json.dumps(allow, indent=2, sort_keys=True) + "\n")
    return allow


def load_template_alloc(templates_dir=TEMPLATES):
    """Return ``{role_key: (model, effort_or_None)}`` from the guild templates.

    Reads ``model:`` / ``effort:`` out of each ``governance/agent-templates/<role>.md``
    frontmatter (ADR-0029). A haiku template carries no ``effort:`` line, so its
    effort is ``None``. Returns ``{}`` when the templates directory is absent
    (sparse worktree) — the caller then falls back to the allocation table.
    """
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
    """Return ``{sender_key: [(kind, receiver), ...]}`` from communication-flows.yaml.

    The per-sender list is de-duplicated and sorted ``(kind, receiver)`` so the
    generated shim is byte-stable across regenerations (regenerate-and-diff clean).
    Returns ``None`` when the flows file is absent (sparse worktree) — the route
    section then records that the fabric is not yet in-tree instead of crashing.
    """
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
    """Render the compiled outbound-route lines for role *key* (one per allowed route)."""
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

    roles = []  # (key, display, dept, reports_to)
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

    # ADR-0029 G-4: the shim is COMPILED FROM the per-role guild template. Regenerate
    # the templates from the same SSOTs (lazy import avoids a module-load cycle), then
    # read model+effort BACK from each template so the shim's values genuinely flow
    # overlay+policy → template → shim. A template's model/effort is a VERBATIM copy of
    # the allocation table (G-3); cross-check it here and fail loudly on any drift.
    import gen_agent_templates  # noqa: PLC0415  (lazy: breaks the import cycle)
    gen_agent_templates.generate()
    tmpl_alloc = load_template_alloc()
    for key, _, _, _ in roles:
        if key not in tmpl_alloc:
            continue  # template absent → fall back to the allocation table (tolerance)
        t_model, t_effort = tmpl_alloc[key]
        if t_model != models[key] or t_effort != efforts[key]:
            raise SystemExit(
                f"FATAL: guild template governance/agent-templates/{key}.md declares "
                f"model={t_model}/effort={t_effort} but model-allocation.md says "
                f"model={models[key]}/effort={efforts[key]} — re-run "
                "scripts/gen_agent_templates.py (ADR-0029 G-3)")
        # Compile FROM the template's verbatim values (identical to the SSOT).
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

    # WS-A (ADR-0033 TB-2): compile the overlay `## External tools` grants into the
    # tracked, reviewed allow-list the PreToolUse hook trusts (C1 generate-and-diff).
    allow = write_tool_allowlist()
    print(f"  ✓ board/.tool-allowlist.json ({len(allow)} tool grant(s))")


if __name__ == "__main__":
    main()
