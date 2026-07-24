# `proof-delivery-fixture/` — a LABELED WS-G delivery fixture (DAS-1591)

> **This is a FIXTURE, not a real proof.** It exists to build and CI-check the WS-G
> delivery-scorecard rails **offline**, with no tenant VM and no live 0→100 run. It
> **cannot** self-certify as a shipped proof — by construction it yields
> `verdict: incomplete` (see below). The real proof project (the WS-H control-plane
> dashboard slice, Founder Q1) is bootstrapped later under `projects/<proof-name>/`
> (DAS-1593), runs its own six AADL gates, and is deployed to the VM by DAS-1595
> (genuinely infra-gated). Do NOT read this fixture as a delivered proof.

## What this scores

`agent_eval.score_delivery()` (the WS-G extension of the golden-eval harness, ADR-0029
extend-vs-new) scores a delivery against the six ED-1 completion-contract dimensions
(ADR-0037 ED-1), each a **deterministic verifier over a committed artifact**:

| # | Dimension | Committed artifact | Fixture status |
|---|---|---|---|
| D1 | `aadl_gates_closed` | `fixtures/stage-board.md` | **pass** |
| D2 | `merged_pr_green_ci` | `fixtures/counted-tickets.json` | **skipped** (absent — a fixture has no real merged PR) |
| D3 | `wave_attestation` | `fixtures/wave-attestation.json` | **skipped** (absent — no real committed attestation for a counted run) |
| D4 | `diagnostics_100` | `fixtures/diagnostics.json` | **skipped** (absent — no real clean-tree diagnostics run) |
| D5 | `golden_eval` | `fixtures/golden-eval.json` | **pass** |
| D6 | `anti_gaming_probe` | `fixtures/impl.py` + `fixtures/test_impl.py` | **pass** (the suite turns RED under mutation) |

Three dimensions are **honestly `skipped`** because a labeled fixture genuinely lacks
those real-run artifacts. Per ADR-0020 (`skipped` never counts green) and the
CONJUNCTIVE verdict (`complete` iff all six `pass`), the fixture is **`incomplete`** —
exactly the design's point: the machinery **cannot round an unmeasured dimension up to
green**. The all-pass path (the only `complete`) is exercised in
`tests/test_ws_g_delivery_scorecard.py` with a constructed complete delivery in a tmp
dir (never a committed all-green fixture that could be mistaken for a real proof).

## The anti-gaming (D6) probe — SWE-bench-style

`fixtures/impl.py` is a real implementation; `fixtures/test_impl.py` genuinely exercises
it. The probe **guts** the implementation (every body → `return None`) and re-runs the
delivery's own suite: a real suite turns **RED** (pass the probe); a suite that stays
**GREEN** against the gutted implementation is gaming (`assert True` / hard-coded /
all-skipped) and **fails** the probe. The gaming case is asserted in the test file.

## Reproduce

```
python3 scripts/agent_eval.py --delivery evals/e2e/proof-delivery-fixture --json
# (ws_g_proof is OFF by default → the scorecard is inert; the test suite passes
#  enabled=True to score the fixture and asserts verdict == "incomplete".)
python3 -m pytest tests/test_ws_g_delivery_scorecard.py -q
```
