#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import org_model
import yaml
from _paths import ROOT

ROUTING_MD: Path = ROOT / "board" / "ROUTING.md"
ROUTING_SOURCE: str = "config/org.yaml"
SCHEMA_YAML: Path = ROOT / "org" / "schema.daslab.yaml"
FLOWS_YAML: Path = ROOT / "governance" / "communication-flows.yaml"

KINDS: frozenset[str] = frozenset({"delegation", "escalation"})
SOURCES: frozenset[str] = frozenset({"routing.reports_to", "schema.escalation"})
EDGE_KEYS: frozenset[str] = frozenset({"sender", "receiver", "kind", "source"})
FOUNDER: str = "founder"


_ROW = re.compile(
    r"^\|\s*`(?P<key>[a-z0-9-]+)`\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<dept>[^|]+?)\s*\|\s*(?P<reviewer>[^|]+?)\s*\|\s*$"
)
_NO_REVIEWER = {"—", "-", ""}


class SourceError(RuntimeError):
    pass


def _parse_legacy_routing_markdown(path: Path) -> tuple[list[str], dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceError(f"cannot read {path}: {exc}") from exc

    order: list[str] = []
    name_to_key: dict[str, str] = {}
    reviewer_name: dict[str, str] = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        key = m.group("key")
        name = m.group("name").strip()

        order.append(key)
        name_to_key[name] = key
        reviewer_name[key] = m.group("reviewer").strip()

    if not order:
        raise SourceError(f"no role rows parsed from {path}")

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
                f"in {path}"
            )
        manager[key] = mgr_key
    return order, manager


def _parse_routing() -> tuple[list[str], dict[str, str]]:
    if ROUTING_MD.is_file():
        return _parse_legacy_routing_markdown(ROUTING_MD)
    try:
        table = org_model.routing_table()
    except org_model.OrgConfigError as exc:
        raise SourceError(f"cannot read the org routing table: {exc}") from exc
    if not table:
        raise SourceError(f"{ROUTING_SOURCE} declares no roles")
    order = [r.role for r in table]
    manager = {r.role: (r.reviewer or "") for r in table}
    for key, mgr in manager.items():
        if mgr and mgr not in manager:
            raise SourceError(
                f"reviewer {mgr!r} for role {key!r} is not a known role key "
                f"in {ROUTING_SOURCE}"
            )
    return order, manager


def _parse_escalation_ladder() -> list[str]:
    try:
        data = yaml.safe_load(SCHEMA_YAML.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SourceError(f"cannot read {SCHEMA_YAML}: {exc}") from exc
    ladder = (data or {}).get("routing", {}).get("escalation")
    if not isinstance(ladder, list) or not ladder:
        raise SourceError(f"routing.escalation missing/empty in {SCHEMA_YAML}")
    return [str(x) for x in ladder]


Edge = tuple[str, str, str, str]


def derive_expected_edges() -> list[Edge]:
    order, manager = _parse_routing()
    edges: list[Edge] = []
    for report in order:
        mgr = manager[report]
        if not mgr:
            continue
        edges.append((mgr, report, "delegation", "routing.reports_to"))
        edges.append((report, mgr, "escalation", "routing.reports_to"))
    return edges


def emit_yaml() -> str:
    ladder = _parse_escalation_ladder()
    edges = derive_expected_edges()
    if FOUNDER not in ladder or ladder[-1] != FOUNDER:
        raise SourceError(
            f"{FOUNDER!r} must be the terminal escalation rung, got {ladder}"
        )
    lines: list[str] = [
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
    errors: list[str] = []
    version, flows = _load_flows(path)

    if not isinstance(version, int) or version < 1:
        errors.append(f"version must be an integer >= 1 (got {version!r})")
    if not isinstance(flows, list) or not flows:
        errors.append("flows must be a non-empty list")
        return errors

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


    try:
        order, _ = _parse_routing()
        fleet = set(order)
        expected = set(derive_expected_edges())
    except SourceError as exc:
        errors.append(str(exc))
        return errors

    for sender, receiver, _kind, _source in file_edges:
        if sender not in fleet:
            errors.append(f"dangling sender role {sender!r} (not in {ROUTING_SOURCE})")
        if receiver not in fleet:
            errors.append(f"dangling receiver role {receiver!r} (not in {ROUTING_SOURCE})")

    invented = file_edges - expected
    for edge in sorted(invented):
        errors.append(f"invented edge (no reporting line in {ROUTING_SOURCE}): {edge}")
    missing = expected - file_edges
    for edge in sorted(missing):
        errors.append(f"missing derived edge: {edge}")


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
    parser = argparse.ArgumentParser(prog="validate_commflows.py", description='validate_commflows.py — shape + derivation validator for communication-flows.yaml')
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
        f"projection of {ROUTING_SOURCE} (delegation + escalation edges)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
