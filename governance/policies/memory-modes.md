# Policy: Memory modes (full vs memory-optional)

> **Status:** Binding board policy — precedence level 2 (root `AGENTS.md` §2).
> **Scope:** How QONUN 4 (ArcRift persistent memory) degrades when the memory
> layer is absent, so a bare clone boots zero-touch.

QONUN 4 mandates `recall_context` at the start and `store_memory` at the end of
every unit of work. That is **full mode**. But a fresh clone on a new machine — or
CI — may not yet have the optional memory services. DasLab still boots and runs.

## Full mode (default when the memory layer is present)

`scripts/doctor.py` OPTIONAL checks pass:
- **ArcRift MCP** reachable (`.mcp.json` names ArcRift; its server file exists).
- **Ollama** running with `nomic-embed-text` (embeddings).

QONUN 4 applies in full: agents `recall_context` → work → `store_memory`.

## Memory-optional mode (degraded — first boot / CI / bare machine)

When `doctor.py` REQUIRED checks pass but the OPTIONAL memory checks do not, the
org runs in **memory-optional mode**:

- The org **boots and executes normally** — board, agents, gates, validators, and
  `/daslab-cycle` are all file-based and need no memory layer.
- `recall_context` / `store_memory` become **best-effort**: an agent that cannot
  reach ArcRift logs a one-line `memory: degraded (ArcRift unavailable)` warning
  and proceeds, rather than blocking. No cross-session memory is persisted until
  the layer is provisioned.
- `scripts/doctor.py` exits **0** (REQUIRED pass) and prints OPTIONAL checks as
  **WARN**; `scripts/bootstrap.py` prints the exact provisioning commands.

## Provisioning to full mode

```bash
# Embeddings (Ollama):
ollama pull nomic-embed-text
# ArcRift backend (persistent memory):  see ~/ArcRift setup; then ensure
# .mcp.json's ArcRift server path resolves (it uses ${HOME}).
python3 scripts/doctor.py            # OPTIONAL checks should now PASS → full mode
```

CI runs in memory-optional mode by design (no ArcRift/Ollama on the runners); the
portability job asserts `doctor.py` exits 0 there.
