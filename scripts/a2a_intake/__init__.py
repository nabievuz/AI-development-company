"""scripts/a2a_intake — the A2A goal-proposal intake handler package (DAS-1611).

See ``scripts/a2a_intake/intake.py`` for the implementation and
``docs/design/a2a-outbound.md`` §1 for the design this builds against.

Import convention (matches the rest of ``scripts/`` — no ``scripts/__init__.py``
exists, so tests add ``scripts/`` to ``sys.path`` and import this as a top-level
package, e.g. ``import a2a_intake`` / ``from a2a_intake import intake_goal_proposal``).
"""
from __future__ import annotations

from .intake import (
    FLAG,
    FORBIDDEN_FIELDS,
    REQUIRED_FIELDS,
    IntakeResult,
    intake_goal_proposal,
    is_enabled,
)

__all__ = [
    "FLAG",
    "FORBIDDEN_FIELDS",
    "REQUIRED_FIELDS",
    "IntakeResult",
    "intake_goal_proposal",
    "is_enabled",
]
