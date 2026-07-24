#!/usr/bin/env python3
"""stage_gate.py — machine-enforced stage-gated delivery (P22 / DAS-1494).

DasLab already mandates the six-stage AI-agent lifecycle
(``Planning → Design → Development → Testing → Deployment → Maintenance`` —
``governance/policies/ai-agent-lifecycle.md``) and a never-auto-approve law for
the deployment gate (``gate5_deployment`` in ``config/risk_taxonomy.yaml``). This
module supplies the **end-to-end machine enforcement** that turns the documented
gate order into a hard block, so a project board is provably *executed through the
AADL gates* rather than advanced by convention:

- **Gate order** — a stage-N ticket may not *advance* (reach ``in_progress`` /
  ``in_review`` / ``done``) while GATE-(N-1) is still open (the same goal's
  stage-(N-1) work is not ``done``). A ``todo`` / ``backlog`` stage-N ticket is a
  legitimate *waiting* state and is NOT a violation — only advancing past an open
  gate is (``gate_order_violations``).
- **GATE-5 ⇒ no production deploy** — a production-deploy ticket (classified
  against the *existing* ``gate5_deployment`` risk category, not a new path) must
  not be auto-approved (GATE-5 is human-only, QONUN-5) and must not advance while
  its goal's GATE-5 (Deployment) is open (``production_deploy_violations``).
- **Gate walk** — ``walk_gates`` reads a compiled project board
  (``projects/<name>/board-tickets/``), computes each goal's gate states, and
  refuses to advance past an open gate. Open gates that block downstream stages
  are surfaced as **interrupt-cards** (``emit_gate_cards`` → ``board/interrupts/``,
  DAS-1446 schema) so the Founder — never the machine — signs the gate.
- **Maintenance** — ``maintenance_schedule`` declares the recurring health/eval
  runs the Maintenance stage (GATE-6) owns: the WS4 heartbeat tick and the WS6
  golden-eval harness. It is DATA (a descriptor), not an installer — cadence lives
  in the Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here deploys.

The gate model keys off the ``stage: GATE-N`` frontmatter field that
``gateway_compile.py`` stamps on every story ticket, plus the ticket's ``goal``.
It reuses ``check_gates`` (ticket loader / frontmatter parser) and
``check_never_auto_approve`` (the ``gate5_deployment`` matcher + auto-approval
detector) — no parallel classification path.

Usage::

    python3 scripts/stage_gate.py <board-dir> [--emit-cards] [--interrupts DIR] [--json]

``<board-dir>`` is a compiled board directory (``projects/<name>/board-tickets/``).
Exit codes: 0 = board may advance (no gate violation), 1 = an open-gate violation
blocks advancement, 2 = usage / IO error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _paths import ROOT

# scripts/ is on sys.path when run directly; make the sibling imports robust.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import check_gates as ck  # noqa: E402  (reused loader + frontmatter parser)
import check_never_auto_approve as cna  # noqa: E402  (reused gate5 matcher + auto detector)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# A ticket in one of these states has ADVANCED past the waiting line: it is being
# worked or is complete. Advancing a stage while its predecessor gate is open is
# the violation; a `todo`/`backlog` stage ticket is the legitimate waiting state.
ADVANCED_STATUSES: frozenset[str] = frozenset({"in_progress", "in_review", "done"})

GATE5_CATEGORY = "gate5_deployment"

STAGE_NAMES: dict[int, str] = {
    1: "Planning",
    2: "Design",
    3: "Development",
    4: "Testing",
    5: "Deployment",
    6: "Maintenance",
}

# Extract the AADL stage number from a `stage: GATE-N` frontmatter value.
_STAGE_FIELD_RE = re.compile(r"GATE-([1-6])", re.IGNORECASE)
_TICKET_ID_RE = re.compile(r"^DAS-\d+$")

Ticket = tuple[Path, dict[str, str]]


# --------------------------------------------------------------------------- #
# Frontmatter field helpers
# --------------------------------------------------------------------------- #

def stage_of(fm: dict[str, str]) -> int | None:
    """Return the AADL stage number (1–6) from the ticket's ``stage:`` field, or None."""
    m = _STAGE_FIELD_RE.search(str(fm.get("stage", "")))
    return int(m.group(1)) if m else None


def _coerce_list(raw: object) -> list[str]:
    """Coerce a raw frontmatter value into a clean list of string tokens.

    The regex frontmatter parser (``check_gates``/``board_lint``) captures a list
    value like ``[deploy, gate-5]`` as the raw string ``"[deploy, gate-5]"`` and a
    scalar as a bare string. This normalises both into ``["deploy", "gate-5"]`` so
    the reused ``check_never_auto_approve.matches_category`` (which expects
    scalar-or-list) binds correctly (mirrors ``board_lint._schema_names_of``).
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    out: list[str] = []
    for part in s.split(","):
        cleaned = part.strip().strip('"').strip("'").strip()
        if cleaned:
            out.append(cleaned)
    return out


def load_gate5_matcher(config_path: Path | None = None) -> dict | None:
    """Return the ``gate5_deployment`` matcher from ``config/risk_taxonomy.yaml``.

    Returns None (R12/gate-walk skips the prod-deploy rule) if the config is
    absent or malformed — the deploy classification KEYS OFF the taxonomy config
    (QONUN-5) rather than a hard-coded parallel list.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment guard
        return None
    p = Path(config_path) if config_path else (ROOT / "config" / "risk_taxonomy.yaml")
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    matchers = (cfg or {}).get("matchers", {})
    matcher = matchers.get(GATE5_CATEGORY)
    return matcher if isinstance(matcher, dict) else None


def is_production_deploy(fm: dict[str, str], matcher: dict | None) -> bool:
    """True iff the ticket is a production-deploy per the ``gate5_deployment`` category.

    Reuses ``check_never_auto_approve.matches_category`` against the taxonomy's
    ``gate5_deployment`` matcher (labels ``deploy``/``gate-5`` or ``stage: GATE-5``)
    — the SAME classifier the never-auto-approve gate uses, not a fork.
    """
    if not matcher:
        return False
    coerced = {
        "stage": _coerce_list(fm.get("stage")),
        "labels": _coerce_list(fm.get("labels")),
        "paths": _coerce_list(fm.get("paths")),
        "ticket_type": _coerce_list(fm.get("ticket_type")),
    }
    return cna.matches_category(coerced, matcher)


# --------------------------------------------------------------------------- #
# Gate-state model (keyed on `stage: GATE-N` + `goal`)
# --------------------------------------------------------------------------- #

def gate_status(tickets: list[Ticket]) -> dict[str, dict[int, str]]:
    """Return ``{goal: {stage_no: 'done' | 'open'}}`` from the board's stage tickets.

    A goal's gate-N is ``'done'`` iff at least one stage-N ticket exists for that
    goal and every stage-N ticket for it is ``done``; otherwise ``'open'``. A stage
    with no ticket for a goal is simply absent (the caller treats an absent prior
    gate as "cannot verify → skip", mirroring ``check_gates``).
    """
    per: dict[str, dict[int, list[str]]] = {}
    for _path, fm in tickets:
        n = stage_of(fm)
        if n is None:
            continue
        goal = fm.get("goal", "").strip()
        if not goal:
            continue
        per.setdefault(goal, {}).setdefault(n, []).append(fm.get("status", "").strip())
    out: dict[str, dict[int, str]] = {}
    for goal, stages in per.items():
        out[goal] = {
            n: ("done" if statuses and all(s == "done" for s in statuses) else "open")
            for n, statuses in stages.items()
        }
    return out


def stage_ticket_ids(tickets: list[Ticket]) -> dict[str, dict[int, str]]:
    """Return ``{goal: {stage_no: representative ticket id}}`` (first seen wins)."""
    out: dict[str, dict[int, str]] = {}
    for _path, fm in tickets:
        n = stage_of(fm)
        if n is None:
            continue
        goal = fm.get("goal", "").strip()
        tid = fm.get("id", "").strip()
        if not goal or not tid:
            continue
        out.setdefault(goal, {}).setdefault(n, tid)
    return out


# --------------------------------------------------------------------------- #
# Rule 1 — gate order (no advancing past an open gate)
# --------------------------------------------------------------------------- #

def gate_order_violations(
    tickets: list[Ticket],
    gs: dict[str, dict[int, str]] | None = None,
) -> list[str]:
    """Return violations for stage-N tickets that advanced while GATE-(N-1) is open.

    A violation fires when a stage-N (N>=2) ticket is ``in_progress`` / ``in_review``
    / ``done`` while the same goal's stage-(N-1) is not ``done``. A stage with no
    prior-stage ticket is skipped (cannot verify). A ``todo``/``backlog`` stage
    ticket is never a violation — that is the legitimate gate-waiting state.
    """
    gs = gs if gs is not None else gate_status(tickets)
    violations: list[str] = []
    for _path, fm in tickets:
        n = stage_of(fm)
        if n is None or n < 2:
            continue
        status = fm.get("status", "").strip()
        if status not in ADVANCED_STATUSES:
            continue
        goal = fm.get("goal", "").strip()
        prior = gs.get(goal, {}).get(n - 1)
        if prior is None or prior == "done":
            continue
        tid = fm.get("id", _path.name)
        violations.append(
            f"{tid}: Stage-{n} ({STAGE_NAMES.get(n, '?')}) ticket is '{status}' but "
            f"GATE-{n - 1} ({STAGE_NAMES.get(n - 1, '?')}) for goal '{goal}' is open "
            f"— a stage may not advance past an open predecessor gate (AADL §0)"
        )
    return violations


# --------------------------------------------------------------------------- #
# Rule 2 — GATE-5 open ⇒ no production deploy
# --------------------------------------------------------------------------- #

def production_deploy_violations(
    tickets: list[Ticket],
    matcher: dict | None = None,
    gs: dict[str, dict[int, str]] | None = None,
) -> list[str]:
    """Return violations enforcing "GATE-5 open ⇒ NO production deploy".

    Two machine blocks over the ``gate5_deployment`` category (reused from the
    risk taxonomy):

    (a) A production-deploy ticket that is auto-approved (``approval: auto*``) —
        GATE-5 is never-auto-approve; a human (Founder) must sign the deployment
        gate (QONUN-5).
    (b) A production-deploy *action* (a gate5 ticket that does NOT itself carry
        ``stage: GATE-5`` — i.e. it is not the deployment-gate ticket) that has
        advanced while its goal's GATE-5 (Deployment) is open.
    """
    matcher = matcher if matcher is not None else load_gate5_matcher()
    if not matcher:
        return []
    gs = gs if gs is not None else gate_status(tickets)
    violations: list[str] = []
    for _path, fm in tickets:
        if not is_production_deploy(fm, matcher):
            continue
        tid = fm.get("id", _path.name)
        goal = fm.get("goal", "").strip()
        status = fm.get("status", "").strip()
        # (a) never-auto-approve: GATE-5 is human-only.
        if cna.is_auto_approved(fm):
            violations.append(
                f"{tid}: production-deploy ticket (gate5_deployment) is auto-approved — "
                f"GATE-5 is never-auto-approve; a human must sign the deployment gate (QONUN-5)"
            )
        # (b) gate-open block. Exclude the deployment-gate ticket itself (own stage 5):
        # its own completion is what CLOSES GATE-5, so it cannot be gated on itself.
        if stage_of(fm) == 5:
            continue
        g5 = gs.get(goal, {}).get(5)
        if g5 is not None and g5 != "done" and status in ADVANCED_STATUSES:
            violations.append(
                f"{tid}: production-deploy ticket is '{status}' but GATE-5 (Deployment) "
                f"for goal '{goal}' is open — no production deploy while GATE-5 is open"
            )
    return violations


def stage_gate_violations(
    tickets: list[Ticket],
    matcher: dict | None = None,
) -> list[str]:
    """Combined stage-gate rule (board_lint R12): gate order + GATE-5 deploy block."""
    gs = gate_status(tickets)
    out = gate_order_violations(tickets, gs)
    out.extend(production_deploy_violations(tickets, matcher, gs))
    return out


# --------------------------------------------------------------------------- #
# Gate walk (WS7 compile-time / delivery-time) + interrupt-card emission
# --------------------------------------------------------------------------- #

@dataclass
class GateWalk:
    """Result of walking a board's AADL gate order."""

    board_dir: Path
    gate_states: dict[str, dict[int, str]]
    order_violations: list[str] = field(default_factory=list)
    deploy_violations: list[str] = field(default_factory=list)
    # (goal, open_gate_stage, stage_ticket_id) for open gates that block a
    # downstream (stage N+1) that exists on the board.
    open_blocking_gates: list[tuple[str, int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff no violation blocks advancement (the board may advance)."""
        return not self.order_violations and not self.deploy_violations

    @property
    def violations(self) -> list[str]:
        return [*self.order_violations, *self.deploy_violations]


def walk_gates(
    board_dir: Path | str,
    matcher: dict | None = None,
) -> GateWalk:
    """Walk the AADL gate order over a compiled board; refuse to advance past an open gate."""
    board_dir = Path(board_dir)
    tickets = ck.load_tickets(board_dir)
    gs = gate_status(tickets)
    ids = stage_ticket_ids(tickets)
    order_v = gate_order_violations(tickets, gs)
    deploy_v = production_deploy_violations(tickets, matcher, gs)

    open_blocking: list[tuple[str, int, str]] = []
    for goal, stages in sorted(gs.items()):
        present = set(stages)
        for n in sorted(stages):
            if stages[n] != "done" and (n + 1) in present:
                open_blocking.append((goal, n, ids.get(goal, {}).get(n, "?")))

    return GateWalk(
        board_dir=board_dir,
        gate_states=gs,
        order_violations=order_v,
        deploy_violations=deploy_v,
        open_blocking_gates=open_blocking,
    )


def emit_gate_cards(
    walk: GateWalk,
    interrupts_dir: Path | str,
    created_by: str = "cto",
) -> list[Path]:
    """Emit an interrupt-card (DAS-1446 schema) for every open gate that blocks a stage.

    One card per ``(goal, open blocking gate)``, id ``<stage-ticket-id>-gate<N>``.
    Idempotent: an existing card file for the same key is left untouched (never
    overwritten, never double-emitted). Gates ALWAYS wait for the Founder — the
    card asks for a human sign-off; the machine never auto-answers (ADR-0027 SI-7).
    """
    out_dir = Path(interrupts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for goal, n, tid in walk.open_blocking_gates:
        if not _TICKET_ID_RE.match(str(tid)):
            continue  # interrupt schema requires ticket == ^DAS-[0-9]+$
        card_path = out_dir / f"{tid}-gate{n}.json"
        if card_path.exists():
            continue  # idempotent — do not re-emit or clobber
        card = {
            "question": (
                f"AADL GATE-{n} ({STAGE_NAMES.get(n, '?')}) for goal '{goal}' is open: "
                f"Stage-{n} is not signed off. Approve the gate to authorize "
                f"Stage-{n + 1} ({STAGE_NAMES.get(n + 1, '?')})?"
            ),
            "options": ["approve", "changes-requested", "hold"],
            "ticket": str(tid),
            "payload": {
                "kind": "aadl-gate-signoff",
                "goal": goal,
                "gate": f"GATE-{n}",
                "stage": n,
                "blocks_stage": n + 1,
                "never_auto_approve": n == 5,
            },
            "created_by": created_by,
        }
        card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        written.append(card_path)
    return written


# --------------------------------------------------------------------------- #
# Maintenance stage — recurring health/eval schedule (data, not an installer)
# --------------------------------------------------------------------------- #

def maintenance_schedule() -> dict:
    """Return the Maintenance-stage (GATE-6) recurring health/eval run descriptor.

    DATA only — it declares WHAT the Maintenance stage schedules (WS4 heartbeat +
    WS6 golden evals + ArcRift memory hygiene), never installs an OS scheduler
    entry (ADR-0027 SI-1: cadence lives in the Founder-owned launchd/cron entry).
    The runs are never-auto-approve: any acted change (tier promotion, gate
    re-open) still waits for a human (QONUN-5 / SI-7).
    """
    return {
        "gate": "GATE-6",
        "stage": 6,
        "never_auto_approve": True,
        "installs_os_scheduler_entry": False,
        "recurring_runs": [
            {
                "name": "health-tick",
                "kind": "ws4-heartbeat",
                "command": ["python3", "scripts/loop_controller.py", "--tick", "--trigger", "cron_tick"],
                "cadence": "hourly",
                "config": "board/schedule.yaml",
                "safety": "shadow-observe until heartbeat_enabled=true (ADR-0027 SI-7)",
            },
            {
                "name": "golden-eval",
                "kind": "ws6-eval",
                "command": ["python3", "scripts/agent_eval.py"],
                "cadence": "daily",
                "safety": "read-only scorecard; tier/model changes need GATE-6 human sign-off",
            },
            {
                "name": "memory-hygiene",
                "kind": "ws4-scheduled",
                "command": ["prune_memory"],
                "cadence": "weekly",
                "safety": "ArcRift prune of stale/incorrect memories (Persistent Memory Law)",
            },
            {
                "name": "ws-a-tool-edge-health",
                "kind": "ws-a-eval",
                "command": ["python3", "scripts/ws_a_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-a-tool-edge-health.md",
                "safety": "read-only allow-list-drift + redaction probe (ADR-0033 GATE-6, "
                          "DAS-1551); a non-zero exit is an ALERT routed to a follow-up "
                          "ticket, never silently retried or auto-fixed",
            },
            {
                "name": "ws-b-runner-health",
                "kind": "ws-b-eval",
                "command": ["python3", "scripts/ws_b_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-b-runner-health.md",
                "safety": "read-only dispatch-equivalence drift (single run_wave() caller + "
                          "ledger reconciliation) + budget-ceiling drift (mustaqil: SI-5 caps "
                          "and metered_overflow: false intact) (ADR-0034 GATE-6, DAS-1559); a "
                          "non-zero exit is an ALERT routed to a follow-up ticket, never "
                          "silently retried or auto-fixed",
            },
        ],
    }


# --------------------------------------------------------------------------- #
# Rendering + CLI
# --------------------------------------------------------------------------- #

def render_walk(walk: GateWalk) -> str:
    out: list[str] = []
    out.append(f"AADL gate walk — {walk.board_dir}")
    out.append("=" * 60)
    if not walk.gate_states:
        out.append("  (no stage-tagged tickets on this board)")
    for goal, stages in sorted(walk.gate_states.items()):
        cells = "  ".join(f"GATE-{n}:{stages[n]}" for n in sorted(stages))
        out.append(f"  {goal}: {cells}")
    if walk.open_blocking_gates:
        out.append("\nOpen gates blocking a downstream stage (Founder sign-off needed):")
        for goal, n, tid in walk.open_blocking_gates:
            out.append(f"  - {goal}: GATE-{n} open ({tid}) blocks Stage-{n + 1}")
    if walk.violations:
        out.append(f"\nBLOCKED — {len(walk.violations)} gate violation(s):")
        for v in walk.violations:
            out.append(f"  FAIL  {v}")
    else:
        out.append("\nOK — board may advance (no gate violation).")
    return "\n".join(out)


def _as_dict(walk: GateWalk) -> dict:
    return {
        "board_dir": str(walk.board_dir),
        "ok": walk.ok,
        "gate_states": {g: {str(n): s for n, s in st.items()} for g, st in walk.gate_states.items()},
        "order_violations": walk.order_violations,
        "deploy_violations": walk.deploy_violations,
        "open_blocking_gates": [
            {"goal": g, "gate": n, "ticket": tid} for g, n, tid in walk.open_blocking_gates
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("board_dir", help="a compiled board directory (projects/<name>/board-tickets/)")
    ap.add_argument("--emit-cards", action="store_true",
                    help="emit gate interrupt-cards for open blocking gates (DAS-1446)")
    ap.add_argument("--interrupts", default=None,
                    help="interrupt-card output dir (default: board/interrupts/)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    board = Path(args.board_dir)
    if not board.is_dir():
        print(f"ERROR: board dir not found: {board}", file=sys.stderr)
        return 2

    walk = walk_gates(board)
    if args.emit_cards:
        interrupts = Path(args.interrupts) if args.interrupts else (ROOT / "board" / "interrupts")
        emit_gate_cards(walk, interrupts)

    if args.json:
        print(json.dumps(_as_dict(walk), indent=2))
    else:
        print(render_walk(walk))
    return 0 if walk.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
