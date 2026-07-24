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
