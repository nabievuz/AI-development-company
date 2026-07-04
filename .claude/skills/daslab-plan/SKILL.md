---
name: daslab-plan
description: Decompose a goal into DasLab board tickets (epics + PR-sized tickets with owners per RACI). Use when the user states a new goal, project, or batch of work for the org. Args - the goal text.
---

# DasLab plan — approved goal → board tickets

You play the CEO/CPO decomposition role. Input: the goal in args (if empty,
ask for it). Output: ticket files on the board — you do NOT dispatch work
(that's /daslab-cycle).

## Steps

1. Read `board/README.md` (schema), `governance/policies/raci.md` (ownership),
   `governance/policies/ai-agent-lifecycle.md` (AADL — binding for AI-agent
   goals), `docs/02-ORG.md` (roster), `docs/03-PROJECTS.md`.

   **Pick the target board first (QONUN — Project Placement Law).** Decide whether
   the goal is **project** work (any product / client / app / website / agent /
   SaaS / campaign) or **platform** (org-engine) work on DasLab itself:
   - **Project goal →** tickets are written to that project's OWN board,
     `projects/<slug>/board-tickets/` (each project keeps its own board), never to
     the org `board/tickets/`, and they carry `project: <slug>`. Scan that project's
     `board-tickets/*.md` for the next id.
   - **Platform goal →** tickets are written to the org `board/tickets/` and carry
     NO `project:` field. Scan `board/tickets/*.md` (+ `board/archive/`) for the
     next id.

   Either way, next id = max existing DAS-number on the target board + 1 (start at
   DAS-1001 on an empty board); scan the target board so you extend rather than
   duplicate.

2. **Founder Discovery Gate for new projects.** If args describe a new product,
   client project, app, website, agent, SaaS, campaign, or any goal whose
   `projects/<slug>/APPROVED-GOAL-QUEUE.md` does not yet exist, STOP normal
   decomposition and run intake first:
   - Ask the Founder at least 10 concise discovery questions before creating
     tickets. Cover: target user, core problem, must-have outcome, non-goals,
     business model, success metrics, deadline, budget, existing assets, brand,
     integrations, compliance/legal constraints, deployment/domain, support
     expectations, and risk tolerance.
   - If answers are missing in a non-interactive run, output the questions and
     stop. Do not guess and do not create tickets.
   - After answers, do current global research with cited sources: market and
     competitor scan, user expectations, technical options, regulatory/compliance
     considerations, SEO/channel signals when relevant, pricing/unit economics
     when relevant, and key risks. Prefer primary sources for legal/regulatory,
     vendor, platform, pricing, and API facts. If web/research tools are
     unavailable, say the gate cannot close yet.
   - Create the project folder first, then write the research and queue only
     inside it, per the project placement law:
     `projects/<slug>/APPROVED-GOAL-QUEUE.md` plus supporting planning notes
     under `projects/<slug>/docs/01-planning/`.
   - The queue file must include: founder answers summary, research snapshot
     date, source links, assumptions, explicit non-goals, and a prioritized
     table with `order`, `goal_slug`, `outcome`, `why_now`, `research_basis`,
     `owner`, `status`, and `ticket_refs`. Status values:
     `candidate`, `founder_approved`, `planned`, `active`, `done`, `blocked`,
     `rejected`.
   - Present the queue to the Founder and wait for explicit approval
     (`APPROVED:` / `TASDIQLANDI:` or an equally clear approval). Until then,
     no board tickets may be created.

3. **Approved queue only.** If an approved queue exists, decompose only the next
   `founder_approved` queue item, or the specific approved item named by the
   Founder. Never plan from `candidate`, `rejected`, or unapproved text. When
   tickets are created, update the queue item to `planned` and add the ticket
   refs.

4. Decompose per the hierarchy `Goal → Epic → Ticket` (AGENTS.md §3):
   - **AI-agent goal? AADL is mandatory:** exactly one epic per lifecycle
     stage (1-Planning, 2-Design, 3-Development, 4-Testing, 5-Deployment,
     6-Maintenance), titled `<project> — Stage N: <name>`, epic acceptance
     criteria = that stage's GATE checklist from the policy, accountable role
     per the policy §1 table. Child tickets carry their stage epic as
     `parent`. Also create one Stage-1 ticket to bootstrap
     `projects/<name>/` with the policy §2 skeleton + README stage board.
   - one epic per major track, `status: backlog`, assigned to the owning
     lead/manager role;
   - PR-sized child tickets (`parent:` = epic id) with concrete acceptance
     criteria, `status: todo`, `assignee:` = the IC role per RACI — or empty
     if genuinely ambiguous (the cycle triage will route it);
   - `author:` = `ceo`; `goal:` = a kebab-case slug of the goal.

5. Write each ticket exactly per the schema in `board/README.md`, to the **target
   board chosen in step 1** (`projects/<slug>/board-tickets/` for project work,
   `board/tickets/` for platform work), with a `## Log` entry noting it was created
   by /daslab-plan.

6. Report: the epic/ticket tree (ids + titles + assignees), total count, and
   the suggested first wave (`/daslab-cycle`).

## Rules

- New project intake is not optional. Founder questions + global research +
  explicit approval happen before board ticket creation.
- Project-specific discovery, research, queues, **and tickets** live only under
  `projects/<slug>/` (tickets in `projects/<slug>/board-tickets/`). Never write a
  project ticket into the org `board/tickets/` — that board is DasLab-platform
  (org-engine) only, and a ticket there must carry no `project:` field
  (`scripts/board_lint.py` R9).
- Every ticket independently workable by ONE role in one-few sessions; split
  anything bigger.
- No orphans: every ticket carries `parent` (epics excepted) and `goal`.
- Clarify before guessing (ADR-0014): when a queue item under-specifies a
  ticket's scope, write an inline `[NEEDS CLARIFICATION: <precise question>]`
  marker (as plain prose in the Description, max 3 per ticket) instead of
  silently guessing — resolve it from the existing Founder discovery answers.
  More than 3 markers means the ticket is too big: decompose it. A ticket that
  still carries a marker is held by the /daslab-cycle Definition-of-Ready gate,
  not dispatched.
- Spec layer, size-gated (ADR-0015): for a goal that decomposes to **≥ ~15 tickets
  OR any AI-agent goal**, first write a per-epic `SPEC.md` from
  `docs/specs/templates/SPEC.md` (User Scenarios / `FR-NNN` / `SC-NNN`, WHAT/WHY only)
  at `docs/specs/<NNN>-<slug>/` (org-engine) or `projects/<slug>/specs/<NNN>-<feat>/`
  (project), then emit child tickets carrying `spec: <NNN-slug>` + `implements: [FR-…]`.
  Smaller goals skip the SPEC entirely. `scripts/check_spec_consistency.py` checks any
  SPEC that exists; it never forces one.
- Don't assign external-dependency work (RAHMAT/UZINFOCOM/tax/legal) to
  agents — create the ticket, mark `status: blocked`, log the dependency.
