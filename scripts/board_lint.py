#!/usr/bin/env python3


from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT
from artifact_schemas import SchemaError, load_schema_file, schema_path
from merge_reducers import is_valid_policy


_RISKY_EFFECTS_RE = re.compile(
    r"\b(merge[sd]?|spend[s]?|spending|charge[sd]?|charging|send[s]?|sending|"
    r"notif(?:y|ies|ied|ying)|post(?:ed|s|ing)?|dispatch(?:ed|es|ing)?)\b",
    re.IGNORECASE,
)


_IDEMPOTENCY_GUARD_RE = re.compile(
    r"\b(idempotent|idempotency[\s\-]key|guard[\-\s]before|"
    r"check[\s\-]if[\s\-]already|re\-runnable|safe\s+to\s+re\-run|"
    r"already[\s\-]run|guard[\s\-]before[\s\-]act|double[\s\-]apply)\b",
    re.IGNORECASE,
)


VALID_STATUSES = frozenset(
    {"backlog", "todo", "in_progress", "blocked", "in_review", "done", "interrupted"}
)
VALID_PRIORITIES = frozenset({"p0", "p1", "p2"})
REQUIRED_FIELDS = (
    "id",
    "title",
    "status",
    "assignee",
    "author",
    "dept",
    "priority",
    "created",
    "updated",
)


_REPO_ROOT = ROOT


_ROLE_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|", re.MULTILINE)


def load_known_roles(routing_path: Path) -> frozenset[str]:
    text = routing_path.read_text(encoding="utf-8")
    return frozenset(_ROLE_ROW_RE.findall(text))


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$', re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = _FM_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(block):

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


def _zone_of(fm: dict[str, str]) -> str:
    return fm.get("zone", "").strip().strip('"').strip("'")


def _merge_policy_of(fm: dict[str, str]) -> str:
    return fm.get("merge_policy", "").strip().strip('"').strip("'")


def _schema_names_of(fm: dict[str, str], key: str) -> list[str]:
    if key not in fm:
        return []
    raw = fm[key].strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    names: list[str] = []
    for part in raw.split(","):
        cleaned = part.strip().strip('"').strip("'").strip()
        if cleaned:
            names.append(cleaned)
    return names


def same_zone_pair_allowed(fm_a: dict[str, str], fm_b: dict[str, str]) -> bool:
    za, zb = _zone_of(fm_a), _zone_of(fm_b)
    if not za or za != zb:
        return True
    pa, pb = _merge_policy_of(fm_a), _merge_policy_of(fm_b)
    if not pa or pa != pb:
        return False
    return is_valid_policy(pa)


def zone_wave_conflicts(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    by_zone: dict[str, list[tuple[Path, dict[str, str]]]] = {}
    for path, fm in tickets:
        zone = _zone_of(fm)
        if zone:
            by_zone.setdefault(zone, []).append((path, fm))

    violations: list[str] = []
    for zone, group in sorted(by_zone.items()):
        if len(group) < 2:
            continue
        policies = {_merge_policy_of(fm) for _p, fm in group}
        if len(policies) == 1:
            (pol,) = tuple(policies)
            if pol and is_valid_policy(pol):
                continue
        ids = sorted((fm.get("id") or p.name) for p, fm in group)
        violations.append(
            f"same-zone wave conflict on zone '{zone}': {ids} would co-dispatch "
            "but do not all declare the same permitting merge_policy "
            "(default forbids two same-zone tickets in one wave)"
        )
    return violations


def load_tickets(board_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    results: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(board_dir.glob("DAS-*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:

            fm = {}
        results.append((path, fm))
    return results


def lint_tickets(
    tickets: list[tuple[Path, dict[str, str]]],
    known_roles: frozenset[str],
    schemas_dir: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if schemas_dir is None:
        schemas_dir = _REPO_ROOT / "governance" / "schemas"


    known_ids: set[str] = set()
    id_owners: dict[str, list[str]] = {}
    for path, fm in tickets:
        tid = fm.get("id", "").strip()
        if tid:
            known_ids.add(tid)
            id_owners.setdefault(tid, []).append(path.name)


    for tid, owners in sorted(id_owners.items()):
        if len(owners) > 1:
            errors.append(
                f"{tid}: duplicate ticket id claimed by {len(owners)} files "
                f"({', '.join(sorted(owners))}) — renumber all but the "
                f"earliest-created one to the next free DAS-* id"
            )

    for path, fm in tickets:
        ticket_label = fm.get("id") or path.name

        def err(msg: str, ticket_label: str = ticket_label) -> None:
            errors.append(f"{ticket_label}: {msg}")


        for field in REQUIRED_FIELDS:
            if field not in fm:
                err(f"missing required field '{field}'")

        status = fm.get("status", "").strip()
        assignee = fm.get("assignee", "").strip()
        author = fm.get("author", "").strip()
        parent = fm.get("parent", "").strip()
        goal = fm.get("goal", "").strip()
        priority = fm.get("priority", "").strip()


        if status and status not in VALID_STATUSES:
            err(f"invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")


        if assignee and assignee not in known_roles:
            err(f"unknown assignee '{assignee}'")


        if author and author not in known_roles:
            err(f"unknown author '{author}'")


        if priority and priority not in VALID_PRIORITIES:
            err(f"invalid priority '{priority}'; must be one of {sorted(VALID_PRIORITIES)}")


        if parent and not goal:
            err(f"subtask has parent '{parent}' but no 'goal' field")


        if parent and parent not in known_ids:
            err(f"parent '{parent}' does not exist in the board")


        if status == "in_review" and assignee and author and assignee == author:
            err(
                f"in_review ticket has assignee == author '{assignee}'; "
                "self-review is not allowed"
            )


        project = fm.get("project", "").strip()
        on_org_board = "board/tickets/" in str(path).replace("\\", "/")
        if on_org_board and project:
            err(
                f"declares project '{project}' but lives on the org board/tickets/; "
                "project tickets belong in projects/<slug>/board-tickets/ "
                "(board/tickets/ is DasLab-platform only)"
            )


        if "merge_policy" in fm:
            merge_policy = _merge_policy_of(fm)
            zone = _zone_of(fm)
            if not merge_policy:
                err("merge_policy is present but empty; remove it or set "
                    "append-only / owner-exclusive / aggregate:<reducer>")
            elif not is_valid_policy(merge_policy):
                err(f"invalid merge_policy '{merge_policy}'; allowed: "
                    "append-only, owner-exclusive, aggregate:<sum|union>")
            if merge_policy and not zone:
                err("merge_policy declared without a zone: to anchor it "
                    "(a merge policy relaxes the same-zone wave guard, so it "
                    "needs a zone)")


        for contract_key in ("produces", "consumes"):
            if contract_key not in fm:
                continue
            names = _schema_names_of(fm, contract_key)
            if not names:
                err(f"{contract_key} is present but names no artifact schema; "
                    "remove it or name a governance/schemas/<name>.yaml")
                continue
            for name in names:
                sp = schema_path(name, schemas_dir)
                if not sp.is_file():
                    err(f"{contract_key} names unknown artifact schema '{name}' "
                        f"— no governance/schemas/{name}.yaml")
                    continue
                try:
                    load_schema_file(sp)
                except SchemaError as exc:
                    err(f"{contract_key} artifact schema '{name}' is malformed: {exc}")


        _program = fm.get("program", "").strip().strip("\"'").split()
        if _program and _program[0].lower() == "finale":
            for contract_key in ("produces", "consumes"):
                names = (
                    _schema_names_of(fm, contract_key) if contract_key in fm else []
                )
                if not names:
                    err(
                        f"program: finale requires a non-empty '{contract_key}:' "
                        "typed contract naming a governance/schemas/<name>.yaml "
                        "(fail-closed for FINALE tickets); it is absent or empty"
                    )


    try:
        import stage_gate
        errors.extend(stage_gate.stage_gate_violations(tickets))
    except Exception as exc:
        errors.append(
            "R12 stage-gate check could not run and was surfaced instead of "
            "bypassed (fail-closed: a broken stage_gate must not silently disable "
            "GATE-5 no-deploy + gate-order enforcement): "
            f"{type(exc).__name__}: {exc}"
        )

    return errors


def warn_interrupted_idempotency(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    warnings: list[str] = []

    for path, fm in tickets:
        if fm.get("status", "").strip() != "interrupted":
            continue
        ticket_label = fm.get("id") or path.name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue


        body = _FM_RE.sub("", text, count=1)

        risky_matches = _RISKY_EFFECTS_RE.findall(body)
        if not risky_matches:
            continue

        if _IDEMPOTENCY_GUARD_RE.search(body):
            continue

        found = ", ".join(sorted({m.lower() for m in risky_matches}))
        warnings.append(
            f"{ticket_label}: interrupted ticket mentions possibly non-idempotent "
            f"pre-interrupt side effect(s) ({found}) without an idempotency guard "
            "— add a guard-before-act note so re-dispatch is safe (DAS-1447)"
        )

    return warnings


def warn_body_status_lines(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    status_alt = "|".join(re.escape(s) for s in sorted(VALID_STATUSES))
    body_status_re = re.compile(rf"(?mi)^status:[^\S\n]*(?:{status_alt})\b")
    warnings: list[str] = []
    for path, fm in tickets:
        ticket_label = fm.get("id") or path.name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        body = _FM_RE.sub("", text, count=1)
        if body_status_re.search(body):
            warnings.append(
                f"{ticket_label}: a 'status: <status>' line appears in the ticket "
                "BODY (outside frontmatter) — this prose mimics the frontmatter "
                "field and can confuse line-based readers; reword or backtick it "
                "(DAS-1507)"
            )
    return warnings


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='board_lint.py — validate every board/tickets/*.md against the DasLab ticket schema.\n\nReads every ``board/tickets/DAS-*.md`` file, parses YAML frontmatter, and\nenforces the rules defined in ``board/README.md``.  Exits non-zero with a\nhuman-readable error list on any violation; exits 0 (silent) when the board is\nclean.\n\nRules enforced\n--------------\n1. Required fields present: id, title, status, assignee, author, dept, priority,\n   created, updated.\n2. ``status`` is one of the allowed enum values.\n3. ``assignee`` is empty OR a known role key from ROUTING.md.\n4. ``author`` is a known role key from ROUTING.md.\n5. ``priority`` is one of p0 / p1 / p2.\n6. Subtasks (``parent`` is non-empty) must also carry ``goal``.\n7. ``parent`` references an ID that exists in the board (no dangling pointers).\n8. ``in_review`` tickets: ``assignee`` must differ from ``author``\n   (no self-review). This rule is scoped to ``status == "in_review"`` only, so\n   an ``interrupted`` ticket is out of its scope — it is never rejected or\n   stranded by R8 (DAS-1446 consumer sweep).\n9. Org board is platform-only: a ticket on ``board/tickets/`` must NOT declare a\n   ``project:`` field — project tickets live in ``projects/<slug>/board-tickets/``\n   (QONUN — Project Placement Law). Project boards (path ``…/board-tickets/``)\n   are exempt; the field is valid there.\n10. ``merge_policy`` (OPTIONAL) is well-formed: when present its value is one of\n   ``append-only`` / ``owner-exclusive`` / ``aggregate:<reducer>`` (grammar owned\n   by ``scripts/merge_reducers.py``); a present-but-empty or unrecognized value\n   is a defect, and a ``merge_policy`` declared WITHOUT a ``zone:`` anchor is a\n   defect. R10 is a per-ticket grammar check only.\n11. ``produces`` / ``consumes`` (OPTIONAL) name artifact-schema contracts\n   (DAS-1467). Each value is a single schema name or a bracketed/comma list of\n   names, read with the tolerant reader ``_schema_names_of`` (mirrors ``_zone_of``\n   / ``check_dependency_graph._fm_field``). Every named schema must exist as a\n   well-formed ``governance/schemas/<name>.yaml`` — a present-but-unknown name is\n   a FAIL, a present-but-malformed schema file is a FAIL, a present-but-empty\n   value is a FAIL. Absent = lints exactly as before (additive). The schema shape\n   is owned by ``scripts/artifact_schemas.py`` (single source of truth, like\n   ``merge_reducers.py`` is for policy grammar).\n12. Stage-gated delivery (P22 / DAS-1494, OPTIONAL/additive). Cross-ticket rule\n   owned by ``scripts/stage_gate.py``: a ``stage: GATE-N`` ticket must not ADVANCE\n   (``in_progress``/``in_review``/``done``) while the same ``goal``\'s GATE-(N-1) is\n   open, and a production-deploy ticket (the ``gate5_deployment`` risk category —\n   reused from ``config/risk_taxonomy.yaml``, not a fork) must not be auto-approved\n   or advance while GATE-5 (Deployment) is open. A ``todo``/``backlog`` stage ticket\n   is the legitimate gate-waiting state and is never flagged; a board with no\n   ``stage:`` tickets lints exactly as before.\n\nWave correctness guard (exported, not a whole-board rule)\n--------------------------------------------------------\nThe "never two tickets in the same repo ``zone:`` in one wave" correctness guard\n(ADR-0016) is a **per-wave** property, not repo state — the board legitimately\nholds many same-zone tickets across different waves. So it is NOT enforced over\nthe whole board here (that would false-positive). Instead this module exports\n``same_zone_pair_allowed`` / ``zone_wave_conflicts`` — pure, fail-closed\ndecision helpers over a *candidate wave* that ``/daslab-cycle`` (and tests) call.\nThe default is unchanged: a same-zone pair is FORBIDDEN unless every member of\nthe same-zone group declares the SAME valid, permitting ``merge_policy``.\n\nUsage::\n\n    python3 scripts/board_lint.py [--board <path>] [--routing <path>]\n\nExit codes: 0 = clean, 1 = violations found, 2 = usage/IO error.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--board",
        type=Path,
        default=_REPO_ROOT / "board" / "tickets",
        help="Path to the board/tickets/ directory (default: auto-detected from repo root)",
    )
    p.add_argument(
        "--routing",
        type=Path,
        default=_REPO_ROOT / "board" / "ROUTING.md",
        help="Path to board/ROUTING.md (default: auto-detected from repo root)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    board_dir: Path = args.board
    routing_path: Path = args.routing

    if not board_dir.is_dir():
        print(f"ERROR: board directory not found: {board_dir}", file=sys.stderr)
        return 2
    if not routing_path.is_file():
        print(f"ERROR: ROUTING.md not found: {routing_path}", file=sys.stderr)
        return 2

    try:
        known_roles = load_known_roles(routing_path)
    except OSError as exc:
        print(f"ERROR reading ROUTING.md: {exc}", file=sys.stderr)
        return 2

    try:
        tickets = load_tickets(board_dir)
    except OSError as exc:
        print(f"ERROR reading board tickets: {exc}", file=sys.stderr)
        return 2

    errors = lint_tickets(tickets, known_roles)

    if errors:
        print(f"board_lint: {len(errors)} violation(s) found:\n", file=sys.stderr)
        for e in errors:
            print(f"  FAIL  {e}", file=sys.stderr)
        return 1


    idempotency_warnings = warn_interrupted_idempotency(tickets)
    if idempotency_warnings:
        print(
            f"board_lint: {len(idempotency_warnings)} idempotency warning(s) "
            f"(non-fatal — fix before re-dispatching interrupted tickets):"
        )
        for w in idempotency_warnings:
            print(f"  WARN  {w}")


    body_status_warnings = warn_body_status_lines(tickets)
    if body_status_warnings:
        print(
            f"board_lint: {len(body_status_warnings)} body-status warning(s) "
            "(non-fatal — reword prose that mimics the status frontmatter field):"
        )
        for w in body_status_warnings:
            print(f"  WARN  {w}")

    print(f"board_lint: OK — {len(tickets)} ticket(s) checked, 0 violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
