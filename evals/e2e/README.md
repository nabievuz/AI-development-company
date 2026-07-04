# evals/e2e — WS7 gateway end-to-end sample packs

This directory holds two real [PROJECT-OS packs](../../docs/specs/PROJECT-OS-PACK.md)
and the e2e test that compiles them through the WS7 gateway
(`scripts/gateway_compile.py`). It is the GATE-4 Testing validation (DAS-1495,
ORGANISM WS7) for the gateway machinery.

## The two packs

| Pack | Slug | Domain | Stack | Goals | Compiled tickets |
|---|---|---|---|---|---|
| [`sample-pack/`](sample-pack/) | `acme-tasks` | Non-AI CRUD task SaaS with auth + Slack | Python / React / Postgres | 4 | 28 |
| [`sample-pack-2/`](sample-pack-2/) | `helpdesk-triage` | AI support-ticket triage assistant + Zendesk | TypeScript / Anthropic / Redis | 5 | 35 |

The two packs are deliberately different in domain, language, budget shape,
autonomy posture, and goal count. Both are validated and compiled by the **same**
`scripts/gateway_compile.py` with **no code changes** — that is the generality
claim (SPEC FR-010 / SC-003).

## What is proven here (and what is not)

**Proven — the compile + validation.** Given a Founder-approved pack, the gateway:

1. validates the manifest, doc tree, placeholders, and links;
2. confirms the discovery gate (>= 10 Q&A or a waiver);
3. emits the research-enrichment step into the project folder;
4. verifies the Founder approval signal via the wired
   `scripts/check_approved_goal_queue.py`; and
5. compiles **coherent, self-contained, stage-gated story tickets** onto the
   project's own board — with **zero hand-written tickets**. Each compiled ticket
   carries embedded mission context, acceptance criteria, produces/consumes edges,
   its AADL stage, and a gate reference, and the whole board is `board_lint`-clean.

`tests/test_e2e_sample_pack.py` runs both packs into a **tmp/scratch** project dir
(never the org `board/tickets/`) and asserts: at least 25 tickets, every ticket
self-contained, and the board lint-clean.

**Not proven here — the full 0->100 delivery.** Actually *executing* those
compiled tickets — writing the code, passing each of the six AADL gates
(Planning -> Design -> Development -> Testing -> Deployment -> Maintenance), and
shipping a running, deployable artifact — is a much larger, multi-wave operation
carried out by the org's role agents behind the gate order in
[`governance/policies/ai-agent-lifecycle.md`](../../governance/policies/ai-agent-lifecycle.md).
This e2e proves the **intake compiler**: that a pack becomes an executable,
coherent board. The 0->100 delivery is the **scaled operation the gateway
enables**, not something this test performs. Documenting that boundary honestly is
part of the deliverable.

## Reproduce locally

```
python3 -m pytest tests/test_e2e_sample_pack.py -q
# or drive the compiler directly against a copy of a pack in a scratch dir:
#   cp -r evals/e2e/sample-pack /tmp/acme-tasks
#   python3 scripts/gateway_compile.py /tmp/acme-tasks
```

Compiling a pack writes a `board-tickets/` dir inside the pack root, so the test
always copies each pack into a tmp dir first and never mutates the committed pack
or the org board.
