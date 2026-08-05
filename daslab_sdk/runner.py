
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


REPO_ROOT: Path = Path(__file__).resolve().parent.parent


_SCRIPTS_DIR: Path = REPO_ROOT / "scripts"


SETTING_SOURCES: list[str] = ["project"]


_FLAG: str = "ws_b_agent_sdk_runner"


_SDK_MODULE: str = "claude_agent_sdk"


PERMISSION_MODE: str = "default"


_DROP_ENV_KEYS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


QueryFn = Callable[[str, Mapping[str, Any]], str]


def _import_scripts(name: str) -> Any:
    try:
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))
        return importlib.import_module(name)
    except Exception:
        return None


def runner_flag_enabled(flag_path: Path | None = None) -> bool:
    ff = _import_scripts("feature_flags")
    if ff is None:
        return False
    try:
        return bool(ff.enabled(_FLAG, flag_path))
    except Exception:
        return False


def sdk_available() -> bool:
    try:
        return importlib.util.find_spec(_SDK_MODULE) is not None
    except (ImportError, ValueError):
        return False


def isolate_env(env: Mapping[str, str] | None) -> dict[str, str]:
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
                merged_pr=None,
                ci_status="",
                t7_pass=False,
                t7_score=0.0,
                start=created_at,
                end=created_at,
                final_status=tp.to_status,
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
    execute_wave: Any,
    *,
    created_at: str,
    flag_path: Path | None = None,
    **run_wave_kwargs: Any,
) -> WaveDispatchResult:
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
    attestation = wr.run_wave(plan, execute_wave, created_at=created_at, **run_wave_kwargs)
    return WaveDispatchResult(status=RunnerStatus.DISPATCHED, attestation=attestation)
