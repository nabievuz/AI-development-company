# experiments/ — GATE-6 evidence records

Every optimization/tuning change must pre-register a **GATE-6 evidence record**
here before it may apply. This closes "silent tuning": no
parameter drifts without a complete, auditable record.

## Record path & shape

- One file per record: `GATE6-YYYYMMDD-NNNN.yaml`.
- Copy `GATE6-TEMPLATE.yaml` and fill every field. The template itself is a blank
  shape — `check_gate6_record.py` ignores any file whose name contains `TEMPLATE`.
- A record is **complete** only with all of: `hypothesis`, `baseline_metrics`,
  `proposed_change` (+ `config_diff_hash`, `blast_radius`), `guardrails`,
  `evidence`, `approval`, `rollout`, `result` — and `guardrails.max_quality_drop`
  **must be 0** (T7 is the immutable hard constraint).

## How it ties to the event store

- The DGO-X event store is `board/.events.jsonl` — **gitignored runtime state**
  (ADR-0003 / ADR 0011). It is never committed; a fresh checkout has none, which
  `check_gate6_record.py` treats as "no tuning yet → clean".
- A tuning event carries `change_type` (one of the enumerated `TUNING_CHANGE_TYPES`)
  and `gate6_id`. The validator requires a record here whose `gate_6_record.id`
  equals that `gate6_id`. Spelling matters: event field `gate6_id` ↔ record
  `gate_6_record.id`.
- The event store is reused rather than replaced. Safety/optimization events (`break_glass_activation`, `break_glass_review`,
  `gate6_tuning`) coexist with the DGO-X `routing_decision` / `agent_invocation`
  lines as additional JSONL records; each reader filters by its own fields.

## Validator

`scripts/check_gate6_record.py --events board/.events.jsonl --experiments experiments`
— exit 0 clean, exit 1 on a missing/incomplete record or a non-zero
`max_quality_drop`. Wired into CI. The loop stays OFF in P1 (`config/loop.yaml`),
so records here are authored by humans, not by an auto-tuning controller.

