"""Guardrail for the ``frontend-em`` role (R4 rollout 2->32; DAS-1471).

INPUT: the shared scope screen (wrong-dept / missing-consumes / gate-open) is
sufficient — a Frontend EM reviews any engineering-dept ticket routed to it; no
extra relevance screen is added (the dept check already fences off non-
engineering work, and a keyword screen would false-trip legitimate frontend
tickets).

OUTPUT: a Frontend EM's Definition of Done is a *recorded review decision* — an
``in_review`` ticket is either merged (GATE-3, green CI) or returned with
concrete change requests, and the EM never merges work they authored. So the
produced work is only accepted when it records an explicit review decision
(approve / merge / GATE-3, or changes-requested / returned / blocked /
rejected). A review that states no decision is not done.
"""
from __future__ import annotations

import re

from guardrails import (
    GuardrailContext,
    GuardrailResult,
    default_input_guardrail,
    default_output_guardrail,
    ok_result,
    trip,
)

ROLE = "frontend-em"

# An explicit review / merge decision the EM MUST record. Tolerant and
# case-insensitive; the changes-requested forms require the *phrase* (request +
# change, in either order) so a bare "changes" in a diff description never
# counts as a decision on its own.
_REVIEW_DECISION = re.compile(
    r"(?i)(?:"
    r"\bapprov\w*\b|"              # approve / approved / approval
    r"\bmerg(?:e|ed|ing)\b|"      # merge / merged / merging
    r"\blgtm\b|"                   # LGTM
    r"\bgate-?\s?3\b|"            # GATE-3 / gate 3
    r"\breject\w*\b|"             # reject / rejected
    r"\bblocked\b|"               # blocked
    r"\breturned\b|"              # returned (to author)
    r"request\w*\s+chang\w*|"     # request(ed) changes
    r"chang\w*\s+request\w*"      # changes request(ed)
    r")"
)


def input_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """A Frontend EM accepts any in-department, gate-clear ticket."""
    return default_input_guardrail(ctx)


def output_guardrail(ctx: GuardrailContext) -> GuardrailResult:
    """Accept only a review that records an explicit merge / change decision."""
    ok, feedback = default_output_guardrail(ctx)
    if not ok:
        return (ok, feedback)
    if not _REVIEW_DECISION.search(ctx.output or ""):
        return trip(
            "no review decision recorded: a Frontend EM review must end in an "
            "explicit decision — approved/merged (GATE-3, green CI) or returned "
            "with concrete change requests; the output records neither."
        )
    return ok_result()
