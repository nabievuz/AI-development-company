# WS-E guardrail evals — promptfoo golden-set-before-judge (DAS-1584 / FR-007)

> Behind `ws_e_tenant_hardening` (`config/features.yaml`, DEFAULT OFF). This
> tree adds no new admission path and grants no new tool — it reuses the
> promptfoo sidecar WS-D (DAS-1574) already admitted through the ADR-0033
> governed MCP edge (`tools/mcp_bridges/promptfoo_tool_bridge.py`, granted to
> `qa-eng`/`qa-lead` in `board/.tool-allowlist.json`).

## What lives here

- `runner.py` — `run_golden_set()` / `gate_is_red()` / `run_judge_if_eligible()`.
  Wraps `promptfoo_tool_bridge.run_eval()` (reused, not forked) with the
  **golden-set-before-judge** ordering invariant (ADR-0017/0020): a judge or
  dashboard score may only be consulted after a full golden-set pass, and a
  no-pass is the whole gate — RED, with nothing downstream able to rescue it.
- `golden_set.json` — the hand-labeled golden set (3 cases: PII redaction,
  secret redaction, Tier-M preservation). All-pass by construction.
- `golden_set_with_gaming_probe.json` — the same 3 cases **plus** one
  `anti-gaming-probe` case whose recorded `actual` is a superficially
  plausible ("I redacted it") but factually wrong completion — a stand-in for
  a model that pattern-matches the eval surface instead of doing the work.
  The deterministic `expected_contains` check fails it exactly like any other
  wrong answer, which is what makes the probe catch gaming rather than being
  a special-cased rule.

## How it is wired into the `evals/` CI path

`tests/test_ws_e_promptfoo_golden_evals.py` imports this module and runs both
fixtures. `python3 -m pytest` is already the CI step that collects every test
under `tests/` — a red golden set therefore fails that step, i.e. **is** the
CI wiring. No `ci.yml`/`scripts/` file is touched by this ticket.

## Reuse, not re-admission

This tree performs **no** MCP tool grant and edits neither
`board/.tool-allowlist.json` nor any role overlay. It calls the *existing*
admitted `promptfoo_tool_bridge.run_eval` function exactly as WS-D's own
reference sidecar documents it should be called/extended, in-process, the
same convention the WS-A/WS-D tests (`tests/test_ws_d_tool_admission.py`) use.
