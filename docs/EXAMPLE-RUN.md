# Example run — DasLab on any goal

DasLab is a **project-agnostic software factory**. Give it a goal; it first
turns that goal into a Founder-approved, research-backed queue, then plans,
builds, tests, reviews, secures, documents, and ships through the six AADL gates.
This page shows the shape of a run on a small generic goal so a new operator
knows what to expect.

## 1. Bootstrap (once per clone)

```bash
git clone https://github.com/nabievuz/daslab.git && cd daslab
python3 scripts/bootstrap.py          # resolve root, create projects/, regenerate agents, preflight
claude                                # open a session at the repo root
```

## 2. Plan — discovery, research, approval, then tickets

```
/daslab-plan "Build a small CLI that converts CSV to JSON, with tests and a README"
```

For a new project, the CPO/CEO planner first:
- asks the Founder at least 10 discovery questions;
- performs current global research with source links;
- writes `projects/csv2json/APPROVED-GOAL-QUEUE.md`;
- waits for explicit Founder approval.

After the queue item is approved, decomposition:
- creates `projects/csv2json/` (its own git, gitignored) with the AADL skeleton
  `docs/01-planning/ … docs/06-maintenance/` and a project charter;
- writes the GATE-1 plan;
- files stage-gated epics + PR-sized tickets in the project's own board
  `projects/csv2json/board-tickets/`, tagged `goal: csv2json` (the org
  `board/tickets/` is platform-only — QONUN Project Placement Law).

```
projects/csv2json/board-tickets/
  DAS-0042  csv2json — Stage 1: Planning (GATE-1)        [cpo]
  DAS-0043  csv2json — Stage 2: Design (GATE-2)          [cto]
  DAS-0044  csv2json — implement csv→json converter      [backend-eng-1]
  DAS-0045  csv2json — pytest suite for the converter    [qa-eng]
  DAS-0046  csv2json — README + usage docs               [tech-writer]
  …
```

## 3. Cycle — execute wave by wave

```
/daslab-run
```

`/daslab-run` repeatedly applies `/daslab-cycle` while tickets are actionable,
and refills from the next `founder_approved` queue item when the board drains.
Each wave triages the board, dispatches the actionable role agents in parallel
(each on the model its task complexity needs), collects results, and routes
finished work to the reviewing manager (`author ≠ reviewer`). Gates govern: no
ticket is `done` without a merged PR + green CI; no stage opens before the prior
gate closes.

## 4. Ship

When GATE-5 closes, the deliverable lives under `projects/csv2json/` — runnable
code, a passing test suite, a README, and a clean git history — built entirely by
the org. The public board returns to (almost) empty, ready for the next
Founder-approved queue item.

> Swap the goal for anything — an API, a data pipeline, a docs site, a research
> report. The intake gate is the same; only the project changes.
