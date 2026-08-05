from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

GuardrailResult = tuple[bool, str]


_DAS_ID_RE = re.compile(r"^DAS-\d+$")


def ok_result() -> GuardrailResult:
    return (True, "")


def trip(feedback: str) -> GuardrailResult:
    if not feedback or not feedback.strip():
        raise ValueError("a tripped guardrail must carry non-empty feedback")
    return (False, feedback.strip())


@dataclass
class GuardrailContext:

    role: str
    role_dept: str
    ticket_id: str
    ticket_dept: str
    status: str = ""
    consumes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    deps_status: dict[str, str] = field(default_factory=dict)
    gate_open: bool = False
    body: str = ""
    output: str | None = None
    frontmatter: dict[str, str] = field(default_factory=dict)

    def unfinished_deps(self) -> list[str]:
        return [d for d in self.depends_on if self.deps_status.get(d, "missing") != "done"]


@runtime_checkable
class Guardrail(Protocol):

    def __call__(self, ctx: GuardrailContext) -> GuardrailResult: ...


def default_input_guardrail(ctx: GuardrailContext) -> GuardrailResult:

    if ctx.ticket_dept and ctx.role_dept and ctx.ticket_dept != ctx.role_dept:
        return trip(
            f"wrong-department: ticket dept '{ctx.ticket_dept}' != role "
            f"'{ctx.role}' dept '{ctx.role_dept}'; refuse and re-route to the "
            "owning department."
        )


    for item in ctx.consumes:
        name = item.strip()
        if not name:
            continue
        if _DAS_ID_RE.match(name):
            if ctx.deps_status.get(name, "missing") != "done":
                return trip(
                    f"missing consumes: required input '{name}' is not a 'done' "
                    f"dependency (status={ctx.deps_status.get(name, 'missing')})."
                )
        else:
            value = (ctx.frontmatter.get(name, "") or "").strip()
            if not value:
                return trip(
                    f"missing consumes: declared input field '{name}' is absent "
                    "or empty in the ticket frontmatter."
                )


    unfinished = ctx.unfinished_deps()
    if unfinished:
        return trip(
            f"gate-open: depends_on not satisfied — {unfinished} are not 'done'; "
            "the ticket is not actionable yet."
        )
    if ctx.gate_open:
        return trip(
            "gate-open: an AADL predecessor gate is still open; the ticket is "
            "not actionable until the prior stage gate closes."
        )

    return ok_result()


def default_output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    output = (ctx.output or "").strip()
    if not output:
        return trip(
            "empty output: the agent produced no work for the ticket; re-run "
            "and produce the artifact the ticket asks for."
        )
    for marker in ("UNRESOLVED", "TODO", "FIXME"):
        if marker in output:
            return trip(
                f"unresolved work: output still contains a '{marker}' marker; "
                "resolve it before the work can be accepted."
            )
    return ok_result()
