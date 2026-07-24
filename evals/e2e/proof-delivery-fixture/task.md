# Task — score a proof DELIVERY against the six ED-1 dimensions

You are handed a proof **delivery** (a `projects/<proof>/`-shaped deliverable). Score it
against the six ED-1 completion-contract dimensions and emit the machine-readable
`DeliveryScorecard`. Each dimension is a DETERMINISTIC verifier over a REAL committed
artifact — never a prose claim:

1. `aadl_gates_closed` — all six AADL gates closed on the proof stage-board.
2. `merged_pr_green_ci` — a merged PR + green CI (R-9 counted completion) per ticket.
3. `wave_attestation` — a committed, hash-chained wave attestation whose mechanics fired.
4. `diagnostics_100` — diagnostics `<int>/<int>` on a clean tree.
5. `golden_eval` — the delivery's own golden score clears the release bar.
6. `anti_gaming_probe` — the delivery's own suite turns RED when the implementation is
   gutted (SWE-bench-style mutation).

The verdict is CONJUNCTIVE: `complete` iff EVERY dimension is `pass`. An unmeasured
dimension is `skipped`, and `skipped` NEVER counts green (ADR-0020).

Your submission is your CLAIMED per-dimension verdict, e.g.
`{"dimensions": {"aadl_gates_closed": "<pass|fail|skipped>", ...}}`. Credit is earned
only for a claim that matches the deterministic result over the committed artifacts.
