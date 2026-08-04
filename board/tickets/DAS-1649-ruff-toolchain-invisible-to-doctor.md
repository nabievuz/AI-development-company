---
id: DAS-1649
title: The 100/100 gate silently depends on an activated venv, and doctor.py never checks
status: todo
assignee: sre-eng
author: cto
dept: engineering
priority: p2
parent: 
goal: platform-hardening
labels: [tooling, docs]
zone: scripts
depends_on: []
created: 2026-08-04
updated: 2026-08-04
---

## Description

**Both subagents in the 2026-08-04 wave independently tripped on this, and each drew a
different wrong conclusion from it** — one reported "main is 85/100, not 100/100", the
other called it "a missing-toolchain artifact". Neither was quite right, which is the
point: the number is environment-dependent and nothing says so.

`scripts/diagnostics.py:470` shells out to `ruff` **from `PATH`**:

```python
ruff = subprocess.run(["ruff", "check", ...])
```

`ruff==0.9.10` is declared in `requirements-dev.in`/`.txt` and installed in `.venv`, but
`.venv/bin` is only on `PATH` when the venv is activated. So the same commit scores:

| Environment | Score |
|---|---|
| venv activated | **100/100** |
| bare shell (venv present, not activated) | **85/100** — `Code-quality 0/15`, "ruff unavailable" |

The fail-closed behaviour itself is correct per ADR-0021 — an unmeasured lint gate must
not read as a pass. The defect is that **nothing warns anyone**:

- `scripts/doctor.py` checks Claude Code, Python, git, repo root and `projects/` — it
  does **not** check `ruff`, so the preflight that exists to catch exactly this reports
  `REQUIRED 5/5 pass` on a machine where the release gate cannot score 100.
- No document — `README.md` Quickstart, `docs/USER-GUIDE.md`, `docs/USAGE.md` — mentions
  creating or activating a venv, or installing `requirements-dev.txt`.
- Worktrees under `.claude/worktrees/` have no `.venv` at all, so every agent working in
  one sees 85/100 by default and must diagnose it from scratch. Two did, this wave.

A newcomer following the documented Quickstart in a fresh shell gets 85/100 on an
untouched clean checkout and reasonably concludes the platform is broken.

## Acceptance criteria
- [ ] `doctor.py` reports the lint toolchain. Decide and record the tier: `REQUIRED`
      (the release gate cannot pass without it) or `OPTIONAL` with an explicit warning
      naming the 15-point consequence — do not add a silent check.
- [ ] The `ruff unavailable` line in `diagnostics.py` says how to fix it, not just that
      it failed (every other failure line in that file names the remedy).
- [ ] `README.md` Quickstart states the dev-dependency/venv step, and
      `scripts/check_quickstart.py` still passes.
- [ ] Decide whether `diagnostics.py` should prefer `.venv/bin/ruff` when present before
      falling back to `PATH`; record the reasoning either way. A resolution that makes
      agents-in-worktrees work is preferred over one that only fixes the main checkout.
- [ ] Verified in a genuinely clean shell (`env -i` or equivalent), not in a shell that
      already had the venv sourced — the confound that produced two wrong readings.
- [ ] `diagnostics.py` 100/100; `board_lint`/validators green; no `project:` field (R9).

## Log
### 2026-08-04 — orchestrator (daslab-cycle wave)
Not requested by either subagent — filed by the orchestrator after independently
reproducing both readings. Confirmed with `env -u VIRTUAL_ENV PATH=/usr/local/bin:/usr/bin:/bin`:
`Code-quality 0/15`, `SCORE = 85/100` on an otherwise clean `main` at `4fd0412`. With the
venv active, the same tree scores 100/100.

`docs/BOSHLANGICH-QOLLANMA.md` §5 was corrected in the same wave to state the dependency
up front, since that guide promised 100/100 to a first-time reader and would have sent
them straight into this. The doc fix is a mitigation, not the fix — the tooling gap here
is what actually needs closing.
