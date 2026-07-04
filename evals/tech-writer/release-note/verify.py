"""Soft (rubric-scored) verifier marker — tech-writer / release-note.

This is a SOFT task: there is no single deterministic right answer, so scoring is
delegated to the reused T7 rubric via scripts/check_t7_quality.py (the runner
handles this when it sees ``RUBRIC = True``). Per-dimension scores come from a
haiku-as-judge pass at run time, or from the recorded submission's ``judge_scores``
field when scoring offline.

There is deliberately NO verify() function here — a parallel/forked scorer is
forbidden. The runner reuses config/t7_rubric.yaml dimensions and weights.
"""

from __future__ import annotations

#: Marks this task as rubric-scored (haiku-as-judge) rather than deterministic.
RUBRIC = True

#: Guidance a live haiku judge would receive (documented for the live path; the
#: offline example uses recorded judge_scores). Dimensions/weights are NOT defined
#: here — they are read from config/t7_rubric.yaml (the immutable SSOT).
JUDGE_GUIDANCE = (
    "Score the release note on the T7 rubric dimensions. Reward a note that is "
    "accurate to the changeset, complete (what/why/action), and free of internal "
    "jargon. Penalise invented facts. Return a score in [0,1] per dimension."
)
