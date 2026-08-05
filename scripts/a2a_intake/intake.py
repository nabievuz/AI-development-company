#!/usr/bin/env python3

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


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INBOX = ROOT / "board" / "goal-inbox"
DEFAULT_AUDIT_PATH = ROOT / "board" / ".events.jsonl"
DEFAULT_FEATURES = ROOT / "config" / "features.yaml"

FLAG = "a2a_outbound"


REQUIRED_FIELDS: tuple[str, ...] = ("title", "summary", "proposer", "proposed_at")
OPTIONAL_FIELDS: tuple[str, ...] = ("against_spec", "caller_ref")


ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset(REQUIRED_FIELDS) | frozenset(OPTIONAL_FIELDS)


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


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _contains_control_char(value: str) -> bool:
    return bool(_CONTROL_CHAR_RE.search(value))


FRONTMATTER_VALUE_FIELDS: frozenset[str] = frozenset(
    {"proposer", "proposed_at", "against_spec", "caller_ref"}
)


def _redaction_mod() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "a2a_intake_redaction", ROOT / "tools" / "mcp_bridges" / "redaction.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load tools/mcp_bridges/redaction.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_scrub(value: object) -> str:
    try:
        return _redaction_mod().safe_scrub(value)
    except Exception:
        return "[REDACTED:unclassified]"


def is_enabled(features_path: Path | None = None) -> bool:
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


def _append_audit(record: dict[str, Any], audit_path: Path | None = None) -> None:
    path = Path(audit_path) if audit_path is not None else DEFAULT_AUDIT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        with contextlib.suppress(AttributeError, OSError):
            import fcntl

            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            with contextlib.suppress(AttributeError, OSError, NameError):
                import fcntl

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

    decision: str
    admitted: bool
    reason: str
    path: Path | None = None
    denied_field: str | None = None


def _validate(submission: Any, admission_ref: str) -> tuple[str | None, str | None]:
    if not isinstance(submission, dict):
        return "malformed: submission must be an object/mapping", None


    for key in submission:
        if _normalize_key(key) in FORBIDDEN_FIELDS:
            return (
                f"forbidden field {key!r}: a goal proposal may not carry a "
                "control/gate/routing field (A2-2, C3/C4)",
                str(key),
            )


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


    for field_name in REQUIRED_FIELDS:
        value = submission.get(field_name)
        if not isinstance(value, str) or not value.strip():
            return f"malformed: missing or empty required field {field_name!r}", field_name


    proposer = submission["proposer"].strip()
    if not proposer or proposer.lower() in {"anonymous", "unknown", "none", "null"}:
        return "provenance-missing: no authenticated proposer identity", "proposer"


    if not _is_valid_iso8601(submission["proposed_at"]):
        return "malformed: proposed_at is not a valid ISO-8601 timestamp", "proposed_at"


    if not isinstance(admission_ref, str) or not admission_ref.strip():
        return "provenance-missing: no admission_ref from the admission edge", "admission_ref"


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
    if not is_enabled(features_path):


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


    front_matter: dict[str, str] = {
        "status": "proposed",
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


if __name__ == "__main__":
    import sys

    payload = json.loads(sys.stdin.read())
    ref = payload.pop("admission_ref", "") or os.environ.get("DASLAB_A2A_ADMISSION_REF", "manual-probe")
    result = intake_goal_proposal(payload, admission_ref=ref)
    print(json.dumps({"decision": result.decision, "reason": result.reason}))
