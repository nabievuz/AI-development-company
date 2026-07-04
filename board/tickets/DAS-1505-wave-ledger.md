---
id: DAS-1505
title: Co-produce a committed hash-chained wave-ledger in run_wave
status: done
assignee: cto
author: ceo
dept: engineering
priority: p1
parent: DAS-1503
goal: organism-ws9-harness
depends_on: [DAS-1504]
zone: wave-runner
created: 2026-07-04
updated: 2026-07-04
---

## Description

GATE-3 (P22, ADR-0032). Extend `scripts/wave_runner.py` so that `run_wave`
ATOMICALLY appends a committed, hash-chained entry to
`board/wave-ledger.jsonl` (TRACKED) alongside the attestation it already
writes. Each ledger entry carries:
`{run_id, wave, ticket_ids, attestation_path, attestation_hash (sha256 of the
committed attestation file), prev_hash, self_hash, created_at}`.

The ledger chain is doubly-linked like the attestation chain: the self-hash
excludes itself, and the prev-hash links the previous ledger entry (genesis
sentinel for the first entry). Reuse `wave_runner`'s existing hashing / genesis
helpers — do NOT re-implement them. The ledger write is load-bearing: it has
the SAME failure semantics as the attestation write — it RAISES on failure and
is never silently swallowed.

Regenerate the committed sample via `scripts/gen_sample_attestation.py` so
`board/wave-ledger.jsonl` gains the matching sample entry, and keep it TRACKED
and in sync with the sample attestation.

**Why:** the ATTEST re-audit residual (P22) requires a tamper-evident,
committed record of every dispatched wave that is chain-linked to its
attestation, closing the final HARNESS-phase audit gap in the ORGANISM program.

**Extend, do not create new.** This extends the existing `run_wave` path in
`scripts/wave_runner.py`; no new module. Only `board/wave-ledger.jsonl` (the
tracked ledger + sample entry) is a new artifact.

**Key files + paths:**
- `scripts/wave_runner.py` — `run_wave`; add the atomic ledger append.
- `scripts/gen_sample_attestation.py` — regenerate the committed sample entry.
- `scripts/check_attestation.py` — chain/hash semantics of record.
- `board/wave-ledger.jsonl` — NEW tracked ledger (+ sample entry).
- `tests/test_wave_runner.py` — end-to-end tests.
- `docs/adr/0032-harness-forced-attestation.md` — governing ADR.

## Acceptance criteria

- [ ] `run_wave` co-produces a committed hash-chained `board/wave-ledger.jsonl`
  entry atomic with each attestation.
- [ ] Ledger entry carries `attestation_hash` + `prev_hash`/`self_hash` chain
  (self-hash excludes self; genesis sentinel for the first entry).
- [ ] Ledger write reuses existing hashing/genesis helpers and RAISES on
  failure (same semantics as the attestation write).
- [ ] Sample regenerated via `gen_sample_attestation`, tracked, and in sync
  with the sample attestation.
- [ ] `organism_emit=False` writes NO ledger entry (byte-clean no-op;
  flag-on == flag-off preserved).
- [ ] End-to-end tests: single-wave run writes BOTH attestation + a
  chain-linked ledger entry; a two-wave run produces two chain-linked ledger
  entries whose hashes match the committed attestations.
- [ ] Full suite 0 failed, diagnostics 100/100.

Produces: `wave-ledger` (consumed by DAS-1506).

Constraints: org-engine ticket, NO `project:` field.

## Log

### 2026-07-04 — CEO
Created from ORGANISM HARNESS-phase decomposition (/daslab-plan, audit-closure
final phase). Spec-of-record: `docs/research/ORGANISM-PROGRAM-PLAN.md` + the
ATTEST re-audit residual.
READ: `scripts/wave_runner.py`, `scripts/check_attestation.py`,
`scripts/gen_sample_attestation.py`, `tests/test_wave_runner.py`,
`docs/adr/0032-harness-forced-attestation.md`.

### 2026-07-04 — Backend EM
Implemented the ADR-0032 §1 wave-ledger co-write. Branch
`feat/das-1505-wave-ledger`, local commit `98fc0cc` (LOCAL-ONLY — no push/PR).

**Schema + chain.** Each `run_wave` (when `organism_emit=True`) now appends one
line to the TRACKED `board/wave-ledger.jsonl` carrying exactly the eight fields
`{run_id, wave, ticket_ids, attestation_path, attestation_hash, prev_hash,
self_hash, created_at}`. `attestation_hash` = SHA-256 of the committed
attestation FILE's exact bytes (binds the ledger line to the precise receipt).
The ledger is a SECOND, independent doubly-linked chain: `self_hash` excludes
itself (self-exclusion preimage, ADR-0023 §2 convention); `prev_hash` links the
previous ledger line across the whole file (genesis sentinel `sha256:0×64` for
the first line). `ticket_ids` is sorted and equals the attestation's `tickets`.

**Reuse, not re-implement.** New `append_wave_ledger_entry()` +
`_ledger_self_hash` / `_ledger_chain_tip` reuse `wave_runner`'s canonical hashing
(`_sha256`, factored onto a new `_sha256_bytes` byte primitive) and the existing
`_GENESIS_PREV_HASH`. `LEDGER_PATH` / `LEDGER_FIELDS` are the single SSOT for the
reconciliation validator (DAS-1506). Renamed the internal progress-ledger local
to `progress_ledger_path` to avoid colliding with the new `ledger_path` param.

**Atomicity + RAISE-on-failure.** The ledger append is step (7), executed right
after the attestation file is written and equally LOAD-BEARING — it raises on any
I/O failure (never swallowed), so the attestation and its ledger line are one
atomic unit: both produced, or `run_wave` raises. The line is serialised once and
written in a single append (never partial).

**Sample regeneration.** `gen_sample_attestation.py` co-produces the committed
sample ledger entry (genesis line of the chain) via a throwaway temp ledger then
materialises `board/wave-ledger.jsonl` deterministically (idempotent — no blind
append duplication); `--check` now covers the ledger too. Verified the sample
entry's `attestation_hash` == SHA-256 of the committed sample attestation file
(`8c52…`). The sample attestation + evidence bytes are unchanged.

**flag-on == flag-off proof.** `organism_emit=False` returns `None` before any
write, so NO ledger line is produced — asserted by
`test_organism_emit_off_is_a_byte_clean_noop` (now also asserts the ledger file
does not exist). The AST shadow-rule property test still passes (the ledger read
is `read_text`, not an event-store read primitive, and touches no `.events.jsonl`
literal).

**Hermeticity.** Every non-sample `run_wave` caller (`kill_drill`,
`test_wave_runner`, `test_check_attestation`) now passes a tmp/work-dir-local
`ledger_path` so no test or drill writes the real committed ledger.

**VERIFY (all green):** `pytest -q` → 1688 passed, 1 skipped; `diagnostics.py` →
100/100; `board_lint.py` → 0 violations; `check_attestation.py` → exit 0 on the
regenerated sample; `gen_sample_attestation.py --check` → clean; `ruff check
scripts tests` → clean. `board/wave-ledger.jsonl` confirmed NOT gitignored
(`git check-ignore` exit 1).

→ Handing to CTO (GATE-3 review). Produces `wave-ledger`, consumed by DAS-1506
(`check_wave_reconciliation`), which will reuse `LEDGER_PATH` / `LEDGER_FIELDS`
and recompute `attestation_hash` from the committed attestation file bytes.

### 2026-07-04 — Orchestrator (/daslab-cycle collect)
Done via local-only done-gate: full suite 1688; run_wave co-produces a committed hash-chained board/wave-ledger.jsonl entry (8 fields, second independent chain, attestation_hash=sha256 of committed attestation file) atomic with the attestation + RAISES on failure; sample regenerated in-sync; organism_emit=False = no ledger (flag-on==flag-off).
