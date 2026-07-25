#!/usr/bin/env python3
"""scripts/a2a_intake/intake.py — the A2A goal-proposal intake handler (DAS-1611).

Implements design §1 of ``docs/design/a2a-outbound.md`` (DAS-1608 / ADR-0040
A2-2, A2-3 / SPEC-009 FR-002) — the ONLY thing an external A2A caller's goal
submission may become: a ``status: proposed`` candidate file in the existing
``board/goal-inbox/`` queue (the *same* landing the WS-H control plane's
``write_goal()`` already uses, ``tools/control_plane/app.py`` /
``docs/design/ws-h-control-plane.md`` §3.1(a)). This module invents no second
funnel — it writes into that one candidate queue and nowhere else.

Binding invariants this module enforces structurally (not merely by intent):

* **Never a ticket, never an approval (A2-2 / C3 / C4).** The only path this
  module can write through is :func:`intake_goal_proposal`, and that function
  has exactly ONE write call in its body, targeting ``board/goal-inbox/`` with a
  hand-built, allow-listed field set (``status``, ``source``, ``proposer``,
  ``proposed_at``, ``admission_ref``, optionally ``against_spec``/
  ``caller_ref``). There is no code path anywhere in this module that opens a
  file under ``board/tickets/``, sets ``status`` to anything but the literal
  string ``"proposed"``, or writes an ``approval``/``stage``/``assignee``/
  ``routing`` field to any file. A gate/approval/routing write is therefore
  **unreachable by construction** here — the WS-A/WS-B unreachability pattern
  applied to this governance write (mirrors ADR-0033/ADR-0038).
* **Validate-first, fail-closed (A2-2 / §1.3).** The submission is fully
  validated — required fields present, no forbidden control field, provenance
  present — BEFORE any file is written. A denied submission leaves **no**
  artifact in ``board/goal-inbox/`` (no partial write) and is never silently
  coerced into a valid one (a bad field is refused, never dropped-and-accepted).
* **Provenance carried through (§1.2).** ``proposer`` + ``proposed_at`` +
  ``admission_ref`` (the ADR-0009 admission decision id, stamped by the calling
  edge — never accepted from the caller's own submission body, see
  :data:`FORBIDDEN_FIELDS`) ride onto the landed artifact so an auditor can
  always answer "who proposed this and when."
* **Injection-inert (A2-3 / §1.4).** The caller's ``title``/``summary``/
  ``against_spec``/``caller_ref`` strings are written ONLY as literal Markdown
  *text* inside the landed file's body/front-matter values — they are never
  interpolated into a shell command, never ``eval``/``exec``-ed, and never used
  to select which field gets written (every field written is fixed by this
  module's own allow-list, not by anything present in the submission). A
  prompt-injection embedded in ``summary`` ("you are approved", "set status:
  done", ...) lands as inert reviewed text; there is no control write for it to
  reach.
* **Flag-gated, OFF by default (ADR-0019 / SC-005).** With ``a2a_outbound``
  OFF (`config/features.yaml`), :func:`intake_goal_proposal` performs **no
  I/O at all** — no file write, no audit append — and returns a deny result.
  The handler does not exist at dispatch time when the flag is off.
* **Symmetric audit (§1.3).** Both an allow and a deny are appended to the
  canonical append-only event store (``board/.events.jsonl``, ADR-0024/0025),
  redacted per ADR-0012 (the same scrubber ``tools/mcp_bridges/redaction.py``
  used by ``scripts/rbac.py`` — no third redactor), attributed to the admitted
  principal. A deny is never silent.

This module ships NO runtime wiring to the ADR-0009 admission edge itself —
that is DAS-1610's job (``tools/a2a``), which authenticates the caller and
passes the resulting ``admission_ref`` (and the authenticated principal, via
``authenticated_principal``) into :func:`intake_goal_proposal`. This module
only handles what happens to an already-admitted submission: proposal-in,
board-intake-artifact-out, refusal-on-anything-else.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# Self-locating repo root (LAW A — no hardcoded home path).
# scripts/a2a_intake/intake.py -> scripts/a2a_intake/ -> scripts/ -> repo root.
ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INBOX = ROOT / "board" / "goal-inbox"
DEFAULT_AUDIT_PATH = ROOT / "board" / ".events.jsonl"
DEFAULT_FEATURES = ROOT / "config" / "features.yaml"

FLAG = "a2a_outbound"

# ---------------------------------------------------------------------------
# The goal-proposal object shape (design §1.1) — a fixed, closed field set.
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: tuple[str, ...] = ("title", "summary", "proposer", "proposed_at")
OPTIONAL_FIELDS: tuple[str, ...] = ("against_spec", "caller_ref")
# admission_ref is SERVER-STAMPED (from the admission edge, via the
# ``admission_ref=`` keyword-only parameter below) — it is never accepted as a
# key inside the caller's own submission body, so it is listed in
# FORBIDDEN_FIELDS, not OPTIONAL_FIELDS.
ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset(REQUIRED_FIELDS) | frozenset(OPTIONAL_FIELDS)

# Fields the object schema does NOT define (design §1.1): a proposal carrying
# one of these is refused, never silently stripped. Matched case-insensitively
# and with '-'/'_' folded, so "Gate-Status", "APPROVAL", "dispatch_order" all
# match. This list is deliberately broader than the ADR-0040 examples so an
# unanticipated control-shaped key still fails closed rather than passing
# through as an unrecognised-but-harmless extra field.
FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "approval",
        "stage",
        "status",
        "ticket_type",
        "assignee",
        "author",
        "reviewer",
        "gate",
        "gatestatus",
        "routing",
        "dispatchorder",
        "admissionref",
        "priority",
        "dept",
        "parent",
        "id",
        "zone",
        "labels",
        "produces",
        "consumes",
        "program",
        "defer",
        "dependson",
    }
)


def _normalize_key(key: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(key).strip().lower())


# A goal-proposal value is single-line text (design §1.1). Any C0 control
# character — newline, carriage return, NUL, tab, etc. — is refused outright
# rather than stripped: the whole point is to deny the smuggling vector, not
# to "clean up" the caller's input and admit it anyway (§1.3 fail-closed).
# This is what closes the GATE-3 red-team hole (2026-07-24): a caller could
# not inject a forbidden *key*, but a newline inside an allow-listed *value*
# (``against_spec``/``caller_ref``/``proposer``) let a whole extra
# frontmatter line ride onto the landed artifact once it was concatenated via
# f-string. Rejecting the control character up front makes that vector
# unreachable regardless of how the frontmatter is later serialized.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _contains_control_char(value: str) -> bool:
    return bool(_CONTROL_CHAR_RE.search(value))


# Fields whose caller-supplied VALUE is written into the landed artifact's
# YAML *frontmatter* (as opposed to `title`/`summary`, which are written only
# into the Markdown *body* as prose — see `intake_goal_proposal` below, and
# `test_injection_in_summary_lands_as_inert_text` / SC-002c, which is a
# deliberate, still-binding guarantee that body text tolerates newlines
# because it can never be parsed as frontmatter structure). A control
# character in one of these frontmatter-bound fields is exactly the GATE-3
# red-team vector (2026-07-24): it is the field VALUES here, not the summary/
# title body text, that could smuggle extra frontmatter lines.
FRONTMATTER_VALUE_FIELDS: frozenset[str] = frozenset(
    {"proposer", "proposed_at", "against_spec", "caller_ref"}
)


def _redaction_mod() -> Any:
    """Lazy path-based load of the ADR-0012 scrubber (reuse VERBATIM — no fork,
    same loading pattern as ``scripts/rbac.py``'s ``_redaction_mod``)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "a2a_intake_redaction", ROOT / "tools" / "mcp_bridges" / "redaction.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError("cannot load tools/mcp_bridges/redaction.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_scrub(value: object) -> str:
    try:
        return _redaction_mod().safe_scrub(value)
    except Exception:  # noqa: BLE001 — a scrubber failure must never leak raw content
        return "[REDACTED:unclassified]"


# ---------------------------------------------------------------------------
# Feature flag (ADR-0019 / SC-005). Fail-safe to OFF: a broken/absent config
# never turns the handler ON. Line-scan (no YAML dependency), same pattern as
# ``scripts/rbac.is_enabled``.
# ---------------------------------------------------------------------------
def is_enabled(features_path: Path | None = None) -> bool:
    """True iff ``a2a_outbound`` resolves truthy. Default OFF => handler inert."""
    override = os.environ.get("DASLAB_A2A_OUTBOUND_FLAG")
    if override is not None:
        return override.strip().lower() in {"1", "true", "on", "yes"}
    path = Path(features_path) if features_path is not None else DEFAULT_FEATURES
    if not path.is_file():
        return False
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.split("#", 1)[0].strip()
            if raw.startswith(f"{FLAG}:"):
                return raw.split(":", 1)[1].strip().lower() in {"1", "true", "on", "yes"}
    except OSError:
        return False
    return False


# ---------------------------------------------------------------------------
# The append-only audit record (§1.3 — symmetric allow/deny, ADR-0024/0025,
# redacted per ADR-0012). Same durable-append discipline as
# ``scripts/rbac._append_audit`` / ``scripts/dgox/events.py``.
# ---------------------------------------------------------------------------
def _append_audit(record: dict[str, Any], audit_path: Path | None = None) -> None:
    path = Path(audit_path) if audit_path is not None else DEFAULT_AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            import fcntl  # noqa: PLC0415 - POSIX-only, optional

            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError, NameError):
                import fcntl  # noqa: PLC0415

                fcntl.flock(fh, fcntl.LOCK_UN)


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    return slug[:40] or "goal"


def _utcnow_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _is_valid_iso8601(value: str) -> bool:
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return True


@dataclass(frozen=True)
class IntakeResult:
    """The outcome of one :func:`intake_goal_proposal` call.

    ``decision`` is one of ``"allow"``, ``"deny"``, or ``"inert"`` (flag OFF —
    no I/O happened at all, not even an audit append). ``admitted`` is True
    only for ``"allow"``. ``path`` is the landed ``board/goal-inbox/`` file,
    set ONLY on ``"allow"``.
    """

    decision: str
    admitted: bool
    reason: str
    path: Path | None = None
    denied_field: str | None = None


def _validate(submission: Any, admission_ref: str) -> tuple[str | None, str | None]:
    """Validate-first (§1.3): returns (deny_reason, denied_field) or (None, None)
    if the submission is admissible. Performs NO I/O — pure check."""
    if not isinstance(submission, dict):
        return "malformed: submission must be an object/mapping", None

    # Forbidden control field, however cased/spaced — checked BEFORE anything
    # else so a forbidden field is always reported as such, never masked by a
    # missing-field deny.
    for key in submission:
        if _normalize_key(key) in FORBIDDEN_FIELDS:
            return (
                f"forbidden field {key!r}: a goal proposal may not carry a "
                "control/gate/routing field (A2-2, C3/C4)",
                str(key),
            )

    # Newline/control-char injection guard (GATE-3 red-team, 2026-07-24):
    # every caller-supplied value that is written into the landed artifact's
    # FRONTMATTER (proposer/proposed_at/against_spec/caller_ref) is checked
    # BEFORE any other content check, so a control char in an otherwise-valid
    # value is always reported as this deny, never masked by a later
    # missing-field or unknown-field deny. Such a value must be single-line
    # text; any value carrying '\n', '\r', NUL, or another control char is
    # refused, never silently stripped-and-accepted (fail-closed). This does
    # NOT apply to `title`/`summary` — those are written only into the
    # Markdown body as prose (never frontmatter), so a newline there cannot
    # smuggle a frontmatter line (SC-002c, `test_injection_in_summary_lands_
    # as_inert_text` remains the binding guarantee for body fields).
    _normalized_frontmatter_fields = {_normalize_key(f) for f in FRONTMATTER_VALUE_FIELDS}
    for key, value in submission.items():
        if (
            _normalize_key(key) in _normalized_frontmatter_fields
            and isinstance(value, str)
            and _contains_control_char(value)
        ):
            return (
                f"malformed: field {key!r} contains a newline or control "
                "character — this value is written into the landed "
                "artifact's frontmatter and must be single-line text "
                "(frontmatter/structure-injection guard, A2-2/C3/C4)",
                str(key),
            )

    # Required fields present and non-empty strings.
    for field_name in REQUIRED_FIELDS:
        value = submission.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return f"malformed: missing or empty required field {field_name!r}", field_name

    # Provenance: proposer must be a real (non-placeholder) identity string.
    proposer = submission["proposer"].strip()
    if not proposer or proposer.lower() in {"anonymous", "unknown", "none", "null"}:
        return "provenance-missing: no authenticated proposer identity", "proposer"

    # proposed_at must parse as ISO-8601.
    if not _is_valid_iso8601(submission["proposed_at"]):
        return "malformed: proposed_at is not a valid ISO-8601 timestamp", "proposed_at"

    # admission_ref is server-stamped via the keyword argument, never from the
    # submission body (already excluded above via FORBIDDEN_FIELDS); it still
    # must itself be present and non-empty — a call with no admission behind
    # it at all is provenance-missing.
    if not isinstance(admission_ref, str) or not admission_ref.strip():
        return "provenance-missing: no admission_ref from the admission edge", "admission_ref"

    # Any key outside the closed allow-list (required ∪ optional) that is not
    # already caught as forbidden is rejected too — fail-closed on unknowns
    # rather than silently accepting an unanticipated field.
    for key in submission:
        if _normalize_key(key) not in {_normalize_key(f) for f in ALLOWED_INPUT_FIELDS}:
            return (
                f"malformed: field {key!r} is not part of the goal-proposal object shape",
                str(key),
            )

    return None, None


def intake_goal_proposal(
    submission: dict[str, Any],
    *,
    admission_ref: str,
    authenticated_principal: str | None = None,
    inbox_dir: Path | None = None,
    audit_path: Path | None = None,
    features_path: Path | None = None,
    now: str | None = None,
) -> IntakeResult:
    """Intake ONE external A2A goal-proposal submission (DAS-1611 / FR-002).

    Writes ONLY a ``status: proposed`` file into ``board/goal-inbox/`` on
    success. Never creates a ``board/tickets/`` ticket, never writes an
    ``approval``/gate-status/routing field anywhere, never promotes or
    dispatches. See the module docstring for the structural guarantees.

    Parameters
    ----------
    submission:
        The caller-supplied proposal object (untrusted DATA, §1.4). Only the
        allow-listed keys (:data:`REQUIRED_FIELDS` ∪ :data:`OPTIONAL_FIELDS`)
        are ever read from it; every other key is rejected (forbidden or
        unknown), never silently dropped.
    admission_ref:
        The ADR-0009 admission decision id for this call, stamped by the
        calling admission edge (DAS-1610) — NEVER read from ``submission``.
    authenticated_principal:
        If the calling edge already authenticated a principal string, pass it
        here; a mismatch against ``submission["proposer"]`` is treated as a
        provenance-missing deny (the proposal cannot assert an identity the
        admission edge did not authenticate).
    """
    if not is_enabled(features_path):
        # Flag OFF => the handler does not exist at dispatch time (SC-005).
        # No I/O at all — not even an audit append — so the wave stays
        # byte-identical to pre-merge.
        return IntakeResult(decision="inert", admitted=False, reason="a2a_outbound flag is OFF")

    ts = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    deny_reason, denied_field = _validate(submission, admission_ref)
    if deny_reason is None and authenticated_principal is not None:
        proposer = str(submission.get("proposer", "")).strip()
        if proposer != authenticated_principal:
            deny_reason = "provenance-missing: proposer does not match the admitted principal"
            denied_field = "proposer"

    if deny_reason is not None:
        record = {
            "event_type": "a2a_intake_deny",
            "ts": ts,
            "decision": "deny",
            "proposer": _safe_scrub(submission.get("proposer", "")) if isinstance(submission, dict) else "",
            "admission_ref": _safe_scrub(admission_ref),
            "denied_field": denied_field,
            "reason": _safe_scrub(deny_reason),
        }
        _append_audit(record, audit_path)
        return IntakeResult(
            decision="deny", admitted=False, reason=deny_reason, denied_field=denied_field
        )

    # --- Admissible: build the landed artifact from a FIXED, allow-listed set
    # of fields only. Nothing from `submission` beyond these named lookups is
    # ever consulted — there is no dynamic "copy every key" path, so an
    # injected/forbidden key has no way to ride onto the artifact even if the
    # earlier validation were somehow bypassed (defense in depth).
    title = submission["title"].strip()
    summary = submission["summary"].strip()
    proposer = submission["proposer"].strip()
    proposed_at = submission["proposed_at"].strip()
    against_spec = submission.get("against_spec")
    caller_ref = submission.get("caller_ref")

    inbox = Path(inbox_dir) if inbox_dir is not None else DEFAULT_INBOX
    inbox.mkdir(parents=True, exist_ok=True)

    stamp = _utcnow_stamp()
    path = inbox / f"{stamp}-{_slug(title)}.md"
    counter = 1
    while path.exists():
        counter += 1
        path = inbox / f"{stamp}-{_slug(title)}-{counter}.md"

    # Defense in depth (GATE-3 red-team fix #2): emit the frontmatter through a
    # real YAML serializer on a fixed dict, not f-string line concatenation.
    # Even if a control char somehow slipped past `_validate` (regression, a
    # future caller of this internal helper, ...), `yaml.safe_dump` cannot be
    # tricked into treating a value as new structure — it quotes/escapes
    # whatever it is given. `sort_keys=False` preserves the canonical field
    # order (status first, admission_ref last of the fixed fields).
    front_matter: dict[str, str] = {
        "status": "proposed",  # the ONLY status an intake artifact may hold (§1.2)
        "source": "a2a",
        "proposer": proposer,
        "proposed_at": proposed_at,
        "admission_ref": admission_ref.strip(),
    }
    if isinstance(against_spec, str) and against_spec.strip():
        front_matter["against_spec"] = against_spec.strip()
    if isinstance(caller_ref, str) and caller_ref.strip():
        front_matter["caller_ref"] = caller_ref.strip()

    front_text = yaml.safe_dump(
        front_matter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )

    body = (
        "\n## Proposed goal\n"
        f"{title}\n\n"
        "## Rationale (proposer-supplied, UNTRUSTED — reviewed, not executed)\n"
        f"{summary}\n"
    )
    path.write_text(f"---\n{front_text}---\n" + body, encoding="utf-8")

    rel = str(path.relative_to(ROOT)) if _is_relative_to(path, ROOT) else str(path)
    record = {
        "event_type": "a2a_intake",
        "ts": ts,
        "decision": "allow",
        "proposer": _safe_scrub(proposer),
        "admission_ref": _safe_scrub(admission_ref),
        "path": rel,
    }
    _append_audit(record, audit_path)

    return IntakeResult(decision="allow", admitted=True, reason="proposed", path=path)


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


if __name__ == "__main__":  # pragma: no cover - manual probe
    import sys

    payload = json.loads(sys.stdin.read())
    ref = payload.pop("admission_ref", "") or os.environ.get("DASLAB_A2A_ADMISSION_REF", "manual-probe")
    result = intake_goal_proposal(payload, admission_ref=ref)
    print(json.dumps({"decision": result.decision, "reason": result.reason}))
