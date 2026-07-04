# Golden task — product-designer — usability-heuristics

**Role:** `product-designer`
**Kind:** deterministic

## Prompt

`fixtures/screen_audit.json` is a factual audit of one screen (booleans only —
no judgement calls). Using Nielsen's usability heuristics, identify which
heuristics this screen **violates**, applying this fixed mapping:

| Audit field | Violating value | Heuristic violated |
|---|---|---|
| `has_confirmation_on_destructive_action` | `false` | `error_prevention` |
| `shows_loading_indicator` | `false` | `visibility_of_system_status` |
| `error_messages_generic` | `true` | `help_users_recognize_diagnose_recover` |
| `consistent_button_placement` | `false` | `consistency_and_standards` |

Report exactly the heuristic codes whose violating value matches this screen's
audit — no more, no fewer.

## Input

- `fixtures/screen_audit.json` — `{"screen": str, "has_confirmation_on_destructive_action": bool, "shows_loading_indicator": bool, "error_messages_generic": bool, "consistent_button_placement": bool}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "violations": ["<heuristic code>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuine violations:

```
credit = clamp01( (|reported ∩ violations| - |reported \ violations|) / |violations| )
```

A blank submission (`violations: []` or omitted) scores `0.0`. Which fields
actually trigger a violation for THIS screen is derived by `verify.py` from the
fixture, never spelled out directly in the prompt.
