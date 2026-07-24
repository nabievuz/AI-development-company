# Runbook — WS-C: LangGraph/DGO-X execution substrate + per-task sandbox (ADR-0035)

**Goal (MUSTAQIL WS-C):** land the durable LangGraph loop as the DGO-X P2/P3
execution substrate — governed, board-canonical, shadow-before-drive — without
changing dispatch. **This ticket (DAS-1568) ships no runtime code and does not
flip the flag.** Deployment = runbook + confirm `ws_c_langgraph_loop` OFF at
merge + rollback. SRE Lead accountable (GATE-5); Security Lead consulted.

## What ships (from DAS-1564/1565/1567, referenced here — not modified)

| File | Role |
| --- | --- |
| `scripts/dgox/langgraph_loop.py` | Substrate adapter — projects `scripts/dgox/state.py:GraphState` onto LangGraph state channels; `build_graph()`, `langgraph_available()` |
| `scripts/dgox/requirements-langgraph.txt` | Optional extra (`langgraph`, unpinned) — the ADR-0035 import-ban carve-out; kept OUT of core `requirements.txt` |
| `tools/sandbox/` | Per-task sandbox adapter (DAS-1565) — `LocalStubSandbox` (host-free, ships today) and the live `DockerSandbox` (E2B/OpenHands, DAS-1566) |
| `tests/test_ws_c_langgraph_substrate.py`, `tests/test_ws_c_sandbox_adapter.py`, `tests/test_ws_c_langgraph_loop.py` | Substrate, sandbox-stub, and negative/resume suites (GATE-3/GATE-4) |
| `config/features.yaml: ws_c_langgraph_loop` | The feature flag — default **`false`** |

## Deployment posture (AADL Stage 5 / GATE-5, DAS-1568)

**No production deploy happens here.** WS-C ships with `ws_c_langgraph_loop:
false` — the substrate lands in the tree, inert, behind the flag. "Deployment"
for WS-C means *shippable + operable while OFF*, never *live*. Merging this
work changes **no** dispatch behaviour; `/daslab-cycle` remains the fallback
(ADR-0035 LG-5/C5, SPEC-004 FR-007).

## 1. Enable the substrate (documented procedure — NOT executed by this ticket)

LangGraph is sanctioned **only** under `scripts/dgox/` (the ADR-0035 import-ban
carve-out) — it is never imported elsewhere in the engine, and it is deliberately
absent from the core `requirements.txt`.

1. **Install the opt-in extra**, only on a host that will actually drive the
   substrate:
   ```bash
   python3 -m pip install -r scripts/dgox/requirements-langgraph.txt
   ```
   Absent `langgraph` ⇒ `scripts/dgox/langgraph_loop.py:langgraph_available()`
   returns `False` and `build_graph()` raises `SubstrateUnavailableError` — the
   substrate is **unavailable, not broken**. Present ⇒ `build_graph()` compiles
   the DGO-X loop onto a LangGraph `StateGraph`.
2. **Shadow → enforce → drive progression, under board approval at each step**
   (ADR-0035 LG-5, mirrors the `dgox_emit` shadow family, ADR-0019 phase
   discipline):
   - **Shadow:** the graph runs alongside `/daslab-cycle` and mirrors
     `graph_state`/board decisions without acting on them; nothing it produces
     is consumed.
   - **Enforce:** the graph's gate/interrupt decisions are compared against the
     board's actual routing for a supervised window; divergences are logged,
     never auto-applied.
   - **Drive:** the graph actually dispatches worker nodes for a wave. This is
     the autonomous-drive step gated by C5.
   Each step is a separate, explicit board approval — no step is implied by the
   previous one succeeding.
3. **Flip `ws_c_langgraph_loop` ON is a Founder governance act**, only after a
   supervised 0→100 slice (Q4 discovery answer) — a full wave run end-to-end
   under human supervision with a clean checkpoint/attestation trail. It is a
   `security_sensitive` + `governance_or_policy` + `gate5_deployment` change
   (never `approval: auto*`, QONUN-5) in `config/features.yaml`. **This ticket
   does not perform that flip.**

## 2. Stand up the per-task sandbox

Two backends behind the same `tools/sandbox/` adapter contract:

- **`LocalStubSandbox`** — needs **no host**. It ships today, runs in CI, and
  is what the GATE-3/GATE-4 isolation-contract and escape tests
  (`tests/test_ws_c_sandbox_adapter.py`, the SC-005a–d sandbox-escape suite in
  `tests/test_ws_c_langgraph_loop.py`) already run against. Use it for shadow
  and enforce windows — no live execution risk.
- **`DockerSandbox` (E2B/OpenHands)** — the **live** backend. It requires a
  real in-tenant Docker/E2B host on the tenant VM (Founder discovery Q2: one
  Linux VM). **This is DAS-1566, currently `blocked`** — an external
  dependency (no live sandbox host / VM provisioning available to a planning
  or authoring agent). Provisioning it requires, at minimum:
  - a dedicated in-tenant Linux VM (not the orchestrator's own host);
  - the Docker/E2B (or OpenHands) runtime installed and reachable from that VM;
  - the optional `tools/sandbox/requirements-sandbox.txt` extra installed
    **only on that VM** (absent-by-default everywhere else, same opt-in
    pattern as `scripts/dgox/requirements-langgraph.txt`);
  - network/egress policy for the sandbox matching the ADR-0038 tenant
    hardening (no unscoped route to the host, the repo, other tasks, or
    credentials).
  Once provisioned, **the isolation contract + escape tests are not
  rewritten** — the same `LocalStubSandbox`-validated refusal decisions
  (host / repo / other-task / unscoped-credential unreachable) re-run
  **unchanged** against the live `DockerSandbox`, per the DAS-1567 §7 SC-005
  design note. A live isolation smoke on the real host is DAS-1566's own
  acceptance criterion, not this ticket's.

## 3. Invariants at go-live (ADR-0035 LG-1…LG-4, judged, not re-litigated here)

- **Board stays canonical.** `board/tickets/*.md` is the sole source of truth;
  `graph_state` is its mirror; LangGraph state is an execution *projection* of
  `graph_state`. LangGraph is never the top-level dispatcher.
- **Gates halt for the Founder.** Every AADL predecessor gate is a conditional
  edge; security/release/budget and every never-auto-approve category are
  `interrupt()` points that halt and wait — a GATE-5-open deployment stays
  machine-blocked. No worker node is ever routed past an open gate.
- **Checkpoint never a tiebreaker.** Checkpoints reconcile with the ADR-0023
  run-model and the ADR-0031/0032 attestation + wave-ledger through
  `run_wave`; they never fork a second durable truth, and any divergence
  between the LangGraph projection and the board resolves **to the board**,
  never to the checkpoint.
- **Worker write-scope stays structurally impossible to violate.** A worker
  node edits only its ticket body/log + artifacts; `assignee`/`reviewer`/
  `routing_reason`/`confidence` stay supervisor-only (LG-3/C3).
- **The 4 sandbox walls fail-closed.** Host reach, repo reach, cross-task
  reach, and unscoped-credential/egress reach are all unreachable from inside
  the sandbox by default (fail-closed, not fail-open) — proven against the
  stub in GATE-3/GATE-4 and re-proven unchanged against the live backend once
  DAS-1566 unblocks.

## 4. Rollback

Two independent, additive levers — either alone fully reverts to pre-merge
(no-live-drive) behaviour:

1. **Flip `ws_c_langgraph_loop` OFF** in `config/features.yaml` (already the
   default at merge) — the substrate goes inert; `build_graph()` is never
   called, `/daslab-cycle` dispatch is unaffected and byte-identical to
   pre-merge.
2. **Leave the opt-in extra uninstalled** — with `langgraph` absent,
   `langgraph_available()` is `False` and any attempt to compile the graph
   raises `SubstrateUnavailableError` (**unavailable, not broken**), a second,
   structural layer under the flag: even a misconfigured flag can't drive a
   substrate that isn't importable. The sandbox backend stays absent-by-default
   the same way (`tools/sandbox/requirements-sandbox.txt` uninstalled ⇒ no live
   `DockerSandbox`).

Either lever is sufficient; there is no ordering dependency between them, and
they compose for defense in depth during an incident.

## Verify quickly

```bash
python3 scripts/board_lint.py
python3 scripts/diagnostics.py
python3 scripts/check_import_ban.py
python3 -m pytest tests/test_ws_c_langgraph_substrate.py -k "flag_off or inert or unavailable" -q
```

## Definition of Done (WS-C deploy, DAS-1568)

- Runbook complete: enable-for-shadow procedure, sandbox-host provisioning
  pointer (DAS-1566), checkpoint/attestation invariants, and rollback steps.
- `ws_c_langgraph_loop: false` confirmed in `config/features.yaml` at merge —
  a flag-off wave is byte-identical to pre-merge (no dispatch code path reads
  the flag except inside `scripts/dgox/langgraph_loop.py`, which no
  `/daslab-cycle` import touches).
- Rollback proven: flag OFF and/or extra uninstalled both independently leave
  the substrate inert / unavailable-not-broken.
- `diagnostics.py` 100/100; `board_lint.py` and `check_import_ban.py` green.
</content>
