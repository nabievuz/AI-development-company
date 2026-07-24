# ADR 0041 — Retrieval strategy: agentic-search-first; indexed retrieval is a metric-justified, ADR-approved escape hatch, never the source of truth

- **Status:** Accepted (authored by Backend EM; **CTO ratified — RACI 3.1 A — 2026-07-24**; Security Lead consulted — tool admission on the escape-hatch path)
- **Date:** 2026-07-24
- **Scope:** Platform / org-engine — the default retrieval contract every agent works within
- **Deciders:** Backend EM (author), **CTO (accountable)**; Security Lead (consulted — a future index enters as a tool through the ADR 0033 edge)
- **Relates:** MUSTAQIL v3.0 master prompt `docs/research/2026-07-23-daslab-mustaqil-master-prompt-v3.md` §"RETRIEVAL" (Founder Q11 = agentic-search-first) + Part 0 row 6; converging briefs `docs/research/2026-07-23-daslab-agentic-design-patterns-audit.md` §3.2 and `docs/research/2026-07-23-daslab-production-stack-and-toolkits-mining.md` §3.2 (the "no vector-DB-first" caution); builds on [0033](0033-ecosystem-tool-mcp-bridge.md) (the governed MCP tool edge), [0010](0010-adopt-dgox-graph-orchestrated-control-plane.md) §5 (C1–C6, esp. C2 — the board is canonical), [0008](0008-nonblocking-arcrift-memory-loop.md) (ArcRift recall).
- **Supersedes / Amends:** nothing — makes explicit a stance that was previously silent. Additive; changes no dispatch behaviour and stands up no infrastructure.

> Two independent MUSTAQIL briefs converged on the same finding: a vector DB is the reflexive default of the RAG era, and it is the wrong default for a governed, mostly-modest-repo agent org. This ADR ratifies the Founder's Q11 answer so the default is a **decision on the record**, not an accident — and fixes the exact, narrow conditions under which an index may ever be built.

## Context

DasLab agents already retrieve effectively without a vector store. The working set is reached by **agentic search**: `grep`/ripgrep over the tree, `Read` of the exact files, the per-project `07-CONTEXT-PACK` (the curated context bundle), and **ArcRift `recall_context`** for cross-session memory. The canonical state — `board/tickets/`, the ADRs, the governance SSOTs — is plain files an agent reads directly.

The RAG-era reflex is to stand up a vector DB (embed the repo, retrieve by similarity) before it is needed. For DasLab that reflex is a net negative:

- It introduces an **index that can drift** from the files it mirrors — a second copy of the truth that goes stale between re-index runs, inviting an agent to act on a stale chunk instead of the live file.
- It adds **infrastructure to run, secure, and keep fresh** (embeddings, a store, a sync loop) against a substrate the engine deliberately keeps server-free.
- Similarity retrieval **hides provenance**: a chunk with no path/line is weaker evidence than a `Read` of a named file — and DasLab's whole discipline is evidence over vibes.

At the same time, agentic search has a real ceiling: on a genuinely large repository, grep-and-read can become slow or miss cross-file structure. That is a **measurable** condition, not a matter of taste — and it is the only condition under which an index earns its keep. This ADR draws that line.

## Decision

**Agentic search is the default and only-standing retrieval path. No vector DB or embedding index is stood up by default. An indexed-retrieval mechanism may be built only when a large-repo metric justifies it AND a governing ADR approves it; if built, the index is a governed tool, never the source of truth.** Binding invariants:

### RT-1 — Agentic-search-first is the default retrieval path
Every agent retrieves via `grep`/ripgrep, `Read`, the project `07-CONTEXT-PACK`, and ArcRift `recall_context`. These are the sanctioned default for all roles. No role needs, waits on, or assumes a vector index to do its work.

### RT-2 — No vector DB by default
DasLab does not embed the repo or run a similarity store as part of normal operation. The engine stays server-free (`check_no_dead_runtime` holds); the absence of an index is the intended steady state, not a gap to be filled.

### RT-3 — Indexed retrieval is an escape hatch, gated by BOTH a metric AND an ADR
An indexed-retrieval mechanism (e.g. `claude-context`) is built **only if both** conditions hold: **(a)** a stated **large-repo metric** shows agentic search is inadequate for a real target (e.g. repo size / file count past a threshold, or a measured retrieval-latency / miss-rate on that repo — recorded, not asserted), **and (b)** a governing **ADR** (this one, amended, or a successor) approves it for that scope. Either alone is insufficient: no index without a metric, and no index without an ADR. A "we might want it later" is not a metric.

### RT-4 — The index is NEVER canonical — `board/tickets/` and the repo files stay the source of truth (C2)
If an index is ever built, it is a **derived, disposable accelerator** over the canonical files. `board/tickets/`, the ADRs, and the governance SSOTs remain the single source of truth (ADR 0010 §5 C2). An agent resolves any index/file disagreement in favour of the **file**; the index may point *to* a file but never *replaces* reading it. Deleting the index loses no truth.

### RT-5 — If built, the index enters as a governed tool through the ADR 0033 edge — not as core runtime
An index is admitted exactly like any other external capability: as an out-of-process MCP sidecar wired in `.mcp.json`, under the full ADR 0033 contract — least-privilege per-role allow-list (TB-2), `PreToolUse` audit/deny + ADR 0012 redaction (TB-3), feature-flagged OFF with no dispatch change on merge (TB-5). It is **substrate under DGO-X** (ADR 0010 C1), never part of the engine's core runtime and never the org brain.

## Consequences

**Positive:** The default is now an explicit, sourced decision instead of a silent stance — a future agent will not "helpfully" stand up a vector DB and quietly split the truth. Retrieval keeps full provenance (path + line), the engine keeps zero retrieval infrastructure to run or secure, and the one legitimate reason to index (a measured large-repo ceiling) has a precise, dual-key gate. Reversible by construction: with no index, there is nothing to tear down; with one, deleting the `.mcp.json` entry removes it and loses no truth (RT-4).

**Negative / accepted:** On a very large repo, agentic search can be slower or miss cross-file structure until the RT-3 escape hatch is exercised — accepted, because that cost is bounded, measurable, and the trigger to act on it is built into RT-3. We forgo similarity-search recall by default — accepted, since the canonical corpus is navigable by name/structure and provenance-bearing reads are stronger evidence than opaque chunks.

**Law check:** **C1/C2** (any index is derived substrate under DGO-X; the board and repo files stay canonical — RT-4). **ADR 0033** (an index, if built, enters only through the governed MCP edge — RT-5). **ADR 0012** (index/tool events classified + redacted). **No dead runtime** (the engine stays server-free by default — RT-2). **Evidence over vibes** (RT-3's trigger is a recorded metric, not an assertion). **Project placement** (a per-project `07-CONTEXT-PACK` and any project-scoped index live under `projects/<name>/`, hosting no content outside it — C6).

## Enforcement / acceptance

- **Ratified by the CTO on 2026-07-24** (RACI 3.1 A); Security Lead consulted on the escape-hatch tool-admission path. Verified against Founder Q11 (agentic-search-first, no vector DB by default), the MUSTAQIL v3.0 master-prompt §RETRIEVAL discipline, C2 (board/repo canonical — RT-4), and the ADR 0033 governed-tool edge (RT-5); decision + invariants only, no implementation; 0040 left reserved for the A2A outbound surface. Status moves `Proposed` → `Accepted` on this sign-off.
- A PR that stands up a vector DB / embedding index without **both** a recorded large-repo metric (RT-3a) and an approving ADR (RT-3b) is rejected; one that treats an index as canonical or wires it as core runtime rather than through the ADR 0033 edge is rejected (RT-4, RT-5).
- Any future "how should an agent retrieve?" or "should we add a vector DB?" question resolves to this ADR.
