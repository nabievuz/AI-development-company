# Golden task — ux-researcher — insight-vs-noise

**Role:** `ux-researcher`
**Kind:** deterministic

## Prompt

`fixtures/quotes.json` holds raw quotes captured from moderated usability
sessions, each tagged with the participant who said it and a `topic` label
assigned during transcription.

Separate signal from noise: a quote is an **actionable insight** only if its
`topic` was independently raised by **two or more distinct participants**
(a corroborated, recurring pattern worth acting on). A quote whose `topic` was
raised by only **one** participant is **noise** — an anecdote, off-topic
remark, or personal-taste comment that does not warrant a product change on
its own, no matter how vivid it sounds.

## Input

- `fixtures/quotes.json` — `{"participant_count": int, "quotes": [{"id": str,
  "participant": str, "topic": str, "text": str}, ...]}`.

## Required submission

A JSON object (recorded under `submissions/`) with:

```json
{ "insights": ["<quote id>", ...] }
```

List the ids of every quote that belongs to an actionable (multi-participant)
insight. Omit quotes that are noise.

## Scoring (deterministic, fractional credit)

Credit rewards true positives and penalises false positives, normalised by the
number of genuinely-actionable quotes:

```
credit = clamp01( (|reported ∩ insights| - |reported \ insights|) / |insights| )
```

A blank submission (`insights: []` or omitted) scores `0.0`. The insight set is
derived by counting distinct participants per `topic` in the same fixture the
agent was given — it is never spelled out in the prompt.
