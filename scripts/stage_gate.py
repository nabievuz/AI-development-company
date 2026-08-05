#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _paths import ROOT


_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import check_gates as ck
import check_never_auto_approve as cna


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


_STAGE_FIELD_RE = re.compile(r"GATE-([1-6])", re.IGNORECASE)
_TICKET_ID_RE = re.compile(r"^DAS-\d+$")

Ticket = tuple[Path, dict[str, str]]


def stage_of(fm: dict[str, str]) -> int | None:
    m = _STAGE_FIELD_RE.search(str(fm.get("stage", "")))
    return int(m.group(1)) if m else None


def _coerce_list(raw: object) -> list[str]:
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
    try:
        import yaml
    except ImportError:
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
    if not matcher:
        return False
    coerced = {
        "stage": _coerce_list(fm.get("stage")),
        "labels": _coerce_list(fm.get("labels")),
        "paths": _coerce_list(fm.get("paths")),
        "ticket_type": _coerce_list(fm.get("ticket_type")),
    }
    return cna.matches_category(coerced, matcher)


def gate_status(tickets: list[Ticket]) -> dict[str, dict[int, str]]:
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


def gate_order_violations(
    tickets: list[Ticket],
    gs: dict[str, dict[int, str]] | None = None,
) -> list[str]:
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


def production_deploy_violations(
    tickets: list[Ticket],
    matcher: dict | None = None,
    gs: dict[str, dict[int, str]] | None = None,
) -> list[str]:
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

        if cna.is_auto_approved(fm):
            violations.append(
                f"{tid}: production-deploy ticket (gate5_deployment) is auto-approved — "
                f"GATE-5 is never-auto-approve; a human must sign the deployment gate (QONUN-5)"
            )


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
    gs = gate_status(tickets)
    out = gate_order_violations(tickets, gs)
    out.extend(production_deploy_violations(tickets, matcher, gs))
    return out


@dataclass
class GateWalk:

    board_dir: Path
    gate_states: dict[str, dict[int, str]]
    order_violations: list[str] = field(default_factory=list)
    deploy_violations: list[str] = field(default_factory=list)


    open_blocking_gates: list[tuple[str, int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.order_violations and not self.deploy_violations

    @property
    def violations(self) -> list[str]:
        return [*self.order_violations, *self.deploy_violations]


def walk_gates(
    board_dir: Path | str,
    matcher: dict | None = None,
) -> GateWalk:
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
    out_dir = Path(interrupts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for goal, n, tid in walk.open_blocking_gates:
        if not _TICKET_ID_RE.match(str(tid)):
            continue
        card_path = out_dir / f"{tid}-gate{n}.json"
        if card_path.exists():
            continue
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


def maintenance_schedule() -> dict:
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
                "config": "docs/06-maintenance/golden-eval.md",
                "safety": "read-only scorecard; tier/model changes need GATE-6 human sign-off",
            },
            {
                "name": "memory-hygiene",
                "kind": "ws4-scheduled",
                "command": ["prune_memory"],
                "cadence": "weekly",
                "config": "docs/06-maintenance/memory-hygiene.md",
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
            {
                "name": "ws-d-lens-health",
                "kind": "ws-d-eval",
                "command": ["python3", "scripts/ws_d_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-d-lens-health.md",
                "safety": "read-only exporter redaction-on-export probe + in-tenant target "
                          "check (langfuse_observability) + promptfoo/AgentShield/Presidio "
                          "allow-list drift (ADR-0036/ADR-0033 GATE-6, DAS-1577); a non-zero "
                          "exit is an ALERT routed to a follow-up ticket, never silently "
                          "retried or auto-fixed",
            },
            {
                "name": "ws-c-loop-health",
                "kind": "ws-c-eval",
                "command": ["python3", "scripts/ws_c_loop_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-c-loop-health.md",
                "safety": "read-only board-canonical reconcile drift (checkpoint never a "
                          "tiebreaker) + sandbox fail-closed-wall drift (host/cross-task/"
                          "unscoped-credential/egress) + import-ban carve-out drift "
                          "(ADR-0035 langgraph confined to scripts/dgox/) (ADR-0035 GATE-6, "
                          "DAS-1569); a non-zero exit is an ALERT routed to a follow-up "
                          "ticket, never silently retried or auto-fixed",
            },
            {
                "name": "ws-e-tenant-health",
                "kind": "ws-e-eval",
                "command": ["python3", "scripts/ws_e_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-e-tenant-health.md",
                "safety": "read-only RBAC-grant drift (gate.approve/config.edit.security "
                          "stay founder-only; agent:* still denied gate.approve) + gateway "
                          "TN-1 host-pin drift (a rogue role=model host stays refused) + "
                          "in-tenant precondition drift (check_in_tenant.py) + guardrail/"
                          "golden-set eval drift (Presidio redaction + no-pass-is-RED) "
                          "(ADR-0038/ADR-0033 GATE-6, DAS-1587); a non-zero exit is an "
                          "ALERT routed to a follow-up ticket, never silently retried or "
                          "auto-fixed",
            },
            {
                "name": "ws-h-control-health",
                "kind": "ws-h-eval",
                "command": ["python3", "scripts/ws_h_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-h-control-health.md",
                "safety": "read-only RBAC-grant drift (gate.approve/run.trigger stay "
                          "founder-only; agent:* still denied both) + audit-redaction "
                          "drift (the ADR-0012 scrubber still redacts a secret-shaped "
                          "probe) + degrade/flag drift (ws_h_control_plane defaults OFF; "
                          "degrade-to-static holds flag-off and force-static) + "
                          "token-compare drift (_match_token still uses "
                          "hmac.compare_digest, no bare dict .get() regression) "
                          "(ADR-0039/ADR-0033 GATE-6, DAS-1605); a non-zero exit is an "
                          "ALERT routed to a follow-up ticket, never silently retried or "
                          "auto-fixed",
            },
            {
                "name": "ws-a2a-outbound-health",
                "kind": "ws-a2a-eval",
                "command": ["python3", "scripts/ws_a2a_health_check.py", "--json"],
                "cadence": "daily",
                "config": "docs/06-maintenance/ws-a2a-outbound-health.md",
                "safety": "read-only in-tenant boundary drift (check_in_tenant.py, SC-003) "
                          "+ flag/publish-state drift (a2a_outbound vs the newest logged "
                          "a2a_publish event in board/.events.jsonl; flag OFF with zero "
                          "events is the honest baseline, reported OK-with-zero-events) + "
                          "negative-test drift (DAS-1612's suite still green) "
                          "(ADR-0040 GATE-6, DAS-1614/DAS-1624); a non-zero exit is an "
                          "ALERT routed to a follow-up ticket, never silently retried or "
                          "auto-fixed; a2a_outbound is never flipped by this check "
                          "(publish stays a Founder-only act, QONUN-5/FR-003)",
            },
        ],
    }


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
        description="stage_gate.py — machine-enforced stage-gated delivery (P22 / DAS-1494).\n\nDasLab already mandates the six-stage AI-agent lifecycle\n(``Planning → Design → Development → Testing → Deployment → Maintenance`` —\n``governance/policies/ai-agent-lifecycle.md``) and a never-auto-approve law for\nthe deployment gate (``gate5_deployment`` in ``config/risk_taxonomy.yaml``). This\nmodule supplies the **end-to-end machine enforcement** that turns the documented\ngate order into a hard block, so a project board is provably *executed through the\nAADL gates* rather than advanced by convention:\n\n- **Gate order** — a stage-N ticket may not *advance* (reach ``in_progress`` /\n  ``in_review`` / ``done``) while GATE-(N-1) is still open (the same goal's\n  stage-(N-1) work is not ``done``). A ``todo`` / ``backlog`` stage-N ticket is a\n  legitimate *waiting* state and is NOT a violation — only advancing past an open\n  gate is (``gate_order_violations``).\n- **GATE-5 ⇒ no production deploy** — a production-deploy ticket (classified\n  against the *existing* ``gate5_deployment`` risk category, not a new path) must\n  not be auto-approved (GATE-5 is human-only, QONUN-5) and must not advance while\n  its goal's GATE-5 (Deployment) is open (``production_deploy_violations``).\n- **Gate walk** — ``walk_gates`` reads a compiled project board\n  (``projects/<name>/board-tickets/``), computes each goal's gate states, and\n  refuses to advance past an open gate. Open gates that block downstream stages\n  are surfaced as **interrupt-cards** (``emit_gate_cards`` → ``board/interrupts/``,\n  DAS-1446 schema) so the Founder — never the machine — signs the gate.\n- **Maintenance** — ``maintenance_schedule`` declares the recurring health/eval\n  runs the Maintenance stage (GATE-6) owns: the WS4 heartbeat tick and the WS6\n  golden-eval harness. It is DATA (a descriptor), not an installer — cadence lives\n  in the Founder-owned OS scheduler entry (ADR-0027 SI-1); nothing here deploys.\n\nThe gate model keys off the ``stage: GATE-N`` frontmatter field that\n``gateway_compile.py`` stamps on every story ticket, plus the ticket's ``goal``.\nIt reuses ``check_gates`` (ticket loader / frontmatter parser) and\n``check_never_auto_approve`` (the ``gate5_deployment`` matcher + auto-approval\ndetector) — no parallel classification path.\n\nUsage::\n\n    python3 scripts/stage_gate.py <board-dir> [--emit-cards] [--interrupts DIR] [--json]\n\n``<board-dir>`` is a compiled board directory (``projects/<name>/board-tickets/``).\nExit codes: 0 = board may advance (no gate violation), 1 = an open-gate violation\nblocks advancement, 2 = usage / IO error.", formatter_class=argparse.RawDescriptionHelpFormatter
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
