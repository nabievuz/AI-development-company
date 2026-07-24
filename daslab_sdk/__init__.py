"""daslab_sdk — WS-B headless Agent SDK runner (ADR-0034, DAS-1555).

A thin, feature-flagged (``ws_b_agent_sdk_runner``, default OFF) wrapper over the
Claude **Agent SDK** ``query(prompt, options)`` for headless ticket/wave dispatch.
Additive to ``/daslab-cycle``; inert until the flag is ON and the SDK is present.

Public surface:

* :func:`~daslab_sdk.runner.dispatch_ticket` — dispatch one ticket via ``query()``.
* :func:`~daslab_sdk.runner.dispatch_wave` — forward ``(plan, results)`` to the
  single ``scripts/wave_runner.py:run_wave`` seam (new caller, not a re-impl).
* :func:`~daslab_sdk.runner.results_from_dispatches` — assemble ``WaveResults``.
* :func:`~daslab_sdk.runner.build_agent_options` / :func:`~daslab_sdk.runner.isolate_env`
  — the pinned ``cwd``/``setting_sources``/``env`` load-shape (SR-1/SR-5).
* Admission seam (:class:`~daslab_sdk.contracts.Admitter` &c.) — the interface
  DAS-1556 fills; the runner depends on it by injection, never re-implements it.
"""

from __future__ import annotations

from .contracts import (
    AdmissionDecision,
    AdmissionOutcome,
    Admitter,
    RunnerStatus,
    TicketDispatchResult,
    WaveDispatchResult,
)
from .runner import (
    REPO_ROOT,
    SETTING_SOURCES,
    build_agent_options,
    dispatch_ticket,
    dispatch_wave,
    isolate_env,
    results_from_dispatches,
    runner_flag_enabled,
    sdk_available,
)

__all__ = [
    "REPO_ROOT",
    "SETTING_SOURCES",
    "AdmissionDecision",
    "AdmissionOutcome",
    "Admitter",
    "RunnerStatus",
    "TicketDispatchResult",
    "WaveDispatchResult",
    "build_agent_options",
    "dispatch_ticket",
    "dispatch_wave",
    "isolate_env",
    "results_from_dispatches",
    "runner_flag_enabled",
    "sdk_available",
]
