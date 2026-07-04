# Golden task — board-member — adr-signoff-check

**Role:** `board-member`
**Kind:** deterministic

## Prompt

`fixtures/adr_draft.md` is a draft ADR up for board sign-off.
`fixtures/rules.json` gives the gate it must clear:

- `required_sections` — every `## <Section>` heading the ADR must contain.
- `kind` — this ADR's decision kind (drives which roles must sign off), per the
  Governance Charter Decision Rules (e.g. a `strategy` decision needs both
  Chairman AND Board Member sign-off).
- `signoff_requirements` — the roles required to have signed off, per kind.

The draft's `## Signoff` section (if present) lists lines like
`- <role>: approved`. A role only counts as signed off if its line says
`approved` (any other status, or no line at all, means that role has not
signed off).

Determine:
1. Which `required_sections` are **missing** from the draft (by heading text).
2. Which roles required for this ADR's `kind` have **not** signed off as
   `approved`.
3. Whether the ADR **passes** the gate — true only when both lists are empty.

## Input

- `fixtures/adr_draft.md` — the draft ADR.
- `fixtures/rules.json` — the gate rules.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "pass": <bool>,
  "missing_sections": [<string>, ...],
  "missing_signoffs": [<string>, ...]
}
```

## Scoring (deterministic, fractional credit)

Three equally-weighted components (each worth 1/3):
- `pass` matches the fixture-derived boolean.
- `missing_sections` matches the expected set exactly (order-independent).
- `missing_signoffs` matches the expected set exactly (order-independent).

A blank submission scores `0.0`. The answer key lives only in `verify.py`.
