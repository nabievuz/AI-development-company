#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from _paths import ROOT


_FLOWS_DEFAULT: Path = ROOT / "governance" / "communication-flows.yaml"
_TICKETS_DEFAULT: Path = ROOT / "board" / "tickets"


_SEP_RE = re.compile(r"\s*(?:->|→|>)\s*")


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_ROUTES_FIELD_RE = re.compile(r"^routes:\s*(.+?)\s*$", re.MULTILINE)


class InputError(RuntimeError):
    pass


def load_declared_routes(flows_path: Path) -> set[tuple[str, str]]:
    if not flows_path.exists():
        raise InputError(f"flows file not found: {flows_path}")
    try:
        data = yaml.safe_load(flows_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise InputError(f"cannot read/parse {flows_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError(f"{flows_path}: top level must be a mapping")
    flows = data.get("flows")
    if not isinstance(flows, list) or not flows:
        raise InputError(f"{flows_path}: 'flows' must be a non-empty list")
    declared: set[tuple[str, str]] = set()
    for edge in flows:
        if not isinstance(edge, dict):
            continue
        sender = edge.get("sender")
        receiver = edge.get("receiver")
        if sender and receiver:
            declared.add((str(sender), str(receiver)))
    if not declared:
        raise InputError(f"{flows_path}: no (sender, receiver) edges found")
    return declared


def parse_route_token(token: str) -> tuple[str, str]:
    parts = [p.strip().strip("`'\"").strip() for p in _SEP_RE.split(token.strip())]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"bad route token {token!r}: expected 'sender>receiver'"
        )
    return (parts[0], parts[1])


def extract_ticket_routes(text: str) -> list[tuple[str, str]]:
    m = _FM_RE.match(text)
    block = m.group(1) if m else text
    fm = _ROUTES_FIELD_RE.search(block)
    if not fm:
        return []
    raw = fm.group(1).strip().strip("[]").strip()
    if not raw:
        return []
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    return [parse_route_token(t) for t in tokens]


def load_dispatch_routes(dispatch_path: Path) -> list[tuple[str, str]]:
    try:
        data = json.loads(dispatch_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read/parse dispatch file {dispatch_path}: {exc}") from exc
    if not isinstance(data, list):
        raise InputError(f"{dispatch_path}: dispatch file must be a JSON list")
    pairs: list[tuple[str, str]] = []
    for i, rec in enumerate(data):
        if not isinstance(rec, dict) or "sender" not in rec or "receiver" not in rec:
            raise InputError(
                f"{dispatch_path}[{i}]: each record needs 'sender' and 'receiver'"
            )
        pairs.append((str(rec["sender"]), str(rec["receiver"])))
    return pairs


def check_routes(
    refs: list[tuple[str, tuple[str, str]]],
    declared: set[tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    for origin, (sender, receiver) in refs:
        if (sender, receiver) not in declared:
            errors.append(
                f"{origin}: undeclared route ({sender} -> {receiver}) — "
                "not in governance/communication-flows.yaml"
            )
    return errors


def scan_tickets(tickets_dir: Path) -> tuple[list[tuple[str, tuple[str, str]]], list[str]]:
    refs: list[tuple[str, tuple[str, str]]] = []
    errors: list[str] = []
    for path in sorted(tickets_dir.glob("*.md")):
        try:
            pairs = extract_ticket_routes(path.read_text(encoding="utf-8"))
        except OSError as exc:
            errors.append(f"{path.name}: cannot read ticket — {exc}")
            continue
        except ValueError as exc:
            errors.append(f"{path.name}: malformed routes: field — {exc}")
            continue
        for pair in pairs:
            refs.append((path.name, pair))
    return refs, errors


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_comm_flows",
        description='check_comm_flows.py — reject any ticket/dispatch referencing an undeclared route.\n\n`governance/communication-flows.yaml` is the single source of truth for the closed\nset of allowed ``(sender, receiver)`` communication routes (ADR-0026, authored and\nshape-validated by DAS-1465 / `scripts/validate_commflows.py`). This validator is\nthe *enforcement* half of the LOOM fabric (WS2 O2-T03, DAS-1466 §5 row 9): it FAILS\n(exit 1) any ticket or dispatch that references a ``(sender, receiver)`` pair which\nis **not** declared in that file. The structural half — compiling each role\'s allowed\noutbound routes into its `.claude/agents/<role>.md` shim so an undeclared route is\nunrepresentable — lives in `scripts/gen_subagents.py`; this script catches anything\nthat slips past the structure.\n\nWhat counts as a route reference\n--------------------------------\n* **Ticket** — a `routes:` frontmatter field listing one or more route tokens\n  (``sender>receiver`` / ``sender->receiver`` / ``sender→receiver``, a single token\n  or a bracketed/comma list). Tickets that declare no `routes:` field reference no\n  route and are trivially clean — so the whole board passes today.\n* **Dispatch** — an explicit ``--route sender>receiver`` (repeatable) and/or a\n  ``--dispatch FILE.json`` holding a JSON list of ``{"sender": ..., "receiver": ...}``\n  records. The orchestrator calls this before wiring a cross-role message.\n\nAn undeclared pair is one absent from the flows file — including a pair to an unknown\nrole. `kind` (delegation/escalation) is *not* part of the key: a route is the ordered\npair, and being declared in either direction is what this validator checks.\n\nUsage::\n\n    python3 scripts/check_comm_flows.py                      # scan board/tickets/*.md\n    python3 scripts/check_comm_flows.py --route backend-em>cto\n    python3 scripts/check_comm_flows.py --dispatch wave.json\n    python3 scripts/check_comm_flows.py --flows F --tickets T\n\n    --flows    PATH  Path to governance/communication-flows.yaml (default: auto).\n    --tickets  PATH  Path to board/tickets/ directory (default: auto). Scanned only\n                     when no --route/--dispatch is given (ticket mode vs dispatch mode).\n    --route    TOK   A route token to validate; repeatable (dispatch mode).\n    --dispatch PATH  JSON file of [{"sender","receiver"}, ...] records (dispatch mode).\n\nExit codes: 0 = every referenced route is declared, 1 = an undeclared route was\nreferenced, 2 = usage / IO error (flows file unreadable, bad --route token, …).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--flows",
        type=Path,
        default=_FLOWS_DEFAULT,
        help="Path to governance/communication-flows.yaml (default: auto-detected)",
    )
    p.add_argument(
        "--tickets",
        type=Path,
        default=_TICKETS_DEFAULT,
        help="Path to board/tickets/ (scanned only in ticket mode; default: auto)",
    )
    p.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="SENDER>RECEIVER",
        help="A route token to validate (repeatable); switches to dispatch mode",
    )
    p.add_argument(
        "--dispatch",
        type=Path,
        default=None,
        help="JSON file of [{'sender','receiver'}] dispatch records (dispatch mode)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)


    try:
        declared = load_declared_routes(args.flows)
    except InputError as exc:
        print(f"check_comm_flows: {exc}", file=sys.stderr)
        return 2

    refs: list[tuple[str, tuple[str, str]]] = []
    errors: list[str] = []
    dispatch_mode = bool(args.route) or args.dispatch is not None

    if dispatch_mode:
        for tok in args.route:
            try:
                refs.append((f"--route {tok}", parse_route_token(tok)))
            except ValueError as exc:
                print(f"check_comm_flows: {exc}", file=sys.stderr)
                return 2
        if args.dispatch is not None:
            try:
                for pair in load_dispatch_routes(args.dispatch):
                    refs.append((f"{args.dispatch.name} {pair[0]}>{pair[1]}", pair))
            except InputError as exc:
                print(f"check_comm_flows: {exc}", file=sys.stderr)
                return 2
    else:
        if not args.tickets.is_dir():
            print(f"check_comm_flows: tickets dir not found: {args.tickets}", file=sys.stderr)
            return 2
        scanned, scan_errs = scan_tickets(args.tickets)
        refs.extend(scanned)
        errors.extend(scan_errs)

    errors.extend(check_routes(refs, declared))

    if errors:
        print(
            f"check_comm_flows: {len(errors)} undeclared-route violation(s):\n",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  FAIL  {e}", file=sys.stderr)
        return 1

    scope = "dispatch" if dispatch_mode else "board/tickets"
    print(
        f"check_comm_flows: OK — {len(refs)} referenced route(s) across {scope} "
        f"all declared in {args.flows.name} ({len(declared)} routes)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
