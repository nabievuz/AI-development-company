# Recovery drill evidence — PASS

One REAL interrupted run (SIGKILL mid-wave-2) resumed with zero loss through the production `wave_runner.run_wave` path, plus a time-travel fork drill proving the base run byte-identical (R1 durable execution).

- generated_at: `2026-07-04T10:03:49Z`
- kill-drill run_id: `01KWP9B6D238YJ2NWKH4BWKMHK`
- killed (real SIGKILL mid-wave-2): **True**
- zero_lost: **True** · zero_duplicated: **True**
- resumed attestation chain clean: **True** · wave-ledger reconciles: **True**
- resumed tickets: `['DAS-8004', 'DAS-8005', 'DAS-8006', 'DAS-8007']`
- fork drill: divergent=**True** · original_intact=**True**
- **overall verdict: PASS**

The drill trees (events / checkpoints / attestations / wave-ledger) are hermetic and discarded; this run-summary is the durable, git-tracked receipt.

```json
{
  "generated_at": "2026-07-04T10:03:49Z",
  "kind": "recovery_drill_evidence",
  "source": "scripts/kill_drill.py run_kill_drill + run_fork_drill (production wave_runner.run_wave path)",
  "kill_drill": {
    "run_id": "01KWP9B6D238YJ2NWKH4BWKMHK",
    "wave_run_ids": [
      "01KWP9B6D26XTSGX1V75QNR6NK",
      "01KWP9B6D2WAF7NBZA53X59TXG",
      "01KWP9B6D238YJ2NWKH4BWKMHK"
    ],
    "killed": true,
    "zero_lost": true,
    "zero_duplicated": true,
    "chain_clean": true,
    "ledger_reconciles": true,
    "resumed": [
      "DAS-8004",
      "DAS-8005",
      "DAS-8006",
      "DAS-8007"
    ],
    "ok": true
  },
  "fork_drill": {
    "base_run": "01KWP9B6G58E44XZMXE5EFEYKE",
    "fork_run": "01KWP9B6G8RWGJHXAZQHZB63TC",
    "divergent": true,
    "original_intact": true,
    "chain_clean": true,
    "ok": true
  },
  "overall_ok": true
}
```
