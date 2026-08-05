#!/usr/bin/env python3


from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from _paths import ROOT

_DEFAULT_BOARD_DIR = ROOT / "board" / "tickets"
_DEFAULT_INTERRUPTS_DIR = ROOT / "board" / "interrupts"


_RESUME_RE = re.compile(r"(?m)^resume:(.+)$")


_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


@dataclass
class ResumedTicket:

    ticket_id: str
    ticket_path: Path
    resume_value: str
    card: dict
    card_path: Path
    injection_text: str = field(default="", repr=False)


def parse_resume_marker(ticket_body: str) -> str | None:

    body_only = _FM_RE.sub("", ticket_body, count=1)
    m = _RESUME_RE.search(body_only)
    if not m:
        return None
    return m.group(1).strip()


def find_interrupt_card(ticket_id: str, interrupts_dir: Path) -> tuple[Path, dict] | None:
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


    return max(candidates, key=lambda t: t[0].name)


def validate_resume_value(value: str, card: dict) -> bool:
    options: list = card.get("options", [])
    return isinstance(options, list) and value in options


def build_resume_injection(value: str, card: dict) -> str:
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


def detect_resumed_tickets(
    board_dir: Path,
    interrupts_dir: Path,
) -> list[ResumedTicket]:
    resumed: list[ResumedTicket] = []

    for ticket_path in sorted(board_dir.glob("DAS-*.md")):
        text = ticket_path.read_text(encoding="utf-8")


        if "status: interrupted" not in text and "status:interrupted" not in text:
            continue


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


        resume_value = parse_resume_marker(text)
        if resume_value is None:

            continue


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


        if not validate_resume_value(resume_value, card):
            options = card.get("options", [])
            print(
                f"interrupt_roundtrip: ERROR — resume value '{resume_value}' for "
                f"{ticket_id} is not in card options {options}; "
                "skipping dispatch (do not auto-correct).",
                file=sys.stderr,
            )
            continue


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


def _cli_main() -> int:
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
