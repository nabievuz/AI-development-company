# Golden task — legal-analyst — regulatory-flag-scan

**Role:** `legal-analyst`
**Kind:** deterministic

## Prompt

Review the draft privacy policy in `fixtures/privacy-policy.md` against the
standard data-protection disclosure checklist below (modeled on
GDPR-style regulatory expectations). List exactly the disclosure IDs that are
**missing** — not substantively addressed anywhere in the draft.

### Standard disclosure checklist

| disclosure ID | what it covers |
|---|---|
| `legal_basis` | the legal basis relied on for processing personal data |
| `right_to_access` | the data subject's right to request a copy of their data |
| `right_to_erasure` | the data subject's right to request deletion of their data |
| `consent_withdrawal` | how a data subject can withdraw previously given consent |
| `breach_notification_72h` | commitment to notify of a data breach (e.g. within 72 hours) |
| `dpo_contact` | contact details for a Data Protection Officer |
| `retention_period` | how long personal data is retained |
| `cross_border_transfer` | disclosure of international/cross-border data transfers |

## Input

- `fixtures/privacy-policy.md` — the draft policy under review.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "missing_disclosures": ["<disclosure ID>", ...] }
```

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by
the number of genuinely-missing disclosures:

```
credit = clamp01( (|reported ∩ missing| - |reported \ missing|) / |missing| )
```

A blank submission (`missing_disclosures: []` or omitted) scores `0.0`. Which
disclosures are actually missing is determined by reading
`fixtures/privacy-policy.md`; it is never spelled out in this prompt.
