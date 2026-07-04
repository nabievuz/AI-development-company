# ADR 0013 — Effort-tier boundary: per-role effort under a fixed opus floor (max-speed amendment)

- **Status:** Accepted (ratified 2026-06-26 per Founder directive — board-policy amendment approved; authored by Backend EM; **CTO ratify — GATE-2**; implemented via the 4-col `model-allocation.md` table + `gen_subagents.py` patch + 32-agent regen)
- **Date:** 2026-06-22
- **Scope:** Model/effort allocation — `governance/policies/model-allocation.md` +
  `scripts/gen_subagents.py` (all 32 roles)
- **Deciders:** Backend EM (author/MGR), **CTO (accountable)**; Security Lead
  (consulted — opus stays on security-touching work)
- **Relates:** ADR 0007 (model re-tier boundary — the *sibling* axis);
  `governance/policies/model-allocation.md`; `scripts/gen_subagents.py`;
  claude-code#44385 (frontmatter not trusted at dispatch); T7 (quality governor),
  T4 (cheap-share)

## Context

`effort` (Opus 4.5+ / Sonnet 4.5+) controls how many tokens the model spends per
response — text, tool calls, **and** extended thinking. It is a separate axis from
the model: same model, fewer tokens. **Haiku 4.5 does not support `effort`** —
sending it returns `400 "This model does not support the effort parameter."`

**Current state (the problem).** `gen_subagents.py` pins effort by model:

```python
EFFORT_BY_MODEL = {"opus": "max", "sonnet": "max"}
```

So **all 10 opus + 19 sonnet agents run at `effort: max`** — the most thorough,
highest-token, **slowest** setting, *above* the vendor default (`high`). A wave
finishes only when its **slowest** agent finishes (ADR 0007 §Context), so `max`
effort on the IC swarm sets fleet latency for mechanical work too. This — not the
model choice — is the dominant speed lever, and it is currently turned to its slowest
position for the entire fleet.

Lowering effort is **not** a model re-tier: the opus floor (ADR 0007 LAW 3) is
untouched. This ADR records the *effort* boundary as the sibling of ADR 0007's
*model* boundary, because crossing it wrong is a **quality** failure (T7), not a
cost tweak.

## Decision

**Max-speed, per-role effort, within the unchanged opus floor.** Operator directive
(2026-06-22): optimise for speed; accept that a too-aggressive band shows up as an
eval catch and is rolled back (not waived).

1. **Effort becomes a per-role column** in the allocation table and is passed
   **explicitly on every dispatch** alongside `model` (frontmatter is unreliable —
   claude-code#44385). The generator is the source of truth (LAW 3).

2. **Bands (down from the uniform `max`):**
   - **opus roles → `high`.** Gate / architecture / security judgment stays sharp;
     these roles are low-frequency, so holding them at `high` costs ~0 throughput,
     and they are the **safety net** that catches the down-tiered ICs. A single
     unusually deep `cto` / `security-lead` task may be run at `xhigh` for *that
     call* (per-task override) — never as the role default.
   - **sonnet, standard execution → `medium`.** `medium` matches `high` success
     ~92% of the time at ~half the tokens; errors are caught by the opus EM / lead
     gates.
   - **sonnet, mechanical / checklist / templated → `low`.**
   - **haiku → no effort line** (unsupported; omitted as today).

3. **Opus floor unchanged (ADR 0007 §2).** Every AADL gate owner, all architecture/
   ADR work, `cto` and `security-lead` stay **opus**. Effort changes the token
   budget, not the capability tier. A cheaper *tier* still never reviews a security/
   gate item — that guarantee is the opus model, independent of this effort cut.

4. **T7 overrides T4 (rollback, not waiver).** If the fixed eval/gate suite regresses,
   the **rollback-first set** (below) returns to `high` before anything else; effort
   is never lowered past the point evals hold. "Faster" yields to "correct."

5. **Insidious-error floor.** Roles whose wrong output is *not* cheaply gate-caught
   (numeric/analytic, finance, legal, and the safety-executor ICs) floor at `medium`,
   never `low`, even under the max-speed directive.

## Allocation table (drop-in for `model-allocation.md` — adds the `Effort` column)

### Opus — `high` (10)

| Role | Model | Effort | Effort rationale |
|---|---|---|---|
| `cto` | opus | high | Architecture/ADR, GATE-2/3 — `max→high` saves tokens, keeps judgment; `xhigh` per-task for unusually deep design. Opus floor (ADR 0007 §2). |
| `security-lead` | opus | high | Security sign-off gate (GATE-2/4/5); `xhigh` per-task for deep red-team review. Opus floor. |
| `ceo` | opus | high | Strategy/arbitration — low-frequency; down-tiering yields ~0 throughput. |
| `chairman` | opus | high | Governance rulings, binding minutes — rare, judgment-dense. |
| `cpo` | opus | high | GATE-1 scope/KPI — ambiguity multiplies downstream. |
| `senior-pm` | opus | high | PRD authoring (GATE-1 responsible) — ambiguity multiplies downstream. |
| `backend-em` | opus | high | Code review/merge (GATE-3) — the net that catches `medium` backend ICs. |
| `frontend-em` | opus | high | Code review/merge (GATE-3) — the net for `medium` frontend ICs. |
| `qa-lead` | opus | high | GATE-4 eval thresholds / release-blocking — primary regression catch for the aggressive bands. |
| `sre-lead` | opus | high | GATE-5 production launch — prod blast radius. |

### Sonnet — `medium` (13)

| Role | Model | Effort | Effort rationale |
|---|---|---|---|
| `backend-eng-1` | sonnet | medium | Impl tickets — `medium` ≈92% of `high` at ~½ tokens; backend-em (GATE-3) catches. |
| `backend-eng-2` | sonnet | medium | Impl tickets — as above. |
| `frontend-eng-1` | sonnet | medium | Impl tickets — frontend-em (GATE-3) catches. |
| `frontend-eng-2` | sonnet | medium | Impl tickets — as above. |
| `qa-eng` | sonnet | medium | Test authoring / eval runs; qa-lead (GATE-4) gate. **Rollback-first.** |
| `security-eng` | sonnet | medium | Red-team / scans; security-lead review gate. **Rollback-first.** |
| `sre-eng` | sonnet | medium | Runbooks / deploy / monitoring; sre-lead (GATE-5). **Rollback-first.** |
| `design-lead` | sonnet | medium | Design direction / artifact review. |
| `product-designer` | sonnet | medium | Mockups / components / tokens — visually checked. |
| `ux-researcher` | sonnet | medium | Research synthesis — needs reasoning. |
| `product-analyst` | sonnet | medium | Metrics / KPI / goal-drift (GATE-6 responsible) — numeric errors insidious; floor at `medium`. **Rollback-first.** |
| `legal-analyst` | sonnet | medium | Risk-ethics drafting; novel calls escalate via ticket. **Rollback-first.** |
| `finance-analyst` | sonnet | medium | Token/infra budget, burn — numeric, insidious; floor at `medium`. **Rollback-first.** |

### Sonnet — `low` (6)

| Role | Model | Effort | Effort rationale |
|---|---|---|---|
| `content-lead` | sonnet | low | Marketing copy — iterative, cheaply reviewed, low blast radius. |
| `growth-marketer` | sonnet | low | Campaigns / experiments — cheaply reviewed. |
| `cdo` | sonnet | low | Dept coordination docs — checklist-driven. |
| `cmo` | sonnet | low | Dept coordination docs — checklist-driven. |
| `coo` | sonnet | low | GATE-6 accountable but checklist-driven cadence work — raise to `medium` first if GATE-6 pass-rate dips. |
| `board-member` | sonnet | low | Charter-guided reviews / votes — templated. |

### Haiku — no effort line (3)

| Role | Model | Effort | Effort rationale |
|---|---|---|---|
| `seo-specialist` | haiku | — | `effort` unsupported (400 error) — frontmatter omits it; runs as-is. |
| `support-lead` | haiku | — | Unsupported — omitted. |
| `tech-writer` | haiku | — | Unsupported — omitted. |

**Totals:** opus ×10 (all `high`) · sonnet ×19 (13 `medium` + 6 `low`) · haiku ×3
(no effort). = 32.

**Rollback-first set (T7 > T4):** `qa-eng`, `security-eng`, `sre-eng`,
`product-analyst`, `finance-analyst`, `legal-analyst` → `medium → high` before any
other band moves, plus `coo` (`low → medium`) if GATE-6 quality dips.

## Generator patch (`scripts/gen_subagents.py`)

The table migrates from 3-col to 4-col **and** the generator changes **atomically**
(a 3-col row fails the new regex, so they land together).

```python
# Capture role, model, and the optional Effort cell (col 3). Rationale (col 4) ignored.
ROW_RE = re.compile(
    r"^\|\s*`?([a-z0-9-]+)`?\s*\|\s*(opus|sonnet|haiku)\s*\|"
    r"\s*(max|xhigh|high|medium|low)?\s*\|",
    re.M,
)
# Fallback only — an explicit per-role Effort cell wins. Haiku NEVER takes effort.
EFFORT_DEFAULT_BY_MODEL = {"opus": "high", "sonnet": "medium"}

def load_alloc():
    if not MODEL_POLICY.exists():
        raise SystemExit(f"FATAL: {MODEL_POLICY} missing — model allocation is board policy")
    models, efforts = {}, {}
    for role, model, effort in ROW_RE.findall(MODEL_POLICY.read_text()):
        models[role] = model
        efforts[role] = None if model == "haiku" else (effort or EFFORT_DEFAULT_BY_MODEL[model])
    return models, efforts
```

`main()` uses `effort = efforts[key]` in place of `EFFORT_BY_MODEL.get(...)`; the
existing `effort_line = f"\neffort: {effort}" if effort else ""` is unchanged, so
haiku (`None`) still omits the line. Re-run `python3 scripts/gen_subagents.py` until
`git diff` is clean (LAW 3).

> **Interim quick-win (no regex/table edit, ship today):** set
> `EFFORT_BY_MODEL = {"opus": "high", "sonnet": "medium"}`. This alone takes the whole
> fleet `max → high/medium` — the bulk of the speed gain — in one line. The `low` band
> (6 marketing/coordination roles) and any future per-role opus override need the
> column patch above.

## Consequences

**Positive:** the fleet drops from a uniform `max` to `high`/`medium`/`low`; the wave
**bottleneck** (the dev ICs) goes `max → medium`, directly shortening waves and cutting
tokens/$ per action. The opus floor keeps every gate, ADR, and security review at full
capability — **no model capability is traded for speed**.

**Negative / accepted:** the max-speed band invites more eval catches / rollbacks
(operator chose this). Mitigated by opus-`high` gates, the named rollback-first set,
and the T7 governor. The bands are a **judgement** to re-check as a per-effort quality
meter lands; until then the `medium`/`low` calls on insidious-error roles are the
monitored set.

**Law check:** LAW 3 (explicit `model` **and** `effort` per dispatch; `gen_subagents.py`
clean diff; gate/architecture/security stay opus); LAW 2 (a lower-effort agent still
passes a real, distinct-reviewer gate — effort never converts a gate into a
rubber-stamp); T7 governs T4.

## Enforcement / acceptance (hand to a DAS ticket)

- Atomic: 4-col table edit in `model-allocation.md` + `gen_subagents.py` patch +
  `gen_subagents.py` rerun with **clean `git diff`**; record the ADR delta (which roles
  moved and the directive behind it) on the implementing ticket.
- Eval/gate pass-rate on the fixed suite **no worse** than pre-change (T7); every
  effort decision auditable.
- Update `governance/policies/model-allocation.md` precedence note and the weekly
  board minutes (board-policy change → PR + chairman approval).

## References

- Effort parameter — Claude API Docs: https://platform.claude.com/docs/en/build-with-claude/effort
- What's new in Claude Opus 4.8: https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-8
- Migration guide (Sonnet 4.6 effort default `high`): https://platform.claude.com/docs/en/about-claude/models/migration-guide
- Haiku 4.5 has no `effort` parameter (400 error): https://platform.claude.com/docs/en/about-claude/models/overview
