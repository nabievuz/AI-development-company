# ADR 0006 — Static cache-prefix layout + invalidation rule

- **Status:** Proposed (authored by Backend EM; **CTO ratifies — GATE-2 / RACI 3.1 A**)
- **Date:** 2026-06-19
- **Scope:** Platform / prompt assembly
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead (consulted — secret hygiene)
- **Relates:** ADR 0005 (worktree), 0008 (memory), 0009 (transport limit)

## Context

Every dispatched agent re-sends a large, mostly-identical **system preamble** (the
documented ~27 KB stable prologue: role overlay + charters + board rules + QONUN laws).
Re-sending it per call drives both **latency** and **input-token cost**.

**Verified evidence (figures to *use*, with their honest caveats):**

- Anthropic **prompt-cache reads bill at ~10% of base input price** → roughly a **90%
  input-cost reduction on the cached portion**.
- The widely-cited **~79% latency reduction** is the **100k-token-prefix benchmark case** —
  it is *not* a universal number; our ~27 KB preamble is far smaller, so the latency win
  is **real but proportionally smaller**. We adopt the *mechanism* and will **measure the
  actual delta on our own corpus** — we do **not** ship "79%" as a
  guarantee.
- **A single early-prefix token busts the whole downstream cache** — any dynamic content
  (timestamp, run id, ticket text) placed before a breakpoint invalidates everything after
  it. This is the load-bearing failure mode.
- **Opus 4.8 minimum cacheable prefix = 1024 tokens** — a prefix shorter than that is not
  cached at all, so the breakpoint must sit *after* ≥1024 tokens of stable content.

These figures are verified Anthropic prompt-caching behaviour, not the un-peer-reviewed
preprint numbers; we cite them as adoptable, with the latency caveat above.

## Decision

**One shared, STATIC system prefix with explicit `cache_control` breakpoints; ALL dynamic
content moves strictly AFTER the last breakpoint.** Cache correctness is enforced by CI,
not by discipline.

1. **Static prefix = the stable preamble only.** The cached region contains exactly the
   content that is identical across agents/waves/time: QONUN laws, AADL gate model, board
   schema, dept charter, the role overlay's invariant text. It is **byte-stable** — no
   timestamp, no run id, no ticket id, no wave counter, no per-agent string anywhere inside
   it.
2. **`cache_control` breakpoint placement.** A `cache_control: {type: "ephemeral"}`
   breakpoint is set at the **end of the static prefix**, which must contain **≥ 1024
   tokens** (Opus 4.8 minimum) for the cache to engage. **TTL is set explicitly** (default
   5-minute ephemeral; the longer TTL is a measured, ADR-tracked choice if adopted) — never
   left implicit.
3. **Everything dynamic goes after the last breakpoint, in this order:** global ticket
   summary → per-phase summary → the specific ticket text → last-N scratchpad → run
   id/timestamp/wave counter. The dynamic tail is where ADR 0008's prewarmed recall output
   and the bounded STATUS summaries live — they are dynamic by nature
   and therefore **must** sit after the breakpoint.
4. **The invalidation rule (the load-bearing contract):**
   > *No byte before a `cache_control` breakpoint may vary across dispatches.* Any change
   > to the static prefix is a **deliberate, reviewed cache-version bump**, never an
   > accidental edit, because it invalidates the cache fleet-wide and re-pays full input
   > cost on the next call for every agent.
5. **CI linter enforces it (prevents silent cache-busting).** A CI check (`check_cache_prefix.py`)
   **fails the build if the byte-content of the cached prefix changes**
   without an accompanying version bump, and fails if any dynamic marker (a known set:
   ISO timestamps, run-id pattern, ticket-id pattern, wave counter) appears **before** the
   last breakpoint. This makes "a stray early-prefix token busts the cache" a **red CI**,
   not a silent latency/cost regression discovered weeks later.
6. **Secret hygiene (Security Lead, consulted).** Secrets, credentials, tokens, and PII
   **never** enter the cached prefix (it is long-lived and shared) and never enter a log.
   The linter's dynamic-marker denylist is extended with a secret-shaped pattern check;
   secret material that must reach a model travels in the dynamic tail of a single call,
   never the shared cache.

## Consequences

**Positive:** the ~27 KB shared preamble is paid for once per TTL window and read at ~10%
input cost thereafter — a real per-action cost cut; a measurable latency reduction on
context-dominated calls, proven on our corpus rather than asserted from the 100k benchmark;
the linter turns the cache-bust failure mode into a build gate.

**Negative / accepted:** the static/dynamic split is a **discipline the linter must
police forever** — without it, normal edits to charters/overlays silently bust the cache.
The latency win is **smaller than the headline 79%** because our prefix is far smaller than
100k tokens; we state the *measured* number, not the benchmark number. A short prefix
(< 1024 tokens) caches nothing — so trimming the preamble too aggressively can *lose* the
cache; the linter's minimum-length check guards this.

**Law check:** LAW 1 (prompt-assembly code under engine zones); LAW 3 (caching is
model-identity-neutral — it does not change which model serves a role); security invariant
(no secret in a cached prefix or log — spec §ENTERPRISE GOVERNANCE). No new transport;
consistent with ADR 0009.

## Enforcement / acceptance

- Single shared static prefix with `cache_control` breakpoint after ≥1024 stable tokens;
  all dynamic content after the last breakpoint; explicit TTL.
- `check_cache_prefix.py` in CI: fails on (a) cached-prefix byte change without version
  bump, (b) any dynamic/secret marker before the last breakpoint, (c) cached prefix < 1024
  tokens.
- Measured latency/cost delta on a fixed call corpus reported at GATE-4/GATE-6,
  annotated ACHIEVED / CAPPED-by-X — **never** the 100k-benchmark figure presented as ours.
