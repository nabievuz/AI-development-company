# Runbook — WS-A: browser + tool reach via the governed MCP edge (ADR-0033)

**Goal (MUSTAQIL WS-A):** give DasLab roles a browser and the LangChain tool catalog **through the governed MCP edge** — reach goes up, governance does not go down.

## What ships

| File | Role |
| --- | --- |
| `tools/mcp_bridges/mcp.snippet.json` | `.mcp.json` entries to MERGE: `playwright` (consume the ready Playwright MCP server) + `langchain-tools` (the FastMCP sidecar) |
| `tools/mcp_bridges/langchain_tool_bridge.py` | Out-of-process FastMCP sidecar (TB-1). Ships a stdlib `web_fetch` demo tool; swap the backend for any LangChain-catalog tool in production |
| `tools/mcp_bridges/audit_external_tool.py` | `PreToolUse` governance hook (TB-2/TB-3): allow-list per role + append-only audit; **deny-all by default** |
| `tools/mcp_bridges/requirements-tools.txt` | Optional deps (`mcp`, Playwright via `npx`), kept OUT of core `requirements.txt` |
| `tests/test_ws_a_tool_bridge.py` | Unit tests for the hook decision + the sidecar backend |

## Wire-up

1. **Merge** the two servers from `mcp.snippet.json` into the repo-root `.mcp.json` (`mcpServers` object), alongside `ArcRift`/`obsidian`. Do not replace the file.
2. **Deps:** `pip install -r tools/mcp_bridges/requirements-tools.txt`; the browser needs Node (`npx @playwright/mcp` auto-installs on first run).
3. **Register the hook** in `.claude/settings.json`:
   ```json
   { "hooks": { "PreToolUse": [ { "matcher": "mcp__.*",
       "hooks": [ { "type": "command", "command": "python3 tools/mcp_bridges/audit_external_tool.py" } ] } ] } }
   ```
4. **Allow-list** (least privilege, TB-2). Point `$DASLAB_TOOL_ALLOWLIST` at a JSON file, e.g.:
   ```json
   { "mcp__playwright": ["qa-lead", "design-ic"], "mcp__langchain-tools": ["research-ic", "qa-lead"] }
   ```
   Any role not listed for a tool is **denied** and the attempt is audited to `$DASLAB_TOOL_AUDIT_LOG` (default `board/.tool-audit.jsonl`).

## Governance (why this is safe — ADR-0033)

- **TB-1** the bridges are out-of-process sidecars; the engine stays server-free.
- **TB-2** no global grants — a tool reaches only allow-listed roles.
- **TB-3** every external-tool call is audited; transcripts are redactable (ADR-0012).
- **TB-4** the browser is high-blast-radius: treat all fetched content as **untrusted** input (prompt-injection risk — cf. the Jules exfiltration findings), keep `--isolated`, and constrain egress at the tenant boundary (ADR-0038 TN-5).
- **TB-5** off by default: absent the `.mcp.json` entries + allowlist, nothing changes.

## Definition of Done (WS-A)

- The two servers merge cleanly; `mcp.snippet.json` is valid JSON.
- `pytest tests/test_ws_a_tool_bridge.py` is green (hook allow/deny + sidecar backend).
- A demo: an allow-listed role (e.g. `qa-lead`) opens a live page via `mcp__playwright__*` and reports its rendered title/text; a non-listed role is denied and the denial is in the audit log.
- `ruff check` clean; `check_no_hardcoded_paths` green (all paths are env/relative).

## Verify quickly

```bash
pip install -r tools/mcp_bridges/requirements-tools.txt
python3 -m pytest tests/test_ws_a_tool_bridge.py -q
python3 -c "import sys; sys.path.insert(0,'tools/mcp_bridges'); \
import langchain_tool_bridge as b; print(b.web_fetch('https://example.com')[:80])"
```

## Deployment (AADL Stage 5 / GATE-5, DAS-1550)

**No production deploy happens here.** WS-A ships with `ws_a_tool_bridge: false`
(`config/features.yaml`) — the bridge lands in the tree, inert, behind the flag.
"Deployment" for WS-A means *shippable + operable while OFF*, never *live*.
Flipping the flag ON is a later, explicit Founder act — out of scope for this ticket.

### How to enable the flag for a specific role (NOT done by this ticket)

Two independent gates must both open before a role can actually reach a tool —
flipping the feature flag alone grants nothing:

1. **Grant the role reach** — add an `## External tools` block to that role's
   overlay (`<dept>/agents/<role>/AGENTS.md`), e.g.:
   ```yaml
   ## External tools
   external_tools:
     - server: mcp__langchain-tools
       tools: ["*"]        # or a named tool list, never a literal role wildcard
   ```
   Then recompile the tracked grant map: `python3 scripts/gen_subagents.py` —
   this regenerates `board/.tool-allowlist.json` from the overlay SSOT (TB-2:
   no server-wide "any-role" value is ever emitted, only the explicit role list
   that declared the grant).
2. **Flip the flag ON** — either globally via `config/features.yaml`
   (`ws_a_tool_bridge: true`, a `security_sensitive` + `governance_or_policy`
   change, never `approval: auto*`, QONUN-5), or scoped to one shell/session via
   `DASLAB_WS_A_FLAG=on` (read first, overrides the file — useful for a
   narrow shadow test without touching the tracked config).

With the flag ON but a role absent from the compiled allow-list, every call from
that role is still denied and audited (TB-2 deny-by-default holds regardless of
flag state).

### How to add a domain to the egress allow-list

Edit `config/egress-allowlist.yaml` — add the host under the relevant named
`profiles.<name>` list (label-boundary match, C6; no bare substring match):
```yaml
profiles:
  research-read:
    - "*.wikipedia.org"
    - api.crossref.org
    - export.arxiv.org
    - newdomain.example.com   # <- new entry
```
This file is TRACKED and its own change is `security_sensitive` +
`governance_or_policy` (never `approval: auto*`, QONUN-5) — the set of approved
destinations is a reviewed governance surface, not a config a role can self-serve.
A host that resolves to loopback / link-local / RFC-1918 (169.254.169.254,
127.0.0.1, 10.0.0.0/8, IPv6-mapped/ULA equivalents) is blocked at resolve time
regardless of allow-list membership (C5) unless the profile names that exact
host verbatim and the change is reviewed as an explicit, narrow SSRF exception.
Never widen `browser-deny-all` in place — add a new, narrowly scoped profile
instead (see the file's own header comment).

### How to read the audit log

Every external-tool call attempt (allowed or denied) is appended as one JSON
line to `$DASLAB_TOOL_AUDIT_LOG` (default `board/.tool-audit.jsonl`), written by
`tools/mcp_bridges/audit_external_tool.py`. Read it with:
```bash
tail -n 20 board/.tool-audit.jsonl | python3 -m json.tool --json-lines 2>/dev/null \
  || tail -n 20 board/.tool-audit.jsonl
# filter to denials only:
grep '"decision": "deny"' board/.tool-audit.jsonl | tail -n 20
# filter to one role:
grep '"role": "research-ic"' board/.tool-audit.jsonl | tail -n 20
```
Each line carries at least `decision` (`allow`/`deny`), `role`, `tool`, a
redacted+truncated `reason` (280 chars, `redaction.redact_then_truncate` —
ADR-0012), and a timestamp. The log is append-only; treat it as evidence, never
edit it in place.

### Rollback

Two independent, additive levers — either alone fully reverts to pre-merge
behaviour, and they can be applied together for defense in depth:

1. **Remove the sidecar entries from `.mcp.json`** — delete the `langchain-tools`
   and `browser` objects from the `mcpServers` map (leave `obsidian` / `ArcRift`
   untouched). With the entries gone, the tool servers do not exist from Claude
   Code's point of view — there is nothing to call, allow-list or deny.
   This is the **primary, structural rollback**: absence = the tool doesn't exist.
2. **Flip the flag OFF** (already the default) — `ws_a_tool_bridge: false` in
   `config/features.yaml`, or unset `DASLAB_WS_A_FLAG`. With the flag OFF the
   `PreToolUse` hook is fully inert and passes every call through unchanged
   (TB-5) — this is a software-only kill switch that doesn't require touching
   `.mcp.json`, useful when the sidecar processes should stay registered but
   dormant (e.g. mid-incident, fastest possible revert).

Either lever is sufficient; there is no ordering dependency between them.

### TB-5 deploy evidence — flag OFF ⇒ byte-identical dispatch

At merge, `ws_a_tool_bridge: false` in `config/features.yaml` (confirmed — no
override in the environment). The hook's `_flag_on()` fails safe to OFF on an
absent/unreadable config too, so a broken config can never silently turn
governance ON. Evidence this is a true no-op, not just an unread flag:
```bash
python3 -m pytest tests/test_ws_a_tool_bridge.py -k flag_off -q
```
covers `test_c3_flag_off_is_inert` and the stronger DAS-1549 addition
`test_sc003_flag_off_no_op_even_for_a_would_be_denied_tool` (flag OFF passes
through even a call that WOULD be denied if the flag were ON) — both pass. No
`/daslab-cycle` dispatch code path reads `ws_a_tool_bridge`; the flag is consumed
only inside `tools/mcp_bridges/audit_external_tool.py`, a file no dispatch
import touches, so a wave's dispatch trace is unchanged whether the file exists
or not.

### Sidecar absent-by-default

`mcp` (the FastMCP dependency `tools/mcp_bridges/langchain_tool_bridge.py`
needs) is deliberately **not** in the core `requirements.txt` — it lives only in
`tools/mcp_bridges/requirements-tools.txt`, an optional extra a role must
explicitly `pip install` to use the sidecar. A default DasLab checkout therefore
has no `mcp` package installed, so even if `.mcp.json` still names the server,
attempting to run it fails to import rather than silently doing something — a
second layer under the primary `.mcp.json`-removal rollback. `pytest`'s own
`-k flag_off` run above passes with `mcp` absent (2 pre-existing skips elsewhere
in the suite confirm this — "mcp absent, expected").
