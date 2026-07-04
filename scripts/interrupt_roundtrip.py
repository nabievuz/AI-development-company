#!/usr/bin/env python3
"""interrupt_roundtrip.py — helpers for the interrupt round-trip dispatch (DAS-1447).

When a ticket enters ``interrupted`` state, an agent has raised an interrupt card
(``board/interrupts/<card-id>.json``) and yielded.  The Founder answers by writing
``resume:<value>`` into the ticket body (anywhere in the body text, not in
frontmatter).  On the next ``/daslab-cycle`` wave, the orchestrator calls these
helpers to:

1. Detect which ``interrupted`` tickets have been answered (``parse_resume_marker``).
2. Find and load the matching interrupt card (``find_interrupt_card``).
3. Validate that the answer value is one of the card's declared options
   (``validate_resume_value``).
4. Build the injection string that goes into the dynamic tail of the resumed
   ticket's subagent prompt (``build_resume_injection``).

Design contract (DAS-1447 / DAS-1446)
--------------------------------------
- ``resume:<value>`` is the **only** mechanism by which a gate is answered.
  The orchestrator MUST NOT synthesise, default, or infer a value on the
  Founder's behalf.  A ticket without ``resume:<value>`` in its body stays
  ``interrupted`` (parked) indefinitely — gates always wait for the Founder.
- The resume value MUST exactly match one of the card's ``options`` (case-
  sensitive).  A mismatch is a hard skip: do not dispatch with an invalid value.
- The injection string is placed in **slot 3 "specific ticket text"** of the
  dynamic tail — strictly after the ticket body, before last-N scratchpad.
  It must NEVER be placed in the stable prefix (ADR 0006).
- Pre-interrupt side effects may already have run; the injection string warns
  the resuming agent to verify idempotency (DAS-1447 idempotency guard).

Usage (orchestrator, conceptual pseudocode)::

    from interrupt_roundtrip import detect_resumed_tickets

    for rt in detect_resumed_tickets(board_dir, interrupts_dir):
        # rt.ticket_path, rt.ticket_id, rt.resume_value, rt.card, rt.card_path
        # 1. Transition ticket: status interrupted -> in_progress (write frontmatter)
        # 2. Inject rt.injection_text into the dynamic tail of the subagent prompt
        #    (slot 3, after ticket body).
        # 3. Dispatch the ticket in the normal priority order as in_progress.

Schema consumed (DAS-1446 board/interrupts/schema.json)::

    {
      "question": "...",
      "options": ["option-a", "option-b"],
      "ticket": "DAS-NNNN",
      "payload": {},
      "created_by": "backend-eng-1"
    }
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _paths import ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BOARD_DIR = ROOT / "board" / "tickets"
_DEFAULT_INTERRUPTS_DIR = ROOT / "board" / "interrupts"

# Matches ``resume:<value>`` anywhere in a ticket body (not in frontmatter).
# Capture group 1 = the raw value string (may contain hyphens, letters, digits).
_RESUME_RE = re.compile(r"(?m)^resume:(.+)$")

# Frontmatter block — used to strip it before scanning the body for resume:.
_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ResumedTicket:
    """A ticket that was ``interrupted`` and now has a Founder ``resume:<value>``."""

    ticket_id: str
    ticket_path: Path
    resume_value: str
    card: dict
    card_path: Path
    injection_text: str = field(default="", repr=False)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_resume_marker(ticket_body: str) -> str | None:
    """Return the ``<value>`` from ``resume:<value>`` in *ticket_body*, or None.

    The marker is expected to appear on its own line in the body (below the
    frontmatter).  Only the first occurrence is returned; subsequent ones are
    ignored.  Leading/trailing whitespace on the value is stripped.

    Args:
        ticket_body: Full ticket file text, including frontmatter.

    Returns:
        The stripped value string, or ``None`` if no ``resume:`` marker is found.
    """
    # Strip frontmatter first so we only scan the body.
    body_only = _FM_RE.sub("", ticket_body, count=1)
    m = _RESUME_RE.search(body_only)
    if not m:
        return None
    return m.group(1).strip()


def find_interrupt_card(ticket_id: str, interrupts_dir: Path) -> tuple[Path, dict] | None:
    """Find the interrupt card JSON for *ticket_id* in *interrupts_dir*.

    Scans all ``*.json`` files in *interrupts_dir* whose ``"ticket"`` field
    matches *ticket_id*.  Returns ``(card_path, card_dict)`` for the card with
    the lexicographically latest filename (a simple proxy for "most recently
    created").  Returns ``None`` if no matching card is found.

    Args:
        ticket_id: The DAS-NNNN ticket id to look up (e.g. ``"DAS-1450"``).
        interrupts_dir: Path to ``board/interrupts/``.

    Returns:
        A ``(Path, dict)`` pair for the matching card, or ``None``.
    """
    if not interrupts_dir.is_dir():
        return None

    candidates: list[tuple[Path, dict]] = []
    for card_path in sorted(interrupts_dir.glob("*.json")):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if card.get("ticket") == ticket_id:
            candidates.append((card_path, card))

    if not candidates:
        return None

    # Latest by filename (lexicographic, since ids are monotonically increasing).
    return max(candidates, key=lambda t: t[0].name)


def validate_resume_value(value: str, card: dict) -> bool:
    """Return True if *value* is a valid option in *card*.

    The comparison is case-sensitive (matching the answer contract in
    board/interrupts/README.md).  Returns False if the card has no ``options``
    key or the options list is empty.

    Args:
        value: The Founder-provided answer string (from ``resume:<value>``).
        card:  The loaded interrupt card dict.

    Returns:
        ``True`` if *value* is in ``card["options"]``, else ``False``.
    """
    options: list = card.get("options", [])
    return isinstance(options, list) and value in options


def build_resume_injection(value: str, card: dict) -> str:
    """Build the dynamic-tail injection string for a resumed ticket.

    The returned string is placed in **slot 3 ("specific ticket text")** of the
    dynamic tail (strictly after the ticket body, before last-N scratchpad,
    and always after the last ``cache_control`` breakpoint — NEVER in the stable
    prefix per ADR 0006).

    The injection warns the resuming agent to re-check idempotency for any
    pre-interrupt side effects (merge, spend, message send) that may already
    have run.

    Args:
        value: The validated resume value (one of ``card["options"]``).
        card:  The loaded interrupt card dict.

    Returns:
        A markdown-formatted injection string for the dynamic tail.
    """
    options_str = ", ".join(f'"{o}"' for o in card.get("options", []))
    payload_str = json.dumps(card.get("payload", {}), ensure_ascii=False, indent=2)
    question = card.get("question", "(no question text)")

    return (
        "\n---\n"
        "**RESUME CONTEXT (interrupt round-trip — DAS-1447)**\n\n"
        f"This ticket was previously paused (`interrupted`) and the Founder has "
        f"now answered the interrupt gate.\n\n"
        f"- **Original question:** {question}\n"
        f"- **Available options:** [{options_str}]\n"
        f"- **Founder's answer (`resume:<value>`):** `{value}`\n"
        f"- **Interrupt card payload** (agent context saved before the pause):\n"
        f"```json\n{payload_str}\n```\n\n"
        "**Idempotency check (mandatory):** Pre-interrupt side effects (merges, "
        "charges, message sends) may already have run before the pause.  Before "
        "re-executing any such action, verify it has not already been applied — "
        "use a guard-before-act pattern: check-if-already-done, an idempotency "
        "key, or a naturally re-runnable operation.  Do NOT double-apply.\n"
        "---\n"
    )


# ---------------------------------------------------------------------------
# High-level scanner (orchestrator entry point)
# ---------------------------------------------------------------------------

def detect_resumed_tickets(
    board_dir: Path,
    interrupts_dir: Path,
) -> list[ResumedTicket]:
    """Scan *board_dir* for ``interrupted`` tickets with a ``resume:<value>``.

    For each such ticket:
    - Locates the interrupt card in *interrupts_dir*.
    - Validates the resume value against the card's options.
    - Builds the injection string for the dynamic tail.

    Tickets whose value fails validation, or whose card cannot be found, are
    skipped with a warning printed to stderr (the orchestrator should log these
    in the wave-log).

    Gates ALWAYS wait for the Founder: an ``interrupted`` ticket WITHOUT a
    ``resume:`` marker is NOT returned — it stays parked.

    Args:
        board_dir:      Path to ``board/tickets/`` (or a project's
                        ``board-tickets/`` directory).
        interrupts_dir: Path to ``board/interrupts/``.

    Returns:
        List of :class:`ResumedTicket` instances, one per valid resumed ticket.
        Empty list if none found.
    """
    resumed: list[ResumedTicket] = []

    for ticket_path in sorted(board_dir.glob("DAS-*.md")):
        text = ticket_path.read_text(encoding="utf-8")

        # Quick check: only interrupted tickets are candidates.
        if "status: interrupted" not in text and "status:interrupted" not in text:
            continue

        # Parse frontmatter to confirm status field.
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not fm_match:
            continue
        fm_block = fm_match.group(1)
        status_match = re.search(r"^status:\s*(\S+)", fm_block, re.MULTILINE)
        if not status_match or status_match.group(1).strip() != "interrupted":
            continue

        ticket_id_match = re.search(r"^id:\s*(\S+)", fm_block, re.MULTILINE)
        if not ticket_id_match:
            continue
        ticket_id = ticket_id_match.group(1).strip()

        # Look for resume:<value> in the body.
        resume_value = parse_resume_marker(text)
        if resume_value is None:
            # No Founder answer yet — ticket stays parked (gates always wait).
            continue

        # Find the interrupt card.
        card_result = find_interrupt_card(ticket_id, interrupts_dir)
        if card_result is None:
            print(
                f"interrupt_roundtrip: WARNING — resumed ticket {ticket_id} has "
                f"resume:{resume_value} but no interrupt card found in {interrupts_dir}; "
                "skipping dispatch.",
                file=sys.stderr,
            )
            continue
        card_path, card = card_result

        # Validate the resume value against the card's options.
        if not validate_resume_value(resume_value, card):
            options = card.get("options", [])
            print(
                f"interrupt_roundtrip: ERROR — resume value '{resume_value}' for "
                f"{ticket_id} is not in card options {options}; "
                "skipping dispatch (do not auto-correct).",
                file=sys.stderr,
            )
            continue

        # Build the dynamic-tail injection string.
        injection = build_resume_injection(resume_value, card)

        resumed.append(
            ResumedTicket(
                ticket_id=ticket_id,
                ticket_path=ticket_path,
                resume_value=resume_value,
                card=card,
                card_path=card_path,
                injection_text=injection,
            )
        )

    return resumed


# ---------------------------------------------------------------------------
# CLI (smoke-test: list resumed tickets on the current board)
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    """Print a summary of resumed interrupted tickets on the current board."""
    board_dir = _DEFAULT_BOARD_DIR
    interrupts_dir = _DEFAULT_INTERRUPTS_DIR

    if not board_dir.is_dir():
        print(f"ERROR: board directory not found: {board_dir}", file=sys.stderr)
        return 2

    resumed = detect_resumed_tickets(board_dir, interrupts_dir)
    if not resumed:
        print("interrupt_roundtrip: no resumed interrupted tickets found.")
        return 0

    print(f"interrupt_roundtrip: {len(resumed)} resumed ticket(s):")
    for rt in resumed:
        print(f"  {rt.ticket_id}  resume_value={rt.resume_value!r}  card={rt.card_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
