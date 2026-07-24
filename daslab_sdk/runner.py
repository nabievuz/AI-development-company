"""daslab_sdk.runner — the WS-B core headless runner (DAS-1555, ADR-0034 SR-1/3/4/5).

A thin wrapper over the Claude **Agent SDK** ``query(prompt, options)`` for
headless ticket/wave dispatch.  It is *additive* to ``/daslab-cycle`` and inert
until the ``ws_b_agent_sdk_runner`` feature flag is ON (default OFF).

Boundaries this module holds by construction:

* **SR-1 — load the repo's own agents.**  Every dispatch pins ``cwd`` to the repo
  root and ``setting_sources=["project"]``, so the SDK loads the repo's existing
  ``.claude/agents`` shims, skills, ``CLAUDE.md``, hooks, and ``.mcp.json``
  (ArcRift) VERBATIM.  There is **no** code path that builds a role from anything
  other than a generated shim — no ported-agent constructor, no inline system
  prompt.  A role that is not a generated shim is unreachable here.
* **SR-2 / SR-3 — no mechanical decision.**  The runner picks no model, no role,
  and no wave order.  It requires an explicit ``model`` (FR-002, fail-closed) and
  routes every dispatch through an injected admission gateway (DAS-1556); it never
  invents an admit.  Wave execution is delegated to the ONE post-decision seam,
  ``scripts/wave_runner.py:run_wave`` — the runner is a *new caller*, never a
  second producer of the event/attestation stream.
* **SR-4 — board/Git law.**  The runner records no routing field and never merges
  a pull request: a dispatch advances a ticket toward its reviewer, nothing more.
* **SR-5 — flag + isolation.**  Flag OFF ⇒ fully inert (no SDK import, no board
  read, no admission).  The Agent SDK is an *opt-in* extra
  (``daslab_sdk/requirements-sdk.txt``); absent ⇒ the runner is *unavailable*, not
  broken.  The child ``env`` is CONSTRUCTED, never an ``os.environ`` passthrough,
  and drops metered-key vars so the subscription profile resolves.

No live model call is made from this module in tests or CI: the SDK boundary is
injectable (``query_fn``) and the SDK itself is not a core dependency.  The live
end-to-end drive is verified at flip time (DAS-1558).
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .contracts import (
    AdmissionOutcome,
    Admitter,
    RunnerStatus,
    TicketDispatchResult,
    WaveDispatchResult,
)

__all__ = [
    "REPO_ROOT",
    "SETTING_SOURCES",
    "build_agent_options",
    "dispatch_ticket",
    "dispatch_wave",
    "isolate_env",
    "results_from_dispatches",
    "runner_flag_enabled",
    "sdk_available",
]

#: Absolute repo root — the parent of this package dir.  Pinned as ``cwd`` on
#: every dispatch so project settings resolve to the repo, not the caller's CWD.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

#: The scripts dir holding the ``run_wave`` seam and the feature-flag reader.
_SCRIPTS_DIR: Path = REPO_ROOT / "scripts"

#: SR-1: load ONLY the repo's own project settings (the 32 shims, CLAUDE.md,
#: hooks, .mcp.json) — never a rebuilt or ported agent set.
SETTING_SOURCES: list[str] = ["project"]

#: The feature flag that gates the entire headless path (ADR-0019; default OFF).
_FLAG: str = "ws_b_agent_sdk_runner"

#: The Python import name of the Claude Agent SDK (opt-in extra).
_SDK_MODULE: str = "claude_agent_sdk"

#: Non-interactive permission mode that STILL honors the repo's PreToolUse hooks
#: (SR-4 / WS-A) — never a bypass mode.  The exact value is re-confirmed at the
#: DAS-1558 flip; kept as a single named knob.
PERMISSION_MODE: str = "default"

#: Host credential vars that must NEVER reach the child env: a metered key — even
#: an empty one — wins its precedence slot and shadows the subscription OAuth
#: profile (ADR-0034 §4.1/§6.2).  DAS-1556's auth wiring refines the allow-set.
_DROP_ENV_KEYS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

#: The injectable SDK boundary: (prompt, options-dict) -> produced output text.
QueryFn = Callable[[str, Mapping[str, Any]], str]


def _import_scripts(name: str) -> Any:
    """Self-locating, guarded import of a ``scripts/`` module; ``None`` on failure.

    Mirrors the bootstrap the sibling scripts use.  Guarded so a missing/broken
    ``scripts`` tree degrades to a clean *unavailable* result instead of a crash.
    """
    try:
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 — any import failure ⇒ unavailable, never crash
        return None


def runner_flag_enabled(flag_path: Path | None = None) -> bool:
    """Is ``ws_b_agent_sdk_runner`` ON?  Fail-closed OFF if the flag is unreadable."""
    ff = _import_scripts("feature_flags")
    if ff is None:
        return False
    try:
        return bool(ff.enabled(_FLAG, flag_path))
    except Exception:  # noqa: BLE001 — unreadable flag ⇒ inert (fail-closed OFF)
        return False


def sdk_available() -> bool:
    """Is the Claude Agent SDK importable?  Uses ``find_spec`` — never imports it."""
    try:
        return importlib.util.find_spec(_SDK_MODULE) is not None
    except (ImportError, ValueError):
        return False


def isolate_env(env: Mapping[str, str] | None) -> dict[str, str]:
    """Return a CONSTRUCTED child env — never an ``os.environ`` passthrough (SR-5).

    Carries only what the caller explicitly supplied and always drops the
    metered-key vars so the subscription OAuth profile resolves (§4.1/§6.2).  With
    no ``env`` supplied the floor is an empty map, not the host environment.
    """
    built: dict[str, str] = dict(env) if env else {}
    for key in _DROP_ENV_KEYS:
        built.pop(key, None)
    return built


def build_agent_options(
    *,
    model: str,
    env: Mapping[str, str] | None = None,
    permission_mode: str = PERMISSION_MODE,
    cwd: Path | str | None = None,
) -> dict[str, Any]:
    """Build the pinned ``ClaudeAgentOptions`` mapping for one dispatch (SR-1).

    A plain dict (the contract shape) so it is constructible and assertable
    without the SDK installed; the real driver converts it to the SDK's
    ``ClaudeAgentOptions``.  ``model`` is a required, non-empty precondition
    (FR-002) — validated before any options are returned.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("explicit non-empty model required per FR-002 / LAW 3")
    return {
        "cwd": str(cwd or REPO_ROOT),
        "setting_sources": list(SETTING_SOURCES),
        "model": model,
        "env": isolate_env(env),
        "permission_mode": permission_mode,
    }


def _default_query_fn(prompt: str, options: Mapping[str, Any]) -> str:
    """Drive the real Agent SDK ``query()`` to completion (headless).

    Reached only with the SDK installed, the flag ON, and an ADMIT — so never in
    CI (the SDK is an opt-in extra) and never a live call in tests (which inject a
    ``query_fn``).  The live end-to-end drive is verified at flip time (DAS-1558).
    """
    import asyncio

    sdk = importlib.import_module(_SDK_MODULE)
    options_obj = sdk.ClaudeAgentOptions(**dict(options))

    async def _drive() -> str:
        chunks: list[str] = []
        async for message in sdk.query(prompt=prompt, options=options_obj):
            text = getattr(message, "result", None) or getattr(message, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        return "".join(chunks)

    return asyncio.run(_drive())


def dispatch_ticket(
    *,
    ticket_id: str,
    role: str,
    model: str,
    prompt: str,
    env: Mapping[str, str] | None = None,
    admit: Admitter | None = None,
    query_fn: QueryFn | None = None,
    permission_mode: str = PERMISSION_MODE,
    flag_path: Path | None = None,
) -> TicketDispatchResult:
    """Headlessly dispatch ONE ticket through the Agent SDK's ``query()``.

    The gate order is load-bearing — every non-dispatch path returns cleanly and
    reaches no model call:

      1. **SR-5 flag gate.**  Flag OFF ⇒ inert no-op (no SDK import, no admission).
      2. **SR-5 SDK availability.**  No injected ``query_fn`` and no SDK installed
         ⇒ clean *unavailable*, not a crash.
      3. **FR-002 explicit model.**  Absent/empty ``model`` ⇒ fail-closed refusal
         *before* the model call.
      4. **SR-2/SR-3 admission.**  No admitter wired ⇒ fail-closed refusal (the
         runner never self-admits); a HOLD verdict ⇒ no dispatch.
      5. **SR-1 dispatch.**  Only inside an ADMIT is ``query()`` called, with
         ``cwd``/``setting_sources`` pinned to load the repo's own agents.
    """
    if not runner_flag_enabled(flag_path):
        return TicketDispatchResult(
            ticket_id=ticket_id,
            status=RunnerStatus.INERT_FLAG_OFF,
            role=role,
            model=model,
            reason="ws_b_agent_sdk_runner OFF — headless path inert",
        )

    if query_fn is None and not sdk_available():
        return TicketDispatchResult(
            ticket_id=ticket_id,
            status=RunnerStatus.UNAVAILABLE_NO_SDK,
            role=role,
            model=model,
            reason="Claude Agent SDK not installed (opt-in extra) — runner unavailable",
        )

    if not isinstance(model, str) or not model.strip():
        return TicketDispatchResult(
            ticket_id=ticket_id,
            status=RunnerStatus.REFUSED_NO_MODEL,
            role=role,
            model="",
            reason="explicit model required per FR-002 / LAW 3 — rejected before the model call",
        )

    if admit is None:
        return TicketDispatchResult(
            ticket_id=ticket_id,
            status=RunnerStatus.REFUSED_NO_ADMITTER,
            role=role,
            model=model,
            reason="admission gateway (DAS-1556) not wired — fail-closed, no self-admit",
        )

    decision = admit(ticket_id=ticket_id, role=role, model=model)
    if decision.outcome is not AdmissionOutcome.ADMIT:
        return TicketDispatchResult(
            ticket_id=ticket_id,
            status=RunnerStatus.ADMISSION_HOLD,
            role=role,
            model=model,
            reason=decision.reason or "admission gateway returned HOLD",
        )

    options = build_agent_options(model=model, env=env, permission_mode=permission_mode)
    drive = query_fn or _default_query_fn
    output = drive(prompt, options)
    return TicketDispatchResult(
        ticket_id=ticket_id,
        status=RunnerStatus.DISPATCHED,
        role=role,
        model=model,
        output=output or "",
        dispatched=True,
    )


def results_from_dispatches(
    plan: Any,
    dispatch_results: list[TicketDispatchResult],
    *,
    created_at: str,
    request_satisfied: bool = True,
    in_loop: bool = False,
    progress_being_made: bool = True,
) -> Any:
    """Assemble a ``wave_runner.WaveResults`` from observed dispatch outcomes.

    Pure pairing of ``plan.tickets`` with their ``TicketDispatchResult`` — the
    "(plan, results) assembly" the runner hands to ``run_wave``.  Enforces SR-4 by
    construction: ``merged_pr`` is always empty (the runner never self-merges) and
    the ticket's close status is the plan's routing target (e.g. ``in_review``),
    never a merge-derived ``done``.
    """
    wr = _import_scripts("wave_runner")
    if wr is None:
        raise RuntimeError("wave_runner seam unavailable — cannot assemble WaveResults")
    by_id = {d.ticket_id: d for d in dispatch_results}
    tickets = []
    for tp in plan.tickets:
        d = by_id.get(tp.ticket_id)
        dispatched = bool(d and d.dispatched)
        tickets.append(
            wr.TicketResult(
                ticket_id=tp.ticket_id,
                outcome="dispatched" if dispatched else "not_dispatched",
                merged_pr=None,  # SR-4: the runner NEVER records a self-merge
                ci_status="",
                t7_pass=False,
                t7_score=0.0,
                start=created_at,
                end=created_at,
                final_status=tp.to_status,  # routing target from the plan, never merge-`done`
                output=(d.output if d else ""),
            )
        )
    return wr.WaveResults(
        tickets=tickets,
        request_satisfied=request_satisfied,
        in_loop=in_loop,
        progress_being_made=progress_being_made,
    )


def dispatch_wave(
    plan: Any,
    results: Any,
    *,
    created_at: str,
    flag_path: Path | None = None,
    **run_wave_kwargs: Any,
) -> WaveDispatchResult:
    """Forward one wave to the single post-decision seam ``run_wave`` (SR-3).

    A NEW CALLER of ``scripts/wave_runner.py:run_wave`` — never a re-implementation
    of dispatch/selection and never a second event/attestation producer.  Inert
    with the flag OFF; the ``organism_emit`` gate on ``run_wave`` itself is
    inherited, not shadowed by a second toggle here.
    """
    if not runner_flag_enabled(flag_path):
        return WaveDispatchResult(
            status=RunnerStatus.INERT_FLAG_OFF,
            reason="ws_b_agent_sdk_runner OFF — headless wave path inert",
        )
    wr = _import_scripts("wave_runner")
    if wr is None:
        return WaveDispatchResult(
            status=RunnerStatus.UNAVAILABLE_NO_SEAM,
            reason="wave_runner seam unimportable — runner unavailable",
        )
    attestation = wr.run_wave(plan, results, created_at=created_at, **run_wave_kwargs)
    return WaveDispatchResult(status=RunnerStatus.DISPATCHED, attestation=attestation)
