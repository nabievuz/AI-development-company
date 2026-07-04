---
name: daslab-cycle
description: Run ONE DasLab work wave — triage the file-based board, dispatch every actionable role subagent in parallel (no policy cap; harness-bounded), collect results, report. Use when the user says to run the org, work the board, or process tickets. Args - optional integer N (cap the wave to N if you want a smaller batch).
---

# DasLab cycle — one wave over the board

You are the DasLab orchestrator. One invocation = ONE operator-invoked
wave. The runtime has no night driver, background loop, or timer chain.

**Wave size:** **no policy cap** — dispatch every actionable ticket the
selection step finds, in one parallel batch. Real concurrency is bounded only
by the Claude Code harness (it queues excess subagents and runs them as slots
free). `N` from args is an optional *upper bound* if you deliberately want a
smaller wave (e.g. a quick test run); omit it to run the whole board.
(Owner removed the hard cap on 2026-06-14: Max-plan usage was barely moving,
so the 10-cap and the opus wave-mix guard were pure throttle. Thermal limit
was already lifted.) The only remaining bounds are **correctness guards** in
the selection step — keep those.

## Steps

0. **ArcRift memory prewarm — one recall per wave (ADR 0008, W7).**
   Issue ONE `recall_context` call before any subagent is spawned, with:
   - `project` = `"daslab"` for org-level waves; `"daslab-<slug>"` for
     project-specific waves. **Never mix projects** — a wave spanning multiple
     projects prewarms per-project, injecting only the matching context into
     each project's agents (LAW 4 strict project scoping).
   - `prompt` = a compact wave-intent sentence (e.g. "wave for DAS-13xx platform
     tickets") — no ticket IDs, no timestamps (those go in the dynamic tail).

   The returned `<ARCRIFT_retrieved_context>` block is carried as a single
   read-once payload into the **dynamic tail** of each agent's prompt (slot 4:
   "Last-N scratchpad / ArcRift recall" — after the last `cache_control`
   breakpoint, never in the stable prefix). This collapses N blocking per-agent
   recalls into 1 prewarmed wave-level read.

   **Durable outbox for store_memory (fire-and-forget, LAW 4):** Each agent
   enqueues its close-of-task `store_memory` payload to a durable local outbox
   (append-only file at `board/.arcrift-outbox.jsonl`, never committed — in
   `.gitignore`) before reporting done. The agent does NOT wait for the MCP
   call to complete. A single background drainer — the orchestrator, after step 6
   collect — reads the outbox and issues `store_memory` calls one at a time
   (single-drainer prevents the known concurrency race). On transient failure
   the drainer retries with exponential backoff until the store lands; it never
   silently drops a pending entry. On orchestrator shutdown, the drainer flushes
   the remaining outbox before exit (or leaves it durable for replay on next start).
   **Zero stores are ever dropped.** Project scoping is per-entry: each outbox
   record carries its own `project` key; the drainer passes that key verbatim —
   never merges across projects.

   **Run-model wave lifecycle — ONE deterministic call at collect (ORGANISM WS8
   ATTEST, ADR-0031; feature-gated `organism_emit`, default OFF).** The wave's
   entire run-model lifecycle — the wave-open/-close checkpoints, the
   `run_start`/`run_end`/`span` emission per dispatch, the per-role guardrail
   tripwires, the progress-/task-ledgers + per-ticket completions, the committed
   redacted evidence snapshot, and the committed hash-chained attestation — is NO
   LONGER a multi-step prose sequence the orchestrator interprets. It is performed
   by a SINGLE deterministic call, `scripts/wave_runner.run_wave(plan, results)`,
   issued ONCE at collect (step 6). Gate it on the `organism_emit` flag in
   `config/features.yaml`, read via `python3 scripts/feature_flags.py`
   (`feature_flags.enabled("organism_emit")`) and passed as `run_wave`'s
   `organism_emit=` argument. It is a SEPARATE channel from the step-5d
   `dgox_emit` shadow — do NOT conflate the two flags, and do NOT disturb
   `dgox_emit`. It defaults OFF; when OFF `run_wave` is a no-op (returns `None`,
   writes nothing) so dispatch DECISIONS are byte-identical to the flag-on path
   (same tickets selected, routed, dispatched, and reported). When ON:
   - The `run_id` join key is a lexicographically-sortable ULID minted ONCE at
     collect (step 6) with `pulse_checkpoint.generate_ulid()`. Hold it in
     run-local memory for this single invocation only; it is volatile and lives
     in the dynamic tail, NEVER in this stable prefix (ADR 0006).
   - One operator invocation = one wave = one run. The run is opened AND CLOSED
     inside the single step-6 `run_wave` call; it starts NO daemon, loop, or
     timer. The "one invocation = one wave, no background timer" contract is
     unchanged — the run-model only adds durable state for resume/replay, never
     a driver.
   - Steps 4 and 5f only CAPTURE the plan and per-dispatch data as DATA for that
     one call; they write no checkpoint or event themselves.
   - **Failure isolation at the call boundary:** the single step-6 `run_wave`
     call is wrapped so any exception is caught and logged in the wave-log/report;
     the wave proceeds unconditionally. A failed call NEVER blocks dispatch
     (flag-on == flag-off dispatch decisions; the only difference is lines in the
     gitignored `board/.events.jsonl`, files under `board/runs/<run_id>/`, and the
     committed `metrics/evidence/` + `metrics/attestations/` artifacts). Isolation
     is not silent swallow: the returned `WaveAttestation` records the mechanics'
     outcome, and a raised load-bearing step surfaces as a logged failure the CI
     attestation gate detects — never a dropped result.

1. **Read state.** `board/README.md` (schema), `board/ROUTING.md` (reviewer
   map), then the frontmatter of every `board/tickets/*.md`. A missing tickets
   dir is an identity failure → stop. **This wave dispatches the org
   `board/tickets/` only — DasLab-platform (org-engine) work. A project's board
   (`projects/<slug>/board-tickets/`) is run by a `/daslab-cycle` wave invoked in
   that project's own context, never pulled into `board/tickets/`
   (QONUN — Project Placement Law).**

2. **Triage (orchestrator-only edits, cheap, do them all):**
   - **Zombie/stale-worktree reap pass (run first, before any routing edit).**
     Run `git worktree list --porcelain` and collect every path matching
     `.claude/worktrees/DAS-*`. For each such path, check whether its ticket is
     `done`, `blocked`, or the branch has already been merged into `origin/main`
     (`git branch -r --merged origin/main | grep <branch>`). If so: run
     `git worktree remove --force <path>` then `git worktree prune`. Log a note
     in the wave-log line for that ticket (or append a freeform line
     `reaped <id> — <reason>`). This closes the zombie accumulation observed in
     the pre-W1 baseline (stale worktree entries from crashed past runs).
   - `todo` with empty `assignee` → assign a role using the ticket's `dept` +
     the RACI in `governance/policies/raci.md`; log the routing in the ticket.
   - `in_review` where `assignee` == `author` → reassign to the author's
     reviewer per ROUTING.md (manager; if manager is the author, one level up).
   - Skip tickets whose title/description matches external blocks
     (RAHMAT / UZINFOCOM / IKPU / tax / legal entity) — leave them, count them.

3. **Select every actionable ticket** (or the first `N` if args set a bound).

   **Interrupted-resume detection (run first, before normal priority selection):**
   Scan every ticket with `status: interrupted`. For each:
   1. Read the full ticket file and look for a line matching `resume:<value>`
      **anywhere in the body** (below the frontmatter — not in a frontmatter
      field).  If absent, the ticket is **parked** — skip it entirely.
      **Gates ALWAYS wait for the Founder. NEVER synthesise, default, or infer a
      `resume:` value.** An unanswered `interrupted` ticket stays parked until a
      human Founder writes the `resume:` line.
   2. If `resume:<value>` is present, locate the interrupt card at
      `board/interrupts/<card-id>.json` where the card's `"ticket"` field matches
      this ticket's `id`.  If multiple cards match, use the one with the
      lexicographically latest filename (monotonically increasing card ids).
      If no card is found: log a warning in the wave-log line for that ticket
      and skip — do not auto-answer.
   3. Validate that `<value>` is one of the card's `"options"` list (case-
      sensitive, exact match).  If not: log an error in the wave-log line for that
      ticket and skip — do not dispatch with an invalid value.
   4. Transition the ticket `status: interrupted → in_progress` (update the
      frontmatter `status:` field and `updated:` date; append a `## Log` entry
      noting the resume value and the wave date).
   5. Record the resume context (value + card) for injection into the dispatch
      dynamic tail in step 5c (slot 3 — after the ticket body text, before
      last-N scratchpad, strictly after the last `cache_control` breakpoint).

   A ticket that was resumed in this step is dispatched in the normal priority
   order below as `in_progress`.  Its zone / dep-blocked / clarify-blocked
   guards still apply — a resumed ticket is not exempt from correctness checks.

   Use `scripts/interrupt_roundtrip.py` (`detect_resumed_tickets`) to implement
   this detection; it handles the card-lookup, validation, and injection-string
   building so the orchestrator does not need to re-implement them inline.

   Priority order: `p0` first, then `in_review` (unblock the pipeline), then
   `in_progress`, then `todo`. A role MAY take multiple tickets in one wave —
   spawn one subagent instance per ticket (each works WIP=1 in its own
   worktree). **Correctness guard (keep):** never two tickets touching the
   same repo area / file set in the same wave — use the declared `zone:` field
   (ADR-0016) when both tickets have one, else fall back to `parent` + title
   overlap; the loser waits for the next wave. Parallel work on the same files
   causes merge conflicts and rework, which *lowers* throughput.
   **Opt-in widening (default stays closed):** a same-zone *pair* MAY run in one
   wave ONLY when every ticket in that zone declares the SAME valid, permitting
   `merge_policy:` (`append-only` / `owner-exclusive` / `aggregate:<reducer>`),
   whose parallel outputs are then merged deterministically by
   `scripts/merge_reducers.py`. With no policy — or a mismatched/invalid one —
   the pair is still forbidden (fail-closed). The decision is the exported,
   fail-closed `board_lint.same_zone_pair_allowed` / `zone_wave_conflicts`
   predicate; it only ever *widens* the guard, never weakens the no-policy
   default. A ticket whose
   `depends_on:` names an id that is not yet `done` is NOT actionable — skip it
   and count it `dep-blocked` (like the AADL gate-order skip).
   **Fanout deferred-synthesis guard:** A ticket carrying `defer: true` is a
   **deferred synthesis ticket** emitted by the fanout primitive (see step 5e).
   It is NEVER dispatched early — `defer: true` is a **hard guard** independent
   of (and in addition to) the `depends_on` dep-blocked skip above.  Even if a
   race condition would otherwise make the ticket appear actionable, re-check
   every id in `depends_on` explicitly: if any is not `done`, refuse dispatch
   and count it `dep-blocked`.  A deferred ticket becomes actionable only when
   every id in its `depends_on` list is `done` AND no race has bypassed the
   dep-blocked check — the double-check is mandatory because the synthesis
   ticket's correctness depends critically on all children having completed.
   **AADL gate order** (`governance/policies/ai-agent-lifecycle.md`; machine-
   enforced by `scripts/stage_gate.py` / `check_gates.py`): a ticket whose parent
   is a `Stage N` epic — or which carries `stage: GATE-N` — is NOT actionable
   while the same project goal's `Stage N-1` / GATE-(N-1) is not `done`. Skip it
   and count it as gate-blocked. A **GATE-5 (Deployment)** open state provably
   blocks any production-deploy ticket (`gate5_deployment` never-auto-approve,
   `config/risk_taxonomy.yaml`) — the deployment gate ALWAYS waits for a Founder
   sign-off; an open blocking gate is surfaced as a `board/interrupts/` card,
   never auto-answered.
   **Clarify gate (Definition of Ready — ADR-0014):** a ticket carrying an
   unresolved `[NEEDS CLARIFICATION: …]` marker (in plain prose, not a code
   example) is NOT actionable — skip it and count it as `clarify-blocked`. If it
   is `todo`, reassign it to the author's reviewer per `ROUTING.md` (a thinking,
   opus-tier role) to resolve the marker; NEVER dispatch a marked ticket to a code
   subagent. **Circuit-breaker:** if `clarify-blocked` is at least half of the
   actionable set, HALT the wave and emit a blocker report (listing each marked
   ticket) instead of looping — an autonomous run must not stall on agents
   over-flagging to dodge hard tickets. (Enforced fail-closed in CI by
   `scripts/check_clarifications.py --strict`; ADR-0013 ratified 2026-06-26.)

   **W6 — Batch review (pipeline compression):** A single reviewer agent MAY
   clear multiple `in_review` tickets in one wave — spawn one subagent
   instance per ticket as usual, all in parallel. The reviewer's WIP=1
   constraint is per-subagent (each instance handles exactly one ticket);
   the orchestrator may spawn multiple reviewer-role subagents in the same
   wave, one per outstanding `in_review` ticket assigned to that reviewer.
   The correctness guard (no two tickets in the same repo zone) still applies
   — if two `in_review` items touch the same file set, the second waits for
   the next wave.

   If the selection set is empty, run the approved-goal refill check exactly
   once (W5 — never-starve hardening; loop-safe):
   - **Blocker-first:** if any non-done ticket is blocked on external input or
     an open lifecycle gate, emit an explicit report listing each blocker with
     its reason, then stop this wave. Do not plan around real blockers; do not
     restart selection.
   - **Scan for approved queue item:** scan `projects/*/APPROVED-GOAL-QUEUE.md`
     for the first `founder_approved` item with empty `ticket_refs`. This scan
     runs exactly once per empty-selection event — never in a loop.
   - **Board drained — explicit stop report:** if no such item exists (queue is
     empty, exhausted, or every item is already planned/done), emit the
     following literal report and stop immediately:
     > Board drained. No founder-approved queue item available. Awaiting
     > Founder input before the next goal can be planned. (daslab-cycle stop)
     Never invent a new goal, never fabricate a queue item, and never restart
     selection when this branch is taken. The supervisor (`/daslab-run`) will
     surface this stop to the operator.
   - **Refill:** if exactly one `founder_approved` item exists with empty
     `ticket_refs`, apply the `/daslab-plan` decomposition rules to that queue
     item inside this invocation. **Write the tickets to the target board per the
     Placement Law:** a project item's tickets go to that project's OWN board
     (`projects/<slug>/board-tickets/`, carrying `project: <slug>`) — never to the
     org `board/tickets/`; a platform (org-engine) item's tickets go to
     `board/tickets/` with no `project:` field. Update the queue item to `planned`
     with ticket refs, then restart selection once. The org wave selects and
     dispatches only org `board/tickets/` (platform) tickets, so newly-created
     **platform** tickets are dispatched now; newly-created **project** tickets are
     actionable in a `/daslab-cycle` wave run in that project's own context —
     report them as ready rather than pulling them into the org wave.
     Do not run Founder Discovery from `/daslab-cycle`; that belongs to
     `/daslab-plan`. The restart-once constraint is hard: if the newly created
     tickets are themselves immediately empty (e.g. all gate-blocked or all in a
     project board), take the blocker-first branch above — do not restart selection
     a second time.

4. **Wave-log emission (KPI instrumentation — append-only, do this step before
   spawning subagents).** Write the wave-start marker and dispatch table to
   `board/.wave-log` (create if absent; never truncate):

   ```
   ===== wave YYYY-MM-DD HH:MM:SS =====
   | DAS-xxxx  title-slug  todo → in_progress  sre-eng  sonnet |
   | DAS-yyyy  title-slug  in_review → done    qa-lead  opus   |
   ```

   - First line: `===== wave <YYYY-MM-DD> <HH:MM:SS> =====` (UTC wall-clock
     at the moment of dispatch, before any subagent is spawned).
   - One pipe-delimited row per dispatched ticket:
     `| <id>  <short-title>  <old-status> → <new-status>  <assignee>  <model> |`
   - If the selection set is empty (no actionable tickets), append instead:
     `nothing actionable — <YYYY-MM-DD HH:MM:SS>`
   - This log is consumed by `scripts/wave_kpi.py`; do not alter the marker
     format without updating that script. Path: `board/.wave-log` (listed in
     `.gitignore` so it is never committed).

   **Wave PLAN capture for the step-6 runner (ORGANISM WS8 ATTEST — feature-gated
   `organism_emit`, default OFF; skip entirely when OFF).** When ON, immediately
   after the wave-log marker and before any subagent spawns, record the wave PLAN
   as DATA for the single step-6 `run_wave` call: the selected
   `{ticket-id → (from_status, to_status, role, model)}` routing, the anchor
   ticket, and the parked/pending interrupt ids. This is a post-decision
   OBSERVATION of what step-3 selection already decided — it never changes which
   tickets step 3 selected. The wave-open checkpoint is NO LONGER written here as
   prose; `run_wave` writes it (and the paired wave-close checkpoint) at collect
   from this captured plan, via `pulse_checkpoint.write_wave_checkpoint`. Wrap the
   capture in the run-model failure isolation from step 0: an exception is logged
   and the wave proceeds.

5. **Dispatch (worktree-per-ticket isolation — ADR 0005, W1).** Before spawning
   any subagent, the **orchestrator** creates an isolated git worktree for every
   code-touching ticket in the wave. Do this in order, for each ticket:

   a. **Determine if a worktree is needed.** A ticket is "code-touching" (needs
      a worktree) if it will produce a branch / PR. Pure-doc / planning /
      governance tickets that only append to the board or write a single additive
      doc in a zone-disjoint area may run in the main checkout; the rule is:
      "isolate anything that produces a branch/PR." When in doubt, create the
      worktree — isolation is cheap.

   b. **Create the worktree (orchestrator, before spawn).** For code-touching
      tickets, derive the branch slug from the ticket id and title:
      `feat/<ticket-id-lowercase>-<short-slug>` (e.g. `feat/das-1365-worktree-dispatch`).
      Then:
      ```
      git fetch origin
      git worktree add .claude/worktrees/<TICKET-ID>/ \
          -b feat/<ticket-id-lowercase>-<short-slug> \
          origin/main
      ```
      Path is a **pure function of the ticket id** — `\.claude/worktrees/<TICKET-ID>/`
      — so no two agents ever share a worktree. This is the mechanical enforcement
      of LAW 6 at the filesystem layer. If a worktree at that path already exists
      (previous stalled wave), reuse it rather than re-creating (skip `worktree add`).

   c. **Spawn the subagent** (Agent tool, `subagent_type` = role key) — all in
      ONE message so they run in parallel. **Always pass `model` explicitly** =
      the `model:` frontmatter of `.claude/agents/<role>.md` (canon:
      `governance/policies/model-allocation.md`; frontmatter alone is unreliable
      at runtime — claude-code#44385). **No opus wave-mix cap** — dispatch as many
      opus roles as the wave needs (owner removed the 3-opus guard 2026-06-14;
      Max usage wasn't the constraint). Prompt per agent — include the
      **worktree path** so the agent works only there:
      > Work the ticket `board/tickets/<file>.md` (repo root: <worktree-path>).
      > Your working directory is `<worktree-path>` — do all file edits,
      > `git add`, `git commit`, and `git push` from that path. Do NOT create
      > or delete worktrees. Do its next concrete step per your role overlay,
      > update the ticket file (status + log), and report.

      For non-code tickets (no worktree), use the original prompt without a path
      override:
      > Work the ticket `board/tickets/<file>.md`. Do its next concrete step per
      > your role overlay, update the ticket file (status + log), and report.

      **Resume context injection (interrupted → in_progress tickets):** For any
      ticket that transitioned `interrupted → in_progress` in step 3, append the
      resume context block to the dynamic tail of the subagent prompt (slot 3
      "specific ticket text") — strictly **after** the ticket body, before last-N
      scratchpad.  Use `interrupt_roundtrip.build_resume_injection(value, card)`
      to build the text (see `scripts/interrupt_roundtrip.py`).  The injected
      block includes: the Founder's answer, the original question, the option list,
      the interrupt card payload, and an idempotency reminder.

      This block MUST appear only in the dynamic tail — **never** in the stable
      prefix (ADR 0006: volatile content — Founder answer, ticket id, timestamp —
      belongs after the last `cache_control` breakpoint, never before it).

      **W6 — Same-wave build + review (pipeline compression):** When a
      `todo` or `in_progress` ticket and its subsequent `in_review` step can
      be handled by two DISTINCT agent roles in the same wave, dispatch both
      in the same parallel batch. The build agent sets status to `in_review`
      (and its subagent run ends); the reviewer agent — spawned in the same
      `Agent` tool call, running concurrently — then picks it up. Preconditions
      that must ALL be true before applying same-wave build+review:
        1. The reviewer role key differs from the author role key (self-review
           is impossible by the triage reassignment in step 2; this confirms it).
        2. The reviewer is a cheaper or equal-cost model than the builder
           (haiku or sonnet reviewer alongside a sonnet or opus builder).
        3. The ticket is NOT security-touching (see security guard below).
        4. The correctness guard passes — no zone overlap with any other
           ticket in the wave.
      If any precondition fails, dispatch build only; review happens in the
      next wave as normal.

      **Security guard (LAW 2; RACI 5.1 — no compression):** A ticket is
      "security-touching" if its title, description, or parent epic mentions
      auth, secrets, encryption, CVE, supply-chain, or the `security-*` role
      handles it. Security-touching tickets MUST have a blocking security audit
      (security-lead or security-eng review) that runs in its own wave after
      the build wave completes. Do NOT apply same-wave build+review compression
      to security-touching tickets under any circumstances. The step-2 triage
      reassignment guard (assignee == author → reassign to manager) remains
      fully active for all tickets.

   d. **DGO-X shadow emission — `routing_decision` event (ADR 0011, Phase 1).**
      **Feature-gated (ADR-0019): emit ONLY if `config/features.yaml` `dgox_emit` is
      `true`. It defaults OFF — when off, SKIP this whole sub-step (no Phase-2 consumer
      exists yet, so the shadow emission would only burn tokens). Read it via
      `python3 scripts/feature_flags.py`.** When on:
      SHADOW / ADVISORY ONLY — ADR 0010 constraint C3 + Phase-1 shadow rule.
      The emitted records are pure observers. NOTHING in `/daslab-cycle` reads
      or routes off them. Dispatch decisions are entirely unchanged. Phase 2 is
      where a supervisor may read these events; not now.

      For EVERY ticket dispatched in this step (both code-touching and non-code),
      after the worktree is created (or confirmed present) and before the subagent
      is spawned, append one `routing_decision` event to the event store
      (`board/.events.jsonl`) using `scripts/dgox/events.py`. Record:

      - `ticket_id` — the DAS-NNNN id from the ticket frontmatter.
      - `from_status` — the ticket's status at the start of this wave (before
        any orchestrator edit in step 2).
      - `to_status` — the status the ticket will have after dispatch (e.g.
        `in_progress` for a `todo` ticket being dispatched, `done` for an
        `in_review` ticket cleared in the same wave).
      - `assignee` — the role key being dispatched.
      - `model` — the explicit model string passed to the Agent tool call
        (never inferred from frontmatter — LAW 3 / ADR 0007).
      - `reason` — a one-sentence human-readable rationale for the routing.
      - `confidence` — orchestrator confidence score in [0.0, 1.0]; use 0.9 as
        the default for normal scheduled dispatch; lower for ambiguous routing.
      - `policy_checks` — list of gate names that were verified before dispatch
        (e.g. `["aadl_predecessor_gate_closed", "repo_area_available",
        "not_external_blocked"]`). Must be a non-empty list.
      - `fallback` — what happens if a policy check fails (e.g.
        `"skip_to_next_wave"` for zone conflicts, `"block_and_escalate"` for
        AADL failures).
      - `created_at` — call `utcnow()` from `dgox.events` at emission time.

      Emit using the library pattern (not a subprocess):
      ```python
      from dgox.events import EventStore, build_routing_decision, utcnow
      store = EventStore()          # writes to board/.events.jsonl
      ev = build_routing_decision(
          ticket_id=...,
          from_status=...,
          to_status=...,
          assignee=...,
          model=...,
          reason=...,
          confidence=0.9,
          policy_checks=[...],
          fallback=...,
          created_at=utcnow(),
      )
      store.append(ev)
      ```

      If `EventStore.append` raises (malformed event or I/O error): log the
      error in the wave-log line for that ticket and continue — the shadow
      emission MUST NEVER block dispatch. Dispatch proceeds regardless of
      emission success or failure. This is the single-writer enforcement:
      only the orchestrator emits routing_decision events, never subagents.

   e. **Fanout emission — map/reduce shape (P5, ORGANISM pulse loop).**
      When a dispatched ticket carries a `fanout:` directive in its body, or
      when the orchestrator computes N work slices at runtime for a variable-
      width task, materialise the fanout cluster **before** spawning any
      subagent.  Do this in order:

      1. **Determine N at runtime** — the number of work slices.  N is never
         hard-coded; it is computed from the ticket body or from the
         orchestrator's own analysis.
      2. **Call `scripts/fanout.emit_fanout()`** to materialise:
         - **N child tickets** — each carries its own private
           `## Fanout Payload` section (marked with an HTML comment).
           No sibling ticket can read another child's payload; isolation is
           enforced by the file-per-ticket model.  The child ticket body
           also receives a `body_intro` referencing its parent.
         - **1 synthesis ticket** — marked `defer: true`, declares
           `depends_on: [child1, ..., childN]`, and references only child ids
           in its body (never raw sibling payloads).
      3. **Validate the cluster** — run `python3 scripts/check_dependency_graph.py`
         against the board after emission.  No dangling deps, acyclic graph,
         well-formed `zone:` on every ticket.  Abort the wave with a blocker
         report if the validator fails.
      4. **Dispatch children only** — the N child tickets are dispatched in
         this wave as normal (step 5a–d above).  The synthesis ticket is NOT
         dispatched: its `defer: true` marker and the dep-blocked skip in
         step 3 jointly hold it back until every child is `done`.
      5. **Private-payload isolation contract** — the synthesis agent must NOT
         read sibling child ticket files directly.  Results a child wants to
         publish for the synthesis step must be written to an explicit shared
         artifact (board field, output file, or published log entry).  The
         synthesis agent consumes those published results, not the private
         `## Fanout Payload` sections.

   f. **Per-dispatch RESULT capture for the step-6 runner (ORGANISM WS8 ATTEST —
      feature-gated `organism_emit`, default OFF; skip entirely when OFF).
      SEPARATE channel from the step-5d `dgox_emit` shadow — do NOT conflate the
      two flags.** When ON: as each subagent is spawned, capture that dispatch's
      run-lifecycle fields into a run-local buffer — `ticket_id`, `model` (the
      exact explicit string passed to the Agent tool — LAW 3, never inferred),
      `role_key`, `goal`, engine `VERSION`, and the dispatch start timestamp.
      These become the `plan` / `results` DATA fed to the SINGLE
      `wave_runner.run_wave(plan, results)` call at collect (step 6). No
      `run_start` / `run_end` / span event, checkpoint, ledger, evidence, or
      attestation is written here: the runner builds them ALL at collect, once
      each ticket's outcome, PR/CI/T7 evidence, and end timestamp are known. This
      capture is purely observational — it reads no event back into the dispatch
      decision, and a failure to buffer is caught and logged and NEVER blocks
      dispatch (flag-on == flag-off dispatch decisions). This does not alter the
      worktree path (still the pure function of ticket id from step 5b) or any
      selection guard.

   g. **Guardrail tripwire — INPUT/OUTPUT screen with retry-with-feedback
      (`governance/guardrails/` + `scripts/guardrail_dispatch.py`).** Every
      dispatch is wrapped by a per-role guardrail tripwire so a wrong-scope or
      wrong-output dispatch neither silently ships nor stalls. Each role has a
      guardrail module `governance/guardrails/<role>.py` exposing
      `input_guardrail(ctx)` and `output_guardrail(ctx)`, each returning
      `(ok, feedback)`; a role with no bespoke module falls back to the shared
      `default_*` guardrails (so every role is always guarded). The wrapper
      contract, in order:

      1. **INPUT screen (pre-accept).** Before the subagent accepts the ticket,
         run the role's INPUT guardrail (`guardrail_dispatch.build_context`
         assembles it from the ticket + this ROUTING role table + the board). It
         refuses out-of-scope work: wrong-department (the ticket `dept` does not
         match the role's dept in this ROUTING table), a missing declared
         `consumes:` input, or a gate-open violation (an unfinished `depends_on`
         predecessor or an open AADL predecessor gate). On an INPUT trip the
         ticket is NOT accepted — log the reason and re-route, it is not this
         role's work.
      2. **accept → run the agent → OUTPUT screen.** After the agent produces
         its work, run the role's OUTPUT guardrail against that output.
      3. **retry-with-feedback (max 2).** On an OUTPUT trip, write the guardrail
         feedback into the ticket `## Log` tagged `origin: output_guardrail` (so
         a later reader tells guardrail feedback apart from a human reviewer's
         notes) and re-dispatch the SAME agent with that feedback so it can
         self-correct. This is bounded to a maximum of two retries.
      4. **escalate.** If the OUTPUT guardrail still trips after the two retries
         are exhausted, escalate per this ROUTING map: reassign the ticket to the
         failing role's reviewer (its "Reports to" column) and mark it
         `in_review`; if that reviewer IS the ticket author (manager-is-author),
         climb one level up the chain (ultimately CTO/CEO) — the same reviewer
         resolution step 2 uses for `in_review` reassignment. Never loop
         unboundedly; never pass tripped work through.

      The loop is deterministic and its only side effect is on the ticket file
      (append-only feedback log + the escalation reassignment); it never spawns a
      subagent itself — the orchestrator drives the re-dispatch. Reuse the
      reviewer chain already parsed in step 2; do not re-invent the lookup.

6. **Collect & verify.** After all return: re-read each dispatched ticket —
   confirm `status`/`updated`/log actually changed (a subagent that returned
   text but didn't edit the file gets its result written into the log by YOU,
   marked `(orchestrator-recorded)`). Apply any routing the reports request.

   **Live CI/PR done-gate (ADR 0008, W7 — LAW 5: green CI = done).**
   Before marking any engineering ticket `done`, the orchestrator MUST verify
   that its PR's CI checks are actually green:
   ```
   gh pr checks <PR-number>
   ```
   A ticket transitions to `done` only when ALL listed checks pass (exit 0).
   If any check is failing or still running, set `status: in_progress` (not
   done), log the failing check name and its URL, and schedule a follow-up
   check in the next wave. **"Done" is never assumed from a subagent's report
   alone** — the orchestrator confirms it by querying GitHub directly. This gate
   applies to all engineering tickets that have a PR; documentation-only tickets
   with no branch/PR are exempt.

   **ArcRift outbox drain (ADR 0008, W7):** After step 6 collect and before
   emitting the step 7 wave report, the orchestrator reads `board/.arcrift-outbox.jsonl`
   and drains any pending store entries. For each entry (in append order):
   call `store_memory` with the entry's `project`, `content`, and metadata;
   on success, mark the entry acked (append a `{"acked": true, "id": ...}` line);
   on transient failure retry up to 3× with 2-second back-off before leaving
   the entry for the next wave's drainer. A failed entry is never removed —
   it stays for replay. The single-drainer pattern (only the orchestrator calls
   store_memory, never agents directly) prevents the known concurrency race.

   **Worktree reap on resolution (ADR 0005 §4).** For each code-touching ticket
   whose new status is `done` or `blocked` (abandoned), remove its worktree and
   prune:
   ```
   git worktree remove --force .claude/worktrees/<TICKET-ID>/
   git worktree prune
   ```
   Tickets that are `in_review` keep their worktree alive (the branch still
   exists; the reviewer needs it). When a ticket transitions from `in_review` to
   `done` in a future wave, the reap pass in step 2 will catch it.
   If `worktree remove` fails (path already gone, or lock held by a crashed
   agent), log the failure and continue — the step 2 reap pass in the next wave
   will clean it up.

   **Wave lifecycle — the single deterministic `run_wave` call (ORGANISM WS8
   ATTEST, ADR-0031; feature-gated `organism_emit`, default OFF; skip entirely
   when OFF).** When ON, after the collect + CI/PR done-gate has settled every
   ticket's final status, build the wave PLAN and RESULTS as DATA and call
   `scripts/wave_runner.run_wave(plan, results)` EXACTLY ONCE. This one call
   subsumes every wave mechanic that used to be prose spread across steps 0/4/5f/6
   — the wave-open/-close checkpoints (`pulse_checkpoint`), the
   `run_start` / `run_end` / span triplet per dispatch (`dispatch_emitter`), the
   per-role INPUT/OUTPUT guardrail tripwires (`guardrail_dispatch`), the
   progress-/task-ledgers + per-ticket completion records
   (`check_ledger` / `task_ledger` / `pulse_checkpoint`), the committed redacted
   evidence snapshot (`snapshot_evidence`, P13), the committed doubly
   hash-chained `WaveAttestation` (`metrics/attestations/<run_id>.json`), and —
   ATOMICALLY with that attestation (ADR-0032 §1) — one committed, append-only,
   hash-chained entry in the TRACKED `board/wave-ledger.jsonl`. A ticket's
   done-ness now flows THROUGH this attested runner — it is structurally
   load-bearing, not an optional side-effect the model may skip or reorder.

   **The committed wave-ledger is the durable "a wave happened" record.** The
   ledger entry (`board/wave-ledger.jsonl`) is a SECOND, independent committed
   chain co-produced alongside the attestation: it binds each recorded wave to its
   attestation (`attestation_hash`) so that an omitted or tampered wave breaks a
   committed chain instead of leaving a silent gap. Because it is append-only and
   hash-chained, a wave that commits done-ness MUST leave a reconciled ledger
   entry — a dropped or omitted wave becomes *detectable* rather than silently
   lost. The co-write is LOAD-BEARING inside `run_wave` (it raises on failure), so
   the attestation and its ledger line are one atomic unit: both produced, or the
   call raises — never one without the other.

   **Collect-time reconciliation (run after the wave).** After the single
   `run_wave` call has co-produced the committed attestation + ledger entry, run
   the reconciliation gate `python3 scripts/check_wave_reconciliation.py` to prove
   the dispatch record is internally consistent — every committed ledger entry has
   a matching committed attestation (bijection), the per-run entries form an
   unbroken hash chain (a dropped line FAILs), and every ticket a ledger entry
   names reached a terminal state on the board. The reconciler reads the ledger
   through the same `wave_runner` SSOT primitive (`verify_wave_ledger`) the runner
   writes with, so it never forks the chain/hash logic. A reconciliation failure
   is surfaced fail-closed (the CI gate detects a missing, gapped, orphaned, or
   tampered ledger/attestation) — this is what makes an omitted wave detectable.

   Build the two inputs from the step-4 plan buffer and the step-5f dispatch
   buffer plus the settled collect outcomes, REUSING the shipped types (do NOT
   re-implement any mechanic, do NOT import `dgox.*`):
   ```python
   from wave_runner import run_wave, WavePlan, TicketPlan, WaveResults, TicketResult
   from feature_flags import enabled
   import pulse_checkpoint, dispatch_emitter

   run_id = pulse_checkpoint.generate_ulid()          # minted ONCE, here
   plan = WavePlan(
       run_id=run_id, wave=wave_index, goal=goal, engine_version=VERSION,
       tickets=[TicketPlan(ticket_id=t, role=role, model=model,
                           from_status=old, to_status=new) for ...],
       anchor_ticket=anchor, pending_interrupts=parked_interrupt_ids,
   )
   results = WaveResults(
       tickets=[TicketResult(ticket_id=t, outcome=outcome, merged_pr=pr,
                             ci_status=ci, t7_pass=t7p, t7_score=t7s,
                             start=start_ts, end=end_ts, final_status=final,
                             output=agent_output) for ...],
       request_satisfied=..., in_loop=..., progress_being_made=...,
       next_tickets=[...], instruction="...",
   )
   try:
       attestation = run_wave(
           plan, results,
           created_at=dispatch_emitter.utcnow(),
           organism_emit=enabled("organism_emit"),
       )
   except Exception as exc:            # failure-isolated at the CALL boundary
       attestation = None              # log `exc` in the wave report; wave proceeds
   ```
   - `run_wave` mints nothing and reads no clock: `run_id` and every timestamp are
     caller-supplied (volatile — dynamic tail only, ADR 0006). It makes NO routing
     decision — `plan` carries the routing already decided in steps 2–3, `results`
     the outcomes already collected above.
   - **flag-on == flag-off DISPATCH DECISIONS.** With `organism_emit` OFF the call
     returns `None` and writes nothing (no attestation AND no wave-ledger line);
     the ONLY difference between flag states is the post-decision artifacts
     (`board/.events.jsonl` lines, files under `board/runs/<run_id>/`, the
     committed `metrics/evidence/<run_id>.json` + `metrics/attestations/<run_id>.json`,
     and the committed `board/wave-ledger.jsonl` entry). No dispatch/collect
     decision reads any emitted event back.
   - **Commit the committed artifacts.** `metrics/evidence/`,
     `metrics/attestations/`, and `board/wave-ledger.jsonl` are TRACKED (not
     gitignored). Commit the produced evidence + attestation + the co-produced
     wave-ledger entry alongside the wave's other tracked changes — they are the
     proof `check_metric_gaming.py` / `check_attestation.py` /
     `check_wave_reconciliation.py` require for every counted run.
   - The run is thereby opened AND CLOSED within this single operator-invoked
     wave. No daemon, loop, or timer is started; the next wave is a fresh operator
     invocation (the "one invocation = one wave" contract is preserved).
   - **Failure isolation (call boundary):** the single `run_wave` call is wrapped
     so any exception is caught and logged in the wave report; the collect/verify
     results above are unaffected. A failed call NEVER blocks the wave — flag-on
     and flag-off produce identical dispatch and collect DECISIONS. The
     load-bearing emission/attestation raise on failure INSIDE the call, so the
     failure is recorded and surfaced (the CI attestation gate detects a missing
     or broken attestation) — isolation is not silent swallow.

7. **Report the wave** (this is what the user reads):
   - table: ticket → old status → new status → agent → one-line outcome
   - blocked tickets with reasons; escalations; orphaned todos still unrouted
   - what the next wave would pick up.
   - when `organism_emit` is ON: the wave's `run_id` and the
     `board/runs/<run_id>/` checkpoint path (for `--resume` / `--fork` and
     downstream observability); omit when the flag is OFF.

## Prompt-cache prefix layout (ADR 0006 — W4)

### Why this matters

Every dispatched agent re-sends a large shared preamble (~27 KB of QONUN laws,
AADL gate model, board schema, dept charters, and the role overlay invariant
text). Anthropic prompt-cache reads bill at ~10% of base input price, so a
stable cached prefix cuts the input cost of that region by ~90%. A single
volatile byte — a timestamp, run-id, or ticket-id — placed **before** the
`cache_control` breakpoint invalidates the entire downstream cache fleet-wide
and re-pays full input cost on every agent call.

### Byte-stable prefix rule

The **stable prefix** is the only content allowed before the last
`cache_control: {type: "ephemeral"}` breakpoint. It contains exactly:

1. The frozen system text (QONUN laws, AADL gate model, board schema, dept
   charter, the role overlay's invariant paragraphs) — same bytes for every
   agent, every wave, every run.
2. The **deterministically sorted** tool list (sorted by tool name before
   serialisation) — order must never vary across calls for the same agent type.

**Nothing else belongs in the stable prefix.** In particular, the following
are PROHIBITED before the breakpoint:

- ISO timestamps (e.g. `2026-06-19T14:30:00Z`)
- Run IDs, wave counters, or UUIDs (`run-id`, `wave-N`, UUIDv4 patterns)
- Ticket IDs or ticket text (e.g. `DAS-1367`, ticket body)
- Per-wave summaries or current-state snapshots

### Minimum cacheable prefix

Opus 4.8's minimum cacheable prefix is **1024 tokens**. A breakpoint placed
after fewer than 1024 tokens of stable content causes the cache to emit a miss
on every call — no savings at all. (The earlier note of "4096" was stale and
referred to a different model generation; 1024 is the correct Opus 4.8 figure.)

Ensure the stable prefix is long enough to cross this threshold. If charter
consolidation trims the preamble, add a linter check (see below) rather than
silently losing the cache.

### Dynamic tail (after the last breakpoint)

All volatile content goes strictly after the last `cache_control` breakpoint,
in this order:

1. Global ticket summary (cross-wave board state snapshot)
2. Per-phase or per-epic summary
3. The specific ticket text (body + acceptance criteria)
4. Last-N scratchpad (recent agent outputs, ArcRift recall)
5. Run-id / wave counter / current timestamp

### Bounded STATUS summaries (~1–2k tokens)

The dynamic tail may include STATUS summaries — a compact digest of the current
wave state provided to each spawned subagent so it understands the broader
context without re-reading every ticket. Keep these **bounded to ~1–2k tokens**
per summary. A summary that grows without bound eventually defeats the cost
savings it was designed to enable. Enforce this in the wave-log or a dedicated
truncation pass before injection.

### CI enforcement (check_cache_prefix.py)

`scripts/check_cache_prefix.py` is the machine check for the above invariant.
It fails the build if:

- (a) The byte-content of the designated stable-prefix region changes without
  an accompanying version bump — prevents silent cache-version drift.
- (b) Any dynamic marker (ISO timestamp, run-id/UUID pattern, ticket-id
  pattern, wave counter) appears inside the stable-prefix region.
- (c) The stable-prefix region is shorter than 1024 tokens (Opus 4.8 minimum).

Run standalone: `python3 scripts/check_cache_prefix.py`
CI: wired into the `validate` job in `.github/workflows/ci.yml`.

CACHE_PREFIX_VERSION: v19-wave-ledger-reconcile

## Boundaries

- You dispatch and route; you do NOT do the tickets' work yourself.
- Don't create tickets here (that's /daslab-plan) — except (a) a follow-up
  ticket a subagent's report explicitly asks for, or (b) the one approved-goal
  refill case above. New project discovery is never done by cycle.
- Board state lives only in the ticket files — never cache between waves.

## Recovery affordances — --resume and --fork (DAS-1445)

Two operator-invoked recovery modes extend `/daslab-cycle`. Both are
explicitly operator-invoked (passed as arguments); normal wave dispatch is
unchanged.

### `--resume <run_id>`

Replay `board/.events.jsonl` for `run_id` to the last valid checkpoint and
re-dispatch **only unfinished** tickets (those whose last recorded `to_status`
is not a terminal `done`/`blocked`). Already-finished tickets are NOT
re-dispatched (no duplicate work, no clobbering already-merged branches).

**Refuse on corrupted chain.** If `replay_qa.replay_run` finds a broken
or invalid transition for any ticket in the run, resume raises a `ValueError`
and stops — it never re-dispatches off a corrupted replay (T5 zero-corrupted
guardrail; consistent with `scripts/check_recovery.py`).

**Implementation.** Call `scripts/resume_fork.resume_run(run_id)` which:
1. Groups events via `replay_qa.group_runs` (canonical grouping contract).
2. Calls `replay_qa.replay_run` per ticket (canonical transition walk).
3. Cross-checks against `pulse_checkpoint.get_completed_tickets` to exclude
   tickets with a durable completion record (crash-safe: do not re-dispatch
   a ticket that completed before the crash).
4. Returns `{ticket_id: last_status}` for tickets still needing dispatch.

**Selection guards still apply.** A resumed ticket is NOT exempt from the
4 selection guards (zone, dep-blocked, AADL gate-order, clarify gate). Apply
them to the `resume_run` result before dispatching.

**Worktree reuse.** The worktree path is a pure function of ticket id
(`.claude/worktrees/<TICKET-ID>/`). If a worktree already exists at that
path (previous stalled wave), reuse it — do NOT re-create it (step 5b rule).

**`run_id` in events.** For `--resume` to find a wave's tickets, each
`routing_decision` event SHOULD carry the wave's ULID as `run_id`. When
events lack an explicit `run_id`, `replay_qa._run_key` falls back to
`ticket_id`, so `--resume DAS-NNNN` can still replay a single ticket's chain.
Emit `run_id` in step 5d to enable multi-ticket wave recovery.

### `--fork <run_id>@wave-NNN`

Copy the source run's checkpoint state as of `wave-NNN` into a **new**
`run_id` (a freshly minted ULID) and continue alternative planning from there.
The original run's recorded events in `board/.events.jsonl` are left
byte-for-byte untouched — fork writes only new-run events; it never rewrites,
deletes, or re-parents the source run's history.

**Parse the argument** with `scripts/resume_fork.parse_fork_arg(arg)` which
returns `(source_run_id, wave_num)`.

**Implementation.** Call `scripts/resume_fork.fork_run(source_run_id, wave_num)` which:
1. Calls `pulse_checkpoint.reconstruct_ticket_states(source_run_id, wave_num)`
   to recover the full ticket state at `wave-NNN` from the checkpoint delta chain.
2. Mints a new ULID via `pulse_checkpoint.generate_ulid()`.
3. Returns `(new_run_id, ticket_states)` — the new run starts empty (no
   checkpoint files copied to avoid corrupting the ledger hash chain).

New waves dispatched after the fork emit events with `run_id = new_run_id`
and write their own checkpoints under `board/runs/<new_run_id>/`. The source
run's audit trail is permanently intact.

### Shadow-rule note (ADR-0011 Phase-1)

`--resume` reads `board/.events.jsonl` to decide dispatch — the first genuine
event-reader in the recovery path. The Phase-1 "flag-on == flag-off dispatch"
guarantee holds for ALL normal waves (step 5d remains purely observational).
Only the explicit operator-invoked `--resume`/`--fork` path reads events.
A formal ADR supersession is recommended (tracked; see DAS-1445 log and the
comment in `tests/test_dgox_phase1_shadow.py`).
