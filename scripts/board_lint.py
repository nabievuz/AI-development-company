#!/usr/bin/env python3
"""board_lint.py — validate every board/tickets/*.md against the DasLab ticket schema.

Reads every ``board/tickets/DAS-*.md`` file, parses YAML frontmatter, and
enforces the rules defined in ``board/README.md``.  Exits non-zero with a
human-readable error list on any violation; exits 0 (silent) when the board is
clean.

Rules enforced
--------------
1. Required fields present: id, title, status, assignee, author, dept, priority,
   created, updated.
2. ``status`` is one of the allowed enum values.
3. ``assignee`` is empty OR a known role key from ROUTING.md.
4. ``author`` is a known role key from ROUTING.md.
5. ``priority`` is one of p0 / p1 / p2.
6. Subtasks (``parent`` is non-empty) must also carry ``goal``.
7. ``parent`` references an ID that exists in the board (no dangling pointers).
8. ``in_review`` tickets: ``assignee`` must differ from ``author``
   (no self-review). This rule is scoped to ``status == "in_review"`` only, so
   an ``interrupted`` ticket is out of its scope — it is never rejected or
   stranded by R8 (DAS-1446 consumer sweep).
9. Org board is platform-only: a ticket on ``board/tickets/`` must NOT declare a
   ``project:`` field — project tickets live in ``projects/<slug>/board-tickets/``
   (QONUN — Project Placement Law). Project boards (path ``…/board-tickets/``)
   are exempt; the field is valid there.
10. ``merge_policy`` (OPTIONAL) is well-formed: when present its value is one of
   ``append-only`` / ``owner-exclusive`` / ``aggregate:<reducer>`` (grammar owned
   by ``scripts/merge_reducers.py``); a present-but-empty or unrecognized value
   is a defect, and a ``merge_policy`` declared WITHOUT a ``zone:`` anchor is a
   defect. R10 is a per-ticket grammar check only.
11. ``produces`` / ``consumes`` (OPTIONAL) name artifact-schema contracts
   (DAS-1467). Each value is a single schema name or a bracketed/comma list of
   names, read with the tolerant reader ``_schema_names_of`` (mirrors ``_zone_of``
   / ``check_dependency_graph._fm_field``). Every named schema must exist as a
   well-formed ``governance/schemas/<name>.yaml`` — a present-but-unknown name is
   a FAIL, a present-but-malformed schema file is a FAIL, a present-but-empty
   value is a FAIL. Absent = lints exactly as before (additive). The schema shape
   is owned by ``scripts/artifact_schemas.py`` (single source of truth, like
   ``merge_reducers.py`` is for policy grammar).
12. Stage-gated delivery (P22 / DAS-1494, OPTIONAL/additive). Cross-ticket rule
   owned by ``scripts/stage_gate.py``: a ``stage: GATE-N`` ticket must not ADVANCE
   (``in_progress``/``in_review``/``done``) while the same ``goal``'s GATE-(N-1) is
   open, and a production-deploy ticket (the ``gate5_deployment`` risk category —
   reused from ``config/risk_taxonomy.yaml``, not a fork) must not be auto-approved
   or advance while GATE-5 (Deployment) is open. A ``todo``/``backlog`` stage ticket
   is the legitimate gate-waiting state and is never flagged; a board with no
   ``stage:`` tickets lints exactly as before.

Wave correctness guard (exported, not a whole-board rule)
--------------------------------------------------------
The "never two tickets in the same repo ``zone:`` in one wave" correctness guard
(ADR-0016) is a **per-wave** property, not repo state — the board legitimately
holds many same-zone tickets across different waves. So it is NOT enforced over
the whole board here (that would false-positive). Instead this module exports
``same_zone_pair_allowed`` / ``zone_wave_conflicts`` — pure, fail-closed
decision helpers over a *candidate wave* that ``/daslab-cycle`` (and tests) call.
The default is unchanged: a same-zone pair is FORBIDDEN unless every member of
the same-zone group declares the SAME valid, permitting ``merge_policy``.

Usage::

    python3 scripts/board_lint.py [--board <path>] [--routing <path>]

Exit codes: 0 = clean, 1 = violations found, 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT
from artifact_schemas import SchemaError, load_schema_file, schema_path
from merge_reducers import is_valid_policy

# ---------------------------------------------------------------------------
# Idempotency warning patterns (R10 — DAS-1447)
# ---------------------------------------------------------------------------

# High-risk side-effect verbs that should have idempotency guards when they
# appear in the body of an ``interrupted`` ticket.
_RISKY_EFFECTS_RE = re.compile(
    r"\b(merge[sd]?|spend[s]?|spending|charge[sd]?|charging|send[s]?|sending|"
    r"notif(?:y|ies|ied|ying)|post(?:ed|s|ing)?|dispatch(?:ed|es|ing)?)\b",
    re.IGNORECASE,
)

# Idempotency guard phrases — if any of these appear, we consider the ticket
# already guarded and do NOT emit the warning.
_IDEMPOTENCY_GUARD_RE = re.compile(
    r"\b(idempotent|idempotency[\s\-]key|guard[\-\s]before|"
    r"check[\s\-]if[\s\-]already|re\-runnable|safe\s+to\s+re\-run|"
    r"already[\s\-]run|guard[\s\-]before[\s\-]act|double[\s\-]apply)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ``interrupted`` (added DAS-1446): a running agent paused itself to ask the
# Founder a question via an interrupt card (see board/interrupts/README.md). It
# is distinct from ``blocked`` (external-dependency stall, never auto-dispatched)
# and ``in_review`` (awaiting a reviewer). Legal transitions:
#   in_progress -> interrupted   (agent raises an interrupt card and yields)
#   interrupted -> in_progress   (Founder writes resume:<value>; re-enters wave)
#   interrupted -> blocked       (question abandoned; needs a log reason, R-per-board)
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

# Repo root is two levels up from this script (scripts/ -> root)
_REPO_ROOT = ROOT


# ---------------------------------------------------------------------------
# ROUTING.md parser — extract valid role keys
# ---------------------------------------------------------------------------

_ROLE_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|", re.MULTILINE)


def load_known_roles(routing_path: Path) -> frozenset[str]:
    """Return the set of role keys listed in ROUTING.md."""
    text = routing_path.read_text(encoding="utf-8")
    return frozenset(_ROLE_ROW_RE.findall(text))


# ---------------------------------------------------------------------------
# Frontmatter parser — lightweight, no external deps
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$', re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Return key->value dict from YAML frontmatter, or None if absent/malformed."""
    m = _FM_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(block):
        # Strip inline YAML quotes if present
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


# ---------------------------------------------------------------------------
# Tolerant field readers (zone / merge_policy)
# ---------------------------------------------------------------------------
# The regex parser captures every value as a raw string. These helpers strip
# surrounding whitespace and inline YAML quotes so callers compare clean values.
# They mirror the tolerant read pattern in check_dependency_graph._fm_field.

def _zone_of(fm: dict[str, str]) -> str:
    """Return the ticket's declared ``zone:``, cleaned; '' if absent/empty."""
    return fm.get("zone", "").strip().strip('"').strip("'")


def _merge_policy_of(fm: dict[str, str]) -> str:
    """Return the ticket's declared ``merge_policy:``, cleaned; '' if absent."""
    return fm.get("merge_policy", "").strip().strip('"').strip("'")


def _schema_names_of(fm: dict[str, str], key: str) -> list[str]:
    """Return the artifact-schema names declared in ``produces:``/``consumes:``.

    This is the tolerant reader for the DAS-1467 list-ish fields — the reconciled
    parse path for these two keys. It mirrors ``_zone_of``'s whitespace/quote
    stripping and ``check_dependency_graph._fm_field`` + ``DAS_RE.findall``'s
    "raw string → list" tolerance, because the regex frontmatter parser
    (``_KV_RE``) captures a list value like ``[a, b]`` as the raw string
    ``"[a, b]"`` and never splits it.

    Accepts a single name (``produces: task-ledger``) or a bracketed/comma list
    (``produces: [task-ledger, typed-contracts]``). Surrounding brackets and per
    -item whitespace/inline quotes are stripped. Empty items are dropped, so an
    empty or ``[]`` value yields ``[]`` (the caller treats that as present-but
    -empty).
    """
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


# ---------------------------------------------------------------------------
# Wave correctness guard — same-zone pair decision (exported, fail-closed)
# ---------------------------------------------------------------------------
# SAFETY: these decide whether two tickets touching the SAME repo zone may run
# in ONE wave. They are called by /daslab-cycle at dispatch (and by tests), NOT
# over the whole board (the board holds many same-zone tickets across waves).
# The default is fail-closed: a same-zone pair is forbidden UNLESS every member
# declares the SAME valid, permitting merge_policy for that zone.

def same_zone_pair_allowed(fm_a: dict[str, str], fm_b: dict[str, str]) -> bool:
    """Return True iff two tickets MAY co-dispatch in one wave.

    Fail-closed contract:
    - Different (or absent) zones → not a same-zone pair; the guard does not
      apply, so the pair is allowed (returns True).
    - SAME non-empty zone but no / mismatched / empty / invalid merge_policy →
      FORBIDDEN (returns False). This is the unchanged default.
    - SAME non-empty zone AND both declare the SAME valid permitting
      merge_policy → allowed (returns True).
    """
    za, zb = _zone_of(fm_a), _zone_of(fm_b)
    if not za or za != zb:
        return True  # not a same-zone pair — guard is silent
    pa, pb = _merge_policy_of(fm_a), _merge_policy_of(fm_b)
    if not pa or pa != pb:
        return False  # same zone, no shared policy → default forbids
    return is_valid_policy(pa)  # same zone + same valid permitting policy → OK


def zone_wave_conflicts(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    """Return violation strings for same-zone groups in a *candidate wave*.

    A same-zone group of two or more tickets is permitted to co-dispatch ONLY
    when every member declares the SAME valid, permitting ``merge_policy``.
    Otherwise every such group is a violation (fail-closed default). Groups of
    one, and tickets with no ``zone:``, are ignored.
    """
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
                continue  # zone opted in with one shared valid policy → allowed
        ids = sorted((fm.get("id") or p.name) for p, fm in group)
        violations.append(
            f"same-zone wave conflict on zone '{zone}': {ids} would co-dispatch "
            "but do not all declare the same permitting merge_policy "
            "(default forbids two same-zone tickets in one wave)"
        )
    return violations


# ---------------------------------------------------------------------------
# Ticket collection
# ---------------------------------------------------------------------------

def load_tickets(board_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    """Return list of (path, frontmatter) for every DAS-*.md in *board_dir*."""
    results: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(board_dir.glob("DAS-*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            # Treat missing frontmatter as an empty dict — R1 will catch it
            fm = {}
        results.append((path, fm))
    return results


# ---------------------------------------------------------------------------
# Lint rules
# ---------------------------------------------------------------------------

def lint_tickets(
    tickets: list[tuple[Path, dict[str, str]]],
    known_roles: frozenset[str],
    schemas_dir: Path | None = None,
) -> list[str]:
    """Apply all rules and return a list of human-readable violation strings.

    ``schemas_dir`` locates the artifact-schema registry for R11
    (``produces:``/``consumes:``); defaults to ``governance/schemas/`` under the
    repo root. Tests pass a temporary directory here.
    """
    errors: list[str] = []
    if schemas_dir is None:
        schemas_dir = _REPO_ROOT / "governance" / "schemas"

    # Build a set of known ticket IDs for parent-reference check (rule 7)
    known_ids: set[str] = set()
    for _, fm in tickets:
        tid = fm.get("id", "").strip()
        if tid:
            known_ids.add(tid)

    for path, fm in tickets:
        ticket_label = fm.get("id") or path.name

        def err(msg: str, ticket_label: str = ticket_label) -> None:
            errors.append(f"{ticket_label}: {msg}")

        # R1 — Required fields
        for field in REQUIRED_FIELDS:
            if field not in fm:
                err(f"missing required field '{field}'")

        status = fm.get("status", "").strip()
        assignee = fm.get("assignee", "").strip()
        author = fm.get("author", "").strip()
        parent = fm.get("parent", "").strip()
        goal = fm.get("goal", "").strip()
        priority = fm.get("priority", "").strip()

        # R2 — status enum
        if status and status not in VALID_STATUSES:
            err(f"invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")

        # R3 — assignee is empty OR a known role
        if assignee and assignee not in known_roles:
            err(f"unknown assignee '{assignee}'")

        # R4 — author is a known role
        if author and author not in known_roles:
            err(f"unknown author '{author}'")

        # R5 — priority
        if priority and priority not in VALID_PRIORITIES:
            err(f"invalid priority '{priority}'; must be one of {sorted(VALID_PRIORITIES)}")

        # R6 — subtasks need goal
        if parent and not goal:
            err(f"subtask has parent '{parent}' but no 'goal' field")

        # R7 — parent must exist
        if parent and parent not in known_ids:
            err(f"parent '{parent}' does not exist in the board")

        # R8 — in_review cannot be self-reviewed
        if status == "in_review" and assignee and author and assignee == author:
            err(
                f"in_review ticket has assignee == author '{assignee}'; "
                "self-review is not allowed"
            )

        # R9 — org board/tickets/ is platform-only: no project: field.
        # The org board path contains "board/tickets/" (slash); a project's own
        # board is "…/board-tickets/" (hyphen), so the field stays valid there.
        project = fm.get("project", "").strip()
        on_org_board = "board/tickets/" in str(path).replace("\\", "/")
        if on_org_board and project:
            err(
                f"declares project '{project}' but lives on the org board/tickets/; "
                "project tickets belong in projects/<slug>/board-tickets/ "
                "(board/tickets/ is DasLab-platform only)"
            )

        # R10 — merge_policy grammar + zone anchor (per-ticket check).
        # Optional: additive, so tickets without it lint exactly as before. The
        # grammar is owned by scripts/merge_reducers.py (single source of truth).
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

        # R11 — produces/consumes artifact-schema contracts (OPTIONAL, additive).
        # Each named schema must exist as a well-formed governance/schemas/<name>.yaml.
        # Shape/grammar owned by scripts/artifact_schemas.py (single source of truth).
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

        # R13 — FINALE program tickets require typed contracts (FAIL-CLOSED).
        # A ticket that declares `program: finale` MUST carry BOTH `produces:`
        # and `consumes:` (R11 above still validates that each named schema is
        # well-formed). This is the one place the typed-contract discipline is
        # fail-closed rather than optional, and it fires ONLY for the FINALE
        # program marker — so every non-FINALE ticket lints exactly as before.
        # Match the FIRST whitespace-delimited token after stripping quotes, so an
        # inline YAML comment (`program: finale  # note`) or a stray quote cannot
        # bypass this fail-closed gate — the permissive frontmatter parser keeps the
        # trailing comment in the raw value, so exact-equality would silently miss it.
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

    # R12 — stage-gated delivery (P22 / DAS-1494). Cross-ticket, additive:
    # a stage-N ticket must not ADVANCE past an open GATE-(N-1), and a
    # production-deploy must not proceed while GATE-5 is open (reusing the
    # gate5_deployment never-auto-approve category in config/risk_taxonomy.yaml).
    # Imported lazily to avoid an import cycle (stage_gate reuses check_* helpers).
    # The rule is additive: when stage_gate imports cleanly and legitimately reports
    # no violations, `errors` is unchanged. A `todo`/`backlog` stage ticket is NOT
    # flagged (the legitimate gate-waiting state) — only advancing past an open gate is.
    #
    # FAIL-CLOSED (audit remediation FIX-B): a stage_gate import/config/runtime
    # error must NOT be swallowed. Swallowing it silently disabled GATE-5's
    # no-deploy law and the gate-order block — the linter would report a green
    # board while its most safety-critical rule was inert. So on ANY exception we
    # SURFACE it as a lint violation (non-zero exit) rather than `pass`.
    try:
        import stage_gate  # noqa: PLC0415 - lazy, breaks the import cycle
        errors.extend(stage_gate.stage_gate_violations(tickets))
    except Exception as exc:  # noqa: BLE001 - fail-closed: surface, never swallow
        errors.append(
            "R12 stage-gate check could not run and was surfaced instead of "
            "bypassed (fail-closed: a broken stage_gate must not silently disable "
            "GATE-5 no-deploy + gate-order enforcement): "
            f"{type(exc).__name__}: {exc}"
        )

    return errors


# ---------------------------------------------------------------------------
# Idempotency warnings (W10 — DAS-1447)
# ---------------------------------------------------------------------------

def warn_interrupted_idempotency(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    """Return warning strings for ``interrupted`` tickets with possibly non-
    idempotent pre-interrupt side effects (DAS-1447).

    A warning is emitted when:
    - The ticket has ``status: interrupted``, AND
    - Its body mentions a high-risk action verb (merge, spend, charge, send,
      notify, post, dispatch) that could represent a non-idempotent pre-interrupt
      side effect, AND
    - No idempotency guard phrase is found in the body (idempotent, idempotency
      key, guard-before-act, check-if-already-done, re-runnable, safe to re-run).

    These are WARNINGS, not errors — the exit code is not affected.  Emit as
    ``WARN`` lines so they are distinguishable from ``FAIL`` lines.
    """
    warnings: list[str] = []

    for path, fm in tickets:
        if fm.get("status", "").strip() != "interrupted":
            continue
        ticket_label = fm.get("id") or path.name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        # Strip the frontmatter block so we only scan the body.
        body = _FM_RE.sub("", text, count=1)

        risky_matches = _RISKY_EFFECTS_RE.findall(body)
        if not risky_matches:
            continue  # No high-risk verbs — nothing to warn about.

        if _IDEMPOTENCY_GUARD_RE.search(body):
            continue  # Guard already present — no warning needed.

        found = ", ".join(sorted({m.lower() for m in risky_matches}))
        warnings.append(
            f"{ticket_label}: interrupted ticket mentions possibly non-idempotent "
            f"pre-interrupt side effect(s) ({found}) without an idempotency guard "
            "— add a guard-before-act note so re-dispatch is safe (DAS-1447)"
        )

    return warnings


# ---------------------------------------------------------------------------
# Body-prose warnings (W11 — DAS-1507: a `status:`-like line in the body)
# ---------------------------------------------------------------------------


def warn_body_status_lines(
    tickets: list[tuple[Path, dict[str, str]]],
) -> list[str]:
    """Warn when a ticket BODY (outside frontmatter) carries a line like
    ``status: <valid-status>`` — DAS-1507-style prose that mimics the frontmatter
    field and can confuse a line-based reader (e.g. the interrupt round-trip's
    ``status: interrupted`` scan). WARNING, not an error — exit code unaffected.
    Scoped to a real status value so ordinary "status:" prose does not false-warn.
    """
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
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

    # W10 — idempotency warnings for interrupted tickets (DAS-1447).
    # These are informational; they do NOT change the exit code.
    idempotency_warnings = warn_interrupted_idempotency(tickets)
    if idempotency_warnings:
        print(
            f"board_lint: {len(idempotency_warnings)} idempotency warning(s) "
            f"(non-fatal — fix before re-dispatching interrupted tickets):"
        )
        for w in idempotency_warnings:
            print(f"  WARN  {w}")

    # W11 — a `status: <status>` line in the ticket BODY (DAS-1507); informational.
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
