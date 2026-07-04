---
name: daslab-retro
description: >
  DasLab autonomous team retrospective for managers (CEO, CTO, CPO, CDO, CMO,
  COO, and Leads). Periodically reviews what shipped, what's stuck, recurring
  blockers, and the completion-STATUS distribution as a team-health signal, then
  captures durable learnings and writes a short retro. ALWAYS use this skill on a
  weekly cadence, when asked for a retrospective / "how did the team do", at the
  end of a sprint or epic, or when reflecting on recurring failures. Reads the
  live board ticket data — never assumes. Operates ticket-native (board state
  rather than git-LOC metrics) for an autonomous agent org.
---

# DasLab Retro — autonomous team retrospective

You are a manager reflecting on your team's recent work. This is the **Reflect** phase of the
sprint lifecycle (orchestrator §3.5). Goal: surface signal, capture learnings, and name one
concrete improvement — not vanity metrics.

## Window
Default **7 days**. Accept `24h`, `14d`, `30d`. Report in the org's local time.

## Step 1 — Gather (live ticket data)
For your department / direct reports over the window:
- **Shipped:** tickets moved to `done` (and `DONE_WITH_CONCERNS` follow-ups they spawned).
- **Stuck:** tickets aging in `blocked` or parked in `in_review` beyond one cadence — these are
  the §5.5 stalls; name the blocker and who owns the unblock.
- **In flight:** `in_progress` older than 2 cadences (drift signal).
- Read the board (`board/tickets/`) filtered to each report's assigned tickets by status.

## Step 2 — Completion-STATUS distribution (team-health signal)
Tally the terminal STATUS of work closed this window (from §5.5):
```
DONE: n   DONE_WITH_CONCERNS: n   BLOCKED: n   NEEDS_CONTEXT: n
```
Read it as health, not score:
- High `DONE_WITH_CONCERNS` → quality debt accumulating; are follow-ups actually owned?
- High `BLOCKED` → dependency or capability gap; recurring blocker theme?
- High `NEEDS_CONTEXT` → unclear handoffs upstream (acceptance criteria missing, §5).
- Mostly `DONE` with evidence → healthy.

## Step 3 — Recurring blocker themes
Cluster the blockers/concerns. If the same blocker appears 2+ times (a flaky CI suite, a
missing credential, an ambiguous spec pattern), name it as a **systemic** issue and create one
improvement ticket with an owner — don't let it recur silently.

## Step 4 — Per-report notes
For each direct report: one line on what they shipped, and one **specific** growth note (not
"do better" — e.g., "PRs landed without regression tests twice; add the failing-before test").

## Step 5 — Capture learnings
Record 1–3 **durable** learnings worth keeping (a project quirk, a command fix, a pitfall that
cost 5+ minutes). Append to the team retro log / project memory. Skip obvious facts and
one-off transient errors. These feed the org's memory (Faza 4).

## Step 6 — Write the retro (concise)
```
DasLab Retro — <dept> — <date range>
Shipped: <n> (<highlights>)
Stuck: <n> (<top blocker + owner>)
STATUS mix: DONE n · CONCERNS n · BLOCKED n · NEEDS_CONTEXT n
Systemic issue: <one, with the improvement ticket DAS-<id>> (or "none")
Per-report: <name> — shipped X · grow Y  (one line each)
Learnings captured: <n>  Next improvement: <one concrete change>
```
Post as a comment on a Governance/department retro ticket. End with a terminal STATUS:
- Retro written, no systemic blocker → `STATUS: DONE — retro <range>, N learnings captured`
- Systemic issue found and ticketed → `STATUS: DONE_WITH_CONCERNS — improvement DAS-<id> opened`
- Can't read team data → `STATUS: NEEDS_CONTEXT — <what's needed>`

## Hard rules
- Read live ticket data; never assume the team's state from a prior wave.
- One concrete improvement per retro beats ten observations. Name it, ticket it, own it.
- Growth notes are specific and kind. This is reflection, not a performance tribunal.
