# `daslab_sdk` — WS-B headless Agent SDK runner

The thin, feature-flagged wrapper over the Claude **Agent SDK**
`query(prompt, options)` that lets DasLab dispatch a ticket/wave **headlessly**
(no interactive session), additive to `/daslab-cycle`.

- **ADR:** [`docs/adr/0034-agent-sdk-headless-runner.md`](../docs/adr/0034-agent-sdk-headless-runner.md) (SR-1…SR-5)
- **Design:** [`docs/design/ws-b-agent-sdk-runner.md`](../docs/design/ws-b-agent-sdk-runner.md)
- **Spec:** `docs/specs/003-mustaqil-ws-b-runner/SPEC.md` (FR-001…FR-008)
- **Flag:** `ws_b_agent_sdk_runner` in `config/features.yaml` — **default OFF**.

## What it does (and does not)

| Invariant | Behaviour |
|---|---|
| **SR-1** load repo's own agents | Every dispatch pins `cwd` = repo root + `setting_sources=["project"]`, loading the repo's `.claude/agents`, skills, `CLAUDE.md`, hooks, `.mcp.json` VERBATIM. **No** ported-agent constructor exists — a role that is not a generated shim is unreachable. |
| **SR-2/SR-3** no mechanical decision | Requires an explicit `model` (fail-closed); routes every dispatch through an **injected** admission gateway (built by DAS-1556) — the runner picks no model/role/order. Wave execution is delegated to the one seam, `scripts/wave_runner.py:run_wave` (new caller, not a re-impl / second producer). |
| **SR-4** board / Git law | Records no routing field; **never merges a PR** — a dispatch advances a ticket toward its reviewer only. |
| **SR-5** flag + isolation | Flag OFF ⇒ fully inert. The Agent SDK is an **opt-in extra** (`requirements-sdk.txt`), not a core dependency — absent ⇒ *unavailable*, not broken. The child `env` is constructed (never an `os.environ` passthrough) and drops metered-key vars so the subscription OAuth profile resolves. |

## Flag-OFF behaviour — a documented no-op

With `ws_b_agent_sdk_runner` **OFF** (the default):

- `dispatch_ticket(...)` returns `TicketDispatchResult(status=INERT_FLAG_OFF)` —
  it imports no SDK, reads no board, and calls no admission gateway or model.
- `dispatch_wave(...)` returns `WaveDispatchResult(status=INERT_FLAG_OFF)` —
  it never calls `run_wave`.

Interactive `/daslab-cycle` waves are therefore **byte-identical to pre-merge**;
merging this package changes no interactive-wave behaviour (SR-5 / SC-003).

## Absent SDK — unavailable, not broken

With the flag ON but the Agent SDK not installed, `dispatch_ticket(...)` returns
`status=UNAVAILABLE_NO_SDK` (a clean result, not a crash). Install the extra only
where the headless runner runs (a DAS-1558 deployment step):

```
pip install -r daslab_sdk/requirements-sdk.txt
```

## Live dispatch is bound on DAS-1558

No live model call is made from this package in tests or CI — the SDK boundary is
injectable (`query_fn`) and the SDK is not a core dependency. Flipping the flag ON
is a **Founder-only** act gated on the DAS-1558 flip-time precondition
(re-verify the live plan's Agent-SDK terms / monthly credit). DAS-1556 wires the
concrete admission gateway (model + SI-5 budget + Claude-account auth).
