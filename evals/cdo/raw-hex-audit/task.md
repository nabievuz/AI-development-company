# Golden task — cdo — raw-hex-audit

**Role:** `cdo`
**Kind:** deterministic

## Prompt

As CDO you hold final word on tokens, components, and visual language
(`design/CLAUDE.md` §Authority). `fixtures/component_styles.json` is a style
manifest for the core UI kit: each component's fill is either routed through a
design token (`fill.token`) or hard-codes a raw hex value (`fill.hex`). A raw
hex fill bypasses the design-system source of truth — if the brand palette
changes, that component silently drifts out of sync.

List exactly the components whose fill is a **raw hex value** (i.e. NOT
sourced from a token) — these are the components that need remediation before
the next design-system audit.

## Input

- `fixtures/component_styles.json` — `{"components": [{"name": str, "fill": {"token": str} | {"hex": str}}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "raw_hex": ["<component name>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely raw-hex components:

```
credit = clamp01( (|reported ∩ raw_hex| - |reported \ raw_hex|) / |raw_hex| )
```

A blank submission (`raw_hex: []` or omitted) scores `0.0`. The raw-hex set is
derived from the manifest inside `verify.py`; it is never spelled out in the
prompt.
