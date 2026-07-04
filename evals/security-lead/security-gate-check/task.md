# Golden task — security-lead — security-gate-check

**Role:** `security-lead`
**Kind:** deterministic

## Prompt

You are the security sign-off owner for the AADL gate chain (GATE-2 threat-model
review, GATE-4 red-team/eval sign-off, GATE-5 deploy sign-off — see
`.claude/agents/security-lead.md` mission: "Guardrails/OWASP sign-off, red-team
risk acceptance (GATE-2/4/5)"). `fixtures/reviews.json` lists RFCs awaiting your
sign-off, each declaring the gate level it must clear and the evidence sections
its author has already produced (`evidence_present`).

The required evidence sections per gate level are cumulative:

- **GATE-2** requires: `data_flow_diagram`, `trust_boundaries`, `mitigations`.
- **GATE-4** requires everything GATE-2 requires, PLUS: `redteam_report`,
  `risk_acceptance_log`.
- **GATE-5** requires everything GATE-4 requires, PLUS: `pen_test_results`,
  `secrets_scan_clean`.

For each RFC, decide whether it **passes** its declared gate (every required
section is present in `evidence_present`) and, if not, list exactly which
required sections are **missing**.

## Input

- `fixtures/reviews.json` — array of `{id, title, gate_level, evidence_present}`.

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

The expected `pass` verdict and `missing` set are recomputed per RFC from the
gate requirements above applied to `evidence_present` — never spelled out for
a specific RFC in this prompt. Per RFC:

- If your `pass` verdict is wrong, that RFC earns `0.0`.
- If `pass` is correct: when the RFC truly passes (`missing` is empty), you
  earn full credit for that RFC only if you also reported an empty `missing`
  list; when the RFC truly fails, you earn `0.5` for the correct verdict plus
  up to `0.5` scaled by how precisely your `missing` list matches the true
  missing set (true positives minus false positives, normalised by the count
  of truly-missing sections).

Task credit is the mean per-RFC credit. A blank submission (`results` omitted
or empty) scores `0.0`.
