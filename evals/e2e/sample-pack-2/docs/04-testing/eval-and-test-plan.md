# Stage 4 — Testing: eval suite and red-team plan

## Eval suite (automated in CI)
- A labeled ticket set with gold intent, urgency, and target queue.
- Routing accuracy is scored against the set; the CI threshold is 90%.
- A regression check asserts the auto-send count stays exactly zero.

## Integration tests
- End-to-end through the Zendesk stub: ingest, classify, draft, route.
- Redaction test: card numbers and emails never appear in the model-call payload.

## Red-team pass (stricter than org baseline, per the manifest constraint)
- Prompt-injection attempts embedded in ticket bodies must not cause an auto-send
  or exfiltrate redacted data.
- Adversarial tickets that try to force a high-confidence mis-route.

## GATE-4 exit
The eval suite runs in CI with a 90% accuracy threshold and a zero-auto-send
assertion, integration and redaction tests are green, the stricter red-team
findings are closed, and the QA lead signs off.
