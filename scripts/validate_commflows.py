#!/usr/bin/env python3
"""validate_commflows.py — shape + derivation validator for communication-flows.yaml.

`governance/communication-flows.yaml` is a **derived, validatable** projection of
the org communication graph (ADR-0026). Every edge MUST trace to one of the
authoritative SSOTs; no topology is authored by hand. This script is the small
shape/derivation validator that ADR-0026 §Enforcement calls the contract for the
authored file (WS2 O2-T02, ticket DAS-1465). It is deliberately scoped to the
*shape* of the file and its round-trip derivation from `board/ROUTING.md`; the
fuller drift diff-check (`check_comm_flows.py`) is a later ticket (WS2 O2-T03).

File shape (ADR-0026 §1)
------------------------
    version: <int >= 1>
    flows:
      - sender:   <fleet role key from board/ROUTING.md>
        receiver: <fleet role key from board/ROUTING.md>
        kind:     delegation | escalation
        source:   routing.reports_to | schema.escalation

Closed enums
------------
* ``kind``   ∈ {``delegation``, ``escalation``} exactly. ``delegation`` runs DOWN
  the reporting chain (manager → direct report); ``escalation`` runs UP it
  (report → manager). RACI *consult* edges are **out of scope for v1** per
  ADR-0026 §Consequences — a possible future ``kind``, not emitted now.
* ``source`` ∈ {``routing.reports_to``, ``schema.escalation``}.
* ``sender`` / ``receiver`` MUST be fleet role keys present in ``board/ROUTING.md``.
  The string ``founder`` is **forbidden** as a sender or receiver: the founder is
  an external human gate above the chairman, not a routing node (ADR-0026 §3).

Derivation rules enforced (ADR-0026 §1 rules 1–4)
-------------------------------------------------
1. Role-node closure — every sender/receiver is a fleet role in ROUTING.md;
   ``founder`` never appears.
2. Reporting-line completeness + soundness — for each ROUTING.md row
   ``report → manager`` whose reviewer is a fleet role (not ``—``), the file
   contains EXACTLY the two edges
   ``delegation(manager → report)`` and ``escalation(report → manager)``,
   both ``source: routing.reports_to`` — no more, no fewer, no duplicates.
   Roles whose reviewer is ``—`` (``chairman``, ``board-member``) have no upward
   fleet edge; the chain terminates at the top of the fleet.
3. Escalation-ladder consistency — the ``schema.routing.escalation`` ladder is
   present and terminates in the external ``founder`` rung; no fleet edge is
   emitted for that rung.
4. No invented topology — the authored edge set equals the set derived purely
   from the SSOTs. Any extra or missing edge is an error.

Usage
-----
    python3 scripts/validate_commflows.py            # validate the authored file
    python3 scripts/validate_commflows.py --emit     # print the canonical YAML
    python3 scripts/validate_commflows.py --file P    # validate an explicit path

Exit codes
----------
0  the file is a sound derived projection of the SSOTs
1  a validation error (bad shape, bad enum, dangling role, invented/missing edge)
2  usage / environment error (a source SSOT is unreadable)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from _paths import ROOT

ROUTING_MD: Path = ROOT / "board" / "ROUTING.md"
SCHEMA_YAML: Path = ROOT / "org" / "schema.daslab.yaml"
FLOWS_YAML: Path = ROOT / "governance" / "communication-flows.yaml"

KINDS: frozenset[str] = frozenset({"delegation", "escalation"})
SOURCES: frozenset[str] = frozenset({"routing.reports_to", "schema.escalation"})
EDGE_KEYS: frozenset[str] = frozenset({"sender", "receiver", "kind", "source"})
FOUNDER: str = "founder"

# One table row: | `role-key` | Display Name | dept | Reviewer Display Name |
_ROW = re.compile(
    r"^\|\s*`(?P<key>[a-z0-9-]+)`\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<dept>[^|]+?)\s*\|\s*(?P<reviewer>[^|]+?)\s*\|\s*$"
)
_NO_REVIEWER = {"—", "-", ""}


class SourceError(RuntimeError):
    """A source SSOT could not be read/parsed (environment error → exit 2)."""


def _parse_routing() -> tuple[list[str], dict[str, str]]:
    """Parse ROUTING.md → (ordered fleet role keys, role_key → manager_key or '').

    The reviewer column holds display names; they are resolved back to role keys
    via the table's own (key, display-name) columns, so the mapping is derived,
    never hand-written.
    """
    try:
        text = ROUTING_MD.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - environment error
        raise SourceError(f"cannot read {ROUTING_MD}: {exc}") from exc

    order: list[str] = []
    name_to_key: dict[str, str] = {}
    reviewer_name: dict[str, str] = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        key = m.group("key")
        name = m.group("name").strip()
        # Skip the header separator / header row (no backticked key matches those).
        order.append(key)
        name_to_key[name] = key
        reviewer_name[key] = m.group("reviewer").strip()

    if not order:  # pragma: no cover - environment error
        raise SourceError(f"no role rows parsed from {ROUTING_MD}")

    manager: dict[str, str] = {}
    for key in order:
        rev = reviewer_name[key]
        if rev in _NO_REVIEWER:
            manager[key] = ""
            continue
        mgr_key = name_to_key.get(rev)
        if mgr_key is None:
            raise SourceError(
                f"reviewer {rev!r} for role {key!r} is not a known display name "
                f"in {ROUTING_MD}"
            )
        manager[key] = mgr_key
    return order, manager


def _parse_escalation_ladder() -> list[str]:
    try:
        data = yaml.safe_load(SCHEMA_YAML.read_text(encoding="utf-8"))
    except OSError as exc:  # pragma: no cover - environment error
        raise SourceError(f"cannot read {SCHEMA_YAML}: {exc}") from exc
    ladder = (data or {}).get("routing", {}).get("escalation")
    if not isinstance(ladder, list) or not ladder:
        raise SourceError(f"routing.escalation missing/empty in {SCHEMA_YAML}")
    return [str(x) for x in ladder]


# An edge is a canonical (sender, receiver, kind, source) tuple for set compares.
Edge = tuple[str, str, str, str]


def derive_expected_edges() -> list[Edge]:
    """The canonical edge set, a pure function of ROUTING.md (ADR-0026 rule 2).

    Row order is preserved; per row, delegation precedes escalation. This is the
    single source the authored YAML is generated from and diffed against.
    """
    order, manager = _parse_routing()
    edges: list[Edge] = []
    for report in order:
        mgr = manager[report]
        if not mgr:  # reviewer is '—' → top of fleet, no upward edge
            continue
        edges.append((mgr, report, "delegation", "routing.reports_to"))
        edges.append((report, mgr, "escalation", "routing.reports_to"))
    return edges


def emit_yaml() -> str:
    """Render the canonical communication-flows.yaml text from the SSOTs."""
    ladder = _parse_escalation_ladder()
    edges = derive_expected_edges()
    lines: list[str] = [
        "# governance/communication-flows.yaml",
        "# DERIVED + VALIDATABLE view of the org communication graph (ADR-0026).",
        "# Every edge is a (sender -> receiver) ordered pair mechanically derived",
        "# from board/ROUTING.md reporting lines; NEVER hand-author new topology",
        "# here. Regenerate with:  python3 scripts/validate_commflows.py --emit",
        "# Validated by scripts/validate_commflows.py (WS2 O2-T02, DAS-1465).",
        "#",
        "# founder is an EXTERNAL human gate above the chairman, not a routing",
        f"# node: the escalation ladder is {ladder!r} but its terminal 'founder'",
        "# rung produces NO fleet edge (ADR-0026 section 3). consult edges are",
        "# deferred to a future kind (ADR-0026 Consequences); v1 is delegation +",
        "# escalation only.",
        "version: 1",
        "flows:",
    ]
    for sender, receiver, kind, source in edges:
        lines.append(f"  - sender: {sender}")
        lines.append(f"    receiver: {receiver}")
        lines.append(f"    kind: {kind}")
        lines.append(f"    source: {source}")
    return "\n".join(lines) + "\n"


def _load_flows(path: Path) -> tuple[object, list[object]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SourceError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SourceError(f"{path}: top level must be a mapping")
    return data.get("version"), data.get("flows")


def validate(path: Path) -> list[str]:
    """Return a list of human-readable errors ([] means the file is valid)."""
    errors: list[str] = []
    version, flows = _load_flows(path)

    if not isinstance(version, int) or version < 1:
        errors.append(f"version must be an integer >= 1 (got {version!r})")
    if not isinstance(flows, list) or not flows:
        errors.append("flows must be a non-empty list")
        return errors  # nothing else is checkable

    seen: set[Edge] = set()
    file_edges: set[Edge] = set()
    for i, edge in enumerate(flows):
        where = f"flows[{i}]"
        if not isinstance(edge, dict):
            errors.append(f"{where}: each flow must be a mapping")
            continue
        keys = set(edge)
        if keys != EDGE_KEYS:
            missing = EDGE_KEYS - keys
            extra = keys - EDGE_KEYS
            if missing:
                errors.append(f"{where}: missing field(s) {sorted(missing)}")
            if extra:
                errors.append(f"{where}: unknown field(s) {sorted(extra)}")
            continue
        sender = edge["sender"]
        receiver = edge["receiver"]
        kind = edge["kind"]
        source = edge["source"]
        if kind not in KINDS:
            errors.append(f"{where}: kind {kind!r} not in {sorted(KINDS)}")
        if source not in SOURCES:
            errors.append(f"{where}: source {source!r} not in {sorted(SOURCES)}")
        if FOUNDER in (sender, receiver):
            errors.append(
                f"{where}: founder is an external gate, never a sender/receiver "
                "(ADR-0026 section 3)"
            )
        if sender == receiver:
            errors.append(f"{where}: sender and receiver are identical ({sender!r})")
        etuple: Edge = (sender, receiver, kind, source)
        if etuple in seen:
            errors.append(f"{where}: duplicate edge {etuple}")
        seen.add(etuple)
        file_edges.add(etuple)

    # Role-node closure + no-invented-topology + completeness, in one set diff.
    try:
        order, _ = _parse_routing()
        fleet = set(order)
        expected = set(derive_expected_edges())
    except SourceError as exc:
        errors.append(str(exc))
        return errors

    for sender, receiver, _kind, _source in file_edges:
        if sender not in fleet:
            errors.append(f"dangling sender role {sender!r} (not in ROUTING.md)")
        if receiver not in fleet:
            errors.append(f"dangling receiver role {receiver!r} (not in ROUTING.md)")

    invented = file_edges - expected
    for edge in sorted(invented):
        errors.append(f"invented edge (no ROUTING.md reporting line): {edge}")
    missing = expected - file_edges
    for edge in sorted(missing):
        errors.append(f"missing derived edge: {edge}")

    # Escalation-ladder consistency: ladder present, founder is terminal + external.
    try:
        ladder = _parse_escalation_ladder()
    except SourceError as exc:
        errors.append(str(exc))
        return errors
    if FOUNDER not in ladder:
        errors.append(f"schema.routing.escalation lacks the terminal {FOUNDER!r} rung")
    elif ladder[-1] != FOUNDER:
        errors.append(f"{FOUNDER!r} must be the terminal escalation rung, got {ladder}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_commflows.py", description=__doc__)
    parser.add_argument(
        "--emit",
        action="store_true",
        help="print the canonical communication-flows.yaml derived from the SSOTs",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=FLOWS_YAML,
        help="path to the communication-flows.yaml to validate",
    )
    args = parser.parse_args(argv)

    try:
        if args.emit:
            sys.stdout.write(emit_yaml())
            return 0
        errors = validate(args.file)
    except SourceError as exc:
        print(f"validate_commflows: environment error: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"validate_commflows: {len(errors)} error(s) in {args.file}:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(
        f"validate_commflows: OK — {args.file.name} is a sound derived "
        "projection of ROUTING.md (delegation + escalation edges)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
