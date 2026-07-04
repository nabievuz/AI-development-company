"""governance/guardrails — per-role INPUT/OUTPUT guardrails (DAS-1471).

ORGANISM WS2 LOOM, GATE-3 / P10: a closed-loop "tripwire" so a wrong-scope or
wrong-output dispatch neither silently ships nor stalls. Each role gets:

* an **INPUT guardrail** — screens a ticket's *scope* before the agent accepts
  it (wrong-department, missing declared `consumes` inputs, gate-open
  violations: an unfinished `depends_on` or an open AADL predecessor gate); and
* an **OUTPUT guardrail** — screens the agent's *produced work* before it is
  accepted.

Contract
--------
Every per-role module ``governance/guardrails/<role>.py`` exposes two callables,
each returning a ``GuardrailResult`` = ``(ok: bool, feedback: str)``::

    def input_guardrail(ctx: GuardrailContext) -> GuardrailResult: ...
    def output_guardrail(ctx: GuardrailContext) -> GuardrailResult: ...

``feedback`` is empty when ``ok`` is True and a precise, actionable sentence when
``ok`` is False (it is written back into the ticket on an OUTPUT trip so the
re-dispatched agent knows exactly what to fix).

This package holds **only pure logic** — no file IO, no board reads. The context
is assembled by :mod:`guardrails.runner` (which reads the board / ROUTING) and
the retry/escalate loop lives in ``scripts/guardrail_dispatch.py``. Role modules
are loaded **by file path** (so hyphenated keys like ``security-lead.py`` are
valid) and MUST NOT be imported here — that keeps ``import guardrails`` free of
side effects and avoids the hyphen-in-module-name problem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# A guardrail returns (ok, feedback). ok=True → accept; ok=False → trip, with a
# human-actionable reason in feedback.
GuardrailResult = tuple[bool, str]

# Ticket-id shape used to tell a dependency reference (DAS-1234) apart from a
# plain frontmatter field name in a ticket's ``consumes:`` list.
_DAS_ID_RE = re.compile(r"^DAS-\d+$")


def ok_result() -> GuardrailResult:
    """A passing guardrail result: ``(True, "")``."""
    return (True, "")


def trip(feedback: str) -> GuardrailResult:
    """A tripped guardrail result: ``(False, feedback)`` — feedback required."""
    if not feedback or not feedback.strip():
        raise ValueError("a tripped guardrail must carry non-empty feedback")
    return (False, feedback.strip())


@dataclass
class GuardrailContext:
    """Everything a guardrail needs to decide — assembled by the runner.

    The context is deliberately plain data (no IO) so guardrails stay pure and
    unit-testable: a test builds a ``GuardrailContext`` directly, no board on
    disk required.
    """

    role: str                       # role key handling the ticket (assignee)
    role_dept: str                  # the role's dept, per ROUTING.md
    ticket_id: str                  # DAS-NNNN
    ticket_dept: str                # the ticket's declared dept
    status: str = ""                # ticket status at screen time
    consumes: list[str] = field(default_factory=list)      # declared inputs
    depends_on: list[str] = field(default_factory=list)    # dep ticket ids
    deps_status: dict[str, str] = field(default_factory=dict)  # dep id -> status
    gate_open: bool = False         # an AADL predecessor gate is still open
    body: str = ""                  # ticket body (markdown after frontmatter)
    output: str | None = None       # agent's produced work (OUTPUT screen only)
    frontmatter: dict[str, str] = field(default_factory=dict)  # raw fm passthrough

    def unfinished_deps(self) -> list[str]:
        """Dep ids whose status is not ``done`` (a gate-open violation source)."""
        return [d for d in self.depends_on if self.deps_status.get(d, "missing") != "done"]


@runtime_checkable
class Guardrail(Protocol):
    """Structural type a per-role guardrail callable satisfies."""

    def __call__(self, ctx: GuardrailContext) -> GuardrailResult: ...


# ---------------------------------------------------------------------------
# Default guardrails — the shared base every role reuses (and may extend).
# ---------------------------------------------------------------------------


def default_input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Screen ticket *scope* before accept. The three canonical failure modes:

    1. **wrong-department** — the ticket's ``dept`` does not match the role's
       dept (per ROUTING.md). The agent refuses work outside its department.
    2. **missing ``consumes``** — an input the ticket declares it needs is not
       resolvable: a ``DAS-*`` entry must be a ``done`` dependency; any other
       entry must be a present, non-empty frontmatter field.
    3. **gate-open** — a ``depends_on`` predecessor is not ``done``, or an AADL
       predecessor gate is still open (``ctx.gate_open``).

    Returns ``ok_result()`` when scope is acceptable, else ``trip(reason)``.
    """
    # (1) wrong-department
    if ctx.ticket_dept and ctx.role_dept and ctx.ticket_dept != ctx.role_dept:
        return trip(
            f"wrong-department: ticket dept '{ctx.ticket_dept}' != role "
            f"'{ctx.role}' dept '{ctx.role_dept}'; refuse and re-route to the "
            "owning department."
        )

    # (2) missing consumes / declared inputs
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

    # (3) gate-open (unfinished deps or an open AADL predecessor gate)
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
    """Screen produced *work* before accept (generic base).

    Trips when the agent produced nothing, or when the output still carries an
    unresolved-work marker (``UNRESOLVED``, ``TODO``, ``FIXME``) — a signal the
    work is not actually finished. Role modules layer discipline-specific checks
    on top (e.g. security sign-off, test evidence).
    """
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
