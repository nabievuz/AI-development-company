# FIXTURES — `tests/test_check_evidence_gate.py` (DAS-1592)

**These are LABELED FIXTURES, not a real delivery claim.** Every JSON file in
this directory is a synthetic `daslab.delivery_scorecard.v1` payload the test
suite feeds into `scripts/check_evidence_gate.py` — none of it is produced by
the real golden-eval harness (DAS-1591, not yet built) and none of it should
ever be read as evidence that any MUSTAQIL proof delivery actually shipped.

`__RUN_ID__` is a placeholder the test module substitutes at runtime with the
`run_id` of a REAL `wave_runner.run_wave()`-driven attestation written into a
`tmp_path` tree, so the gate is exercised against a byte-faithful committed
attestation + evidence pair, never a hand-typed one (per DAS-1592's "against
LABELED FIXTURES — do not fake a proof" instruction).

| File | Simulates |
|---|---|
| `all_pass.json` | A genuine all-pass delivery — every ED-1 dimension `pass`. |
| `missing_d1.json` | D1 (`aadl_gates_closed`) reported `fail`. |
| `missing_d2_forged.json` | D2 (`merged_pr_green_ci`) claims `pass` against a run whose committed evidence has ZERO counted completions (the cross-artifact corroboration forgery, §2.3). |
| `missing_d3_no_attestation.json` | D3 (`wave_attestation`) — the referenced `run_id` has NO committed wave attestation at all (the missing-artifact case). |
| `missing_d4.json` | D4 (`diagnostics_100`) reported `fail` (e.g. an unclean tree / <100). |
| `missing_d5_skipped.json` | D5 (`golden_eval`) reported `skipped` — proves SKIP is never a pass (ADR-0020). |
| `missing_d6.json` | D6 (`anti_gaming_probe`) reported `fail`. |
| `empty_delivery.json` | An empty/degenerate delivery — `dimensions: []`, scores 0 (every dimension defaults to `skipped`). |
