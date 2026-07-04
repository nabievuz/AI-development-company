# Golden task — chairman — adr-ratify-gate

**Role:** `chairman`
**Kind:** deterministic

## Prompt

A draft ADR has been submitted for your ratification sign-off
(`fixtures/adr_draft.md`). Per the repo's binding ADR convention (every ratified
ADR under `docs/adr/` — see e.g. `docs/adr/0001-status-handoff-protocol.md` —
carries exactly three mandatory `##` sections: **Context**, **Decision**,
**Consequences**), audit the draft and report which of those three mandatory
sections are **missing**. A draft with a missing mandatory section is not
ready to ratify — it must go back to its author before it can be accepted.

## Input

- `fixtures/adr_draft.md` — the draft ADR under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "missing_sections": ["<missing-section>", "..."]
}
```

Use the exact section names (`"Context"`, `"Decision"`, `"Consequences"`) —
only the ones that are absent from the draft's `##` headings. The list may
contain zero, one, two, or all three names, in any order.

## Scoring (deterministic, fractional credit)

- credit = `(hits - false_positives) / |required missing set|`, clamped to
  `[0, 1]`. The required missing set is derived from the mandatory
  `{Context, Decision, Consequences}` triple minus whichever `##` headings
  actually appear in `fixtures/adr_draft.md`.

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
