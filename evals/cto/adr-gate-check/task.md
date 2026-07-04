# Golden task — cto — adr-gate-check

**Role:** `cto`
**Kind:** deterministic

## Prompt

You are the AADL GATE-2/GATE-3 accountable owner (RFC/ADR sign-off — see
`engineering/agents/cto/AGENTS.md` mission). `fixtures/rfcs.json` lists RFCs
awaiting your sign-off, each declaring the AADL gate level it must clear and
the sections its author has written so far.

The required sections per gate level:

- **GATE-2** requires: `problem_statement`, `architecture_diagram`, `risk_analysis`.
- **GATE-3** requires everything GATE-2 requires, PLUS: `security_review`,
  `rollback_plan`.

For each RFC, decide whether it **passes** its declared gate (all required
sections present) and, if not, list exactly which required sections are
**missing**.

## Input

- `fixtures/rfcs.json` — array of `{id, title, gate_level, sections_present}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{
  "results": {
    "<rfc id>": { "pass": true | false, "missing": ["<section>", ...] },
    ...
  }
}
```

## Scoring (deterministic, fractional credit)

The expected `pass` and `missing` set are recomputed per RFC from the gate
requirements above applied to `sections_present` — never spelled out for a
specific RFC in this prompt. Per RFC:

- If your `pass` verdict is wrong, that RFC earns `0.0`.
- If `pass` is correct: when the RFC truly passes (`missing` is empty), you
  earn full credit for that RFC only if you also reported an empty `missing`
  list; when the RFC truly fails, you earn `0.5` for the correct verdict plus
  up to `0.5` scaled by how precisely your `missing` list matches the true
  missing set (true positives minus false positives, normalised by the count
  of truly-missing sections).

Task credit is the mean per-RFC credit. A blank submission (`results` omitted
or empty) scores `0.0`.
