#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import run_workspace as _rw
import wave_planner as _wp
from _paths import ROOT

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

DEFAULT_BOARD_DIR = ROOT / "board" / "tickets"
DEFAULT_ORG_PATH = ROOT / "config" / "org.yaml"
AGENTS_DIR = ROOT / ".claude" / "agents"
DEFAULT_CLAUDE_BIN = "claude"
DEFAULT_PERMISSION_MODE = "acceptEdits"
DEFAULT_TIMEOUT_SECONDS = 1800.0
TRUE_VALUES = {"1", "true", "yes", "on"}

DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "Bash(git:*)",
    "Bash(npm:*)",
    "Bash(npx:*)",
    "Bash(node:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
)


class InvokerError(RuntimeError):
    pass


def _env_path(env: Mapping[str, str], key: str, default: Path) -> Path:
    raw = env.get(key, "").strip()
    return Path(raw).expanduser().resolve() if raw else default


def _env_text(env: Mapping[str, str], key: str, default: str) -> str:
    return env.get(key, "").strip() or default


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise InvokerError(f"{key} must be a number; got {raw!r}") from exc


def _env_flag(env: Mapping[str, str], key: str) -> bool:
    return env.get(key, "").strip().lower() in TRUE_VALUES


def _env_tools(env: Mapping[str, str], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    if key not in env:
        return default
    raw = env.get(key, "").strip()
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class InvokerConfig:
    board_dir: Path = DEFAULT_BOARD_DIR
    org_root: Path = ROOT
    org_path: Path = DEFAULT_ORG_PATH
    claude_bin: str = DEFAULT_CLAUDE_BIN
    permission_mode: str = DEFAULT_PERMISSION_MODE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    dry_run: bool = False
    allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS
    worktree_isolation: bool = True
    verify_command: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> InvokerConfig:
        env = os.environ if env is None else env
        return cls(
            board_dir=_env_path(env, "DASLAB_BOARD_DIR", DEFAULT_BOARD_DIR),
            org_root=_env_path(env, "DASLAB_ORG_ROOT", ROOT),
            org_path=_env_path(env, "DASLAB_ORG_PATH", DEFAULT_ORG_PATH),
            claude_bin=_env_text(env, "DASLAB_CLAUDE_BIN", DEFAULT_CLAUDE_BIN),
            permission_mode=_env_text(env, "DASLAB_PERMISSION_MODE", DEFAULT_PERMISSION_MODE),
            timeout_seconds=_env_float(env, "DASLAB_AGENT_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
            dry_run=_env_flag(env, "DASLAB_INVOKER_DRY_RUN"),
            allowed_tools=_env_tools(env, "DASLAB_ALLOWED_TOOLS", DEFAULT_ALLOWED_TOOLS),
            worktree_isolation=env.get("DASLAB_WORKTREE_ISOLATION", "1").strip().lower()
            in TRUE_VALUES,
            verify_command=_env_text(env, "DASLAB_VERIFY_CMD", ""),
        )


def find_ticket(board_dir: Path, ticket_id: str) -> Path:
    if not board_dir.is_dir():
        raise InvokerError(f"board directory not found: {board_dir}")
    matches = [
        path
        for path in sorted(board_dir.glob("*.md"))
        if _wp.ticket_id_from_stem(path.stem) == ticket_id
    ]
    if not matches:
        raise InvokerError(f"no ticket file for {ticket_id} under {board_dir}")
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise InvokerError(f"{ticket_id} matches more than one ticket file: {names}")
    return matches[0]


def ticket_fields(ticket_path: Path) -> dict[str, str]:
    return _wp.parse_frontmatter(ticket_path.read_text(encoding="utf-8"))


def project_dir_for(ticket_path: Path, org_root: Path) -> Path | None:
    slug = ticket_fields(ticket_path).get("project", "").strip()
    if not slug:
        return None
    candidate = org_root / "projects" / slug
    return candidate if candidate.is_dir() else None


def load_org_roles(org_path: Path = DEFAULT_ORG_PATH) -> tuple[str, ...]:
    return tuple(sorted(_wp.load_org_model(org_path).role_models))


def require_agent(role: str, agents_dir: Path = AGENTS_DIR) -> Path:
    charter = agents_dir / f"{role}.md"
    if not charter.is_file():
        raise InvokerError(f"no agent charter for role {role!r} at {charter}")
    return charter


def resolve_role_and_model(ticket_path: Path, role: str, model: str, org_path: Path) -> tuple[str, str]:
    fields = ticket_fields(ticket_path)
    resolved_role = role or fields.get("assignee", "").strip()
    if not resolved_role:
        raise InvokerError(f"{ticket_path.name} has no assignee; pass --role")
    resolved_model = model
    if not resolved_model:
        resolved_model = _wp.load_org_model(org_path).model_for(resolved_role)
    return resolved_role, resolved_model


def build_prompt(
    request,
    ticket_path: Path,
    project_dir: Path | None,
    allowed_tools: tuple[str, ...] = (),
    isolated: bool = False,
) -> str:
    lines = [
        f"You are {request.role}. Work strictly inside your role charter.",
        f"Execute exactly one ticket: {ticket_path}",
        f"Wave goal: {request.goal or '(none stated)'}",
        f"Wave run id: {request.run_id}, attempt {request.attempt}.",
    ]
    if project_dir is not None and isolated:
        lines.append(
            f"The product checkout for this run is your own git worktree: {project_dir}. "
            "It is on this ticket's branch and no other role can see it. Commit there. "
            "Never run checkout, reset or stash against the shared project tree — that is "
            "how a concurrent role's uncommitted work gets destroyed."
        )
        lines.append(
            "A fresh worktree carries no installed dependencies. Run the project's install "
            "step there before you read any build or test result, and do not symlink the "
            "shared one — a red first build is almost always the missing install, not a "
            "code defect, and reporting it as a defect wastes the next role's wave."
        )
    elif project_dir is not None:
        lines.append(f"The product this ticket is about lives at: {project_dir}")
    if allowed_tools:
        lines.append(
            "Shell commands granted for this run: "
            + ", ".join(allowed_tools)
            + ". Anything outside that list is denied — do not block on it, log it and route it."
        )
    lines.extend(
        [
            "Read the ticket first, then do what it asks. Do not pick up any other ticket.",
            "Stay inside the acceptance criteria; raise anything outside them instead of doing it.",
            "When the work is done, update the ticket file: set its status field and append a"
            " '## Log' entry saying what changed and how you verified it.",
            "End with a short plain-text report: what you changed, what you verified, and what"
            " you deliberately left undone.",
        ]
    )
    return "\n".join(lines)


def build_command(config: InvokerConfig, request, prompt: str, project_dir: Path | None) -> list[str]:
    argv = [
        config.claude_bin,
        "-p",
        prompt,
        "--agent",
        request.role,
        "--output-format",
        "json",
        "--permission-mode",
        config.permission_mode,
    ]
    if request.model:
        argv.extend(["--model", request.model])
    if project_dir is not None:
        argv.extend(["--add-dir", str(project_dir)])
    if config.allowed_tools:
        argv.extend(["--allowedTools", ",".join(config.allowed_tools)])
    return argv


def run_claude(argv: list[str], config: InvokerConfig) -> dict[str, object]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(config.org_root),
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise InvokerError(f"claude CLI not found on PATH: {config.claude_bin}") from exc
    except subprocess.TimeoutExpired as exc:
        raise InvokerError(f"claude exceeded {config.timeout_seconds}s and was killed") from exc

    stdout = proc.stdout.strip()
    if not stdout:
        detail = proc.stderr.strip()[:300] or "(no stderr)"
        raise InvokerError(f"claude exited {proc.returncode} with no stdout: {detail}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InvokerError(f"claude did not emit JSON: {stdout[:300]}") from exc
    if not isinstance(payload, dict):
        raise InvokerError(f"claude JSON payload is not an object: {stdout[:200]}")
    return payload


def agent_output_class() -> type:
    main_module = sys.modules.get("__main__")
    if getattr(main_module, "Orchestrator", None) is not None:
        candidate = getattr(main_module, "AgentOutput", None)
        if isinstance(candidate, type):
            return candidate
    import orchestrator

    return orchestrator.AgentOutput


def output_from_payload(payload: Mapping[str, object]):
    result = str(payload.get("result", ""))
    if payload.get("is_error"):
        raise InvokerError(f"claude reported a failed run: {result[:300]}")
    usage = payload.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}

    def _count(key: str) -> int:
        try:
            return int(usage.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    return agent_output_class()(
        output=result,
        input_tokens=_count("input_tokens"),
        output_tokens=_count("output_tokens"),
        cached_input_tokens=_count("cache_read_input_tokens"),
    )


def board_dir_for(request, config: InvokerConfig) -> Path:
    declared = str(getattr(request, "board_dir", "") or "").strip()
    return Path(declared).expanduser().resolve() if declared else config.board_dir


def branch_for(ticket_path: Path, repo: Path | None = None, ticket_id: str = "") -> str:
    if repo is not None and ticket_id:
        existing = _rw.existing_ticket_branch(repo, ticket_id)
        if existing:
            return existing
    return ticket_path.stem


CI_UNVERIFIED = "unverified"
CI_GREEN = "green"
CI_RED = "red"


def run_verify(command: str, cwd: Path, timeout: float) -> str:
    if not command:
        return CI_UNVERIFIED
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return CI_RED
    return CI_GREEN if proc.returncode == 0 else CI_RED


def ticket_status_now(ticket_path: Path) -> str:
    try:
        return ticket_fields(ticket_path).get("status", "").strip()
    except OSError:
        return ""


def measured_outcome(result, repo: Path | None, branch: str, ci_status: str, final_status: str = ""):
    merged = bool(repo is not None and _rw.branch_is_merged(repo, branch))
    return replace(
        result, merged_pr=merged, ci_status=ci_status, final_status=final_status
    )


KEPT_OUTCOMES = {
    "kept-dirty": "it holds uncommitted work",
    "kept-failed": "git refused to remove it",
}


def report_teardown(ticket_id: str, path: Path, outcome: str) -> str:
    reason = KEPT_OUTCOMES.get(outcome)
    if reason is not None:
        print(
            f"claude_invoker: worktree kept for {ticket_id} — {reason}: {path}",
            file=sys.stderr,
        )
    return outcome


def acquire_workspace(request, config: InvokerConfig, project_dir: Path | None, branch: str):
    if project_dir is None or not config.worktree_isolation:
        return project_dir, None
    path = _rw.worktree_path(request.run_id, request.ticket_id, config.org_root)
    try:
        return _rw.create_git_worktree(project_dir, path, branch), path
    except (_rw.WorktreeError, OSError, subprocess.SubprocessError) as exc:
        raise InvokerError(isolation_failure(request, project_dir, branch, exc)) from exc


def isolation_failure(request, project_dir: Path, branch: str, exc: Exception) -> str:
    holder = _rw.worktree_holding(project_dir, branch)
    if holder:
        return (
            f"cannot isolate {request.ticket_id}: branch {branch!r} is already checked out at "
            f"{holder}. Free that worktree (git worktree remove) or wait for the run holding it "
            "to finish. Turning isolation off does NOT help here — the branch, not the tree, is "
            "the thing that is taken."
        )
    return (
        f"cannot isolate {request.ticket_id}: {exc}. Set DASLAB_WORKTREE_ISOLATION=0 to "
        "dispatch into the shared tree, accepting that a concurrent role's uncommitted "
        "work can be destroyed by any checkout."
    )


def invoke_with_config(request, config: InvokerConfig):
    ticket_path = find_ticket(board_dir_for(request, config), request.ticket_id)
    require_agent(request.role)
    project_dir = project_dir_for(ticket_path, config.org_root)
    isolate = project_dir is not None and config.worktree_isolation

    if config.dry_run:
        planned = (
            _rw.worktree_path(request.run_id, request.ticket_id, config.org_root)
            if isolate
            else project_dir
        )
        prompt = build_prompt(
            request, ticket_path, planned, config.allowed_tools, isolated=isolate
        )
        return agent_output_class()(
            output=json.dumps(
                {
                    "dry_run": True,
                    "argv": build_command(config, request, prompt, planned),
                    "worktree": str(planned) if isolate else "",
                    "branch": branch_for(ticket_path, project_dir, request.ticket_id) if isolate else "",
                }
            )
        )

    workspace, created = acquire_workspace(
        request, config, project_dir, branch_for(ticket_path, project_dir, request.ticket_id)
    )
    prompt = build_prompt(
        request, ticket_path, workspace, config.allowed_tools, isolated=created is not None
    )
    argv = build_command(config, request, prompt, workspace)
    try:
        result = output_from_payload(run_claude(argv, config))
        ci_status = (
            run_verify(config.verify_command, workspace, config.timeout_seconds)
            if workspace is not None
            else CI_UNVERIFIED
        )
        return measured_outcome(
            result,
            project_dir,
            branch_for(ticket_path, project_dir, request.ticket_id),
            ci_status,
            ticket_status_now(ticket_path),
        )
    finally:
        if created is not None and project_dir is not None:
            report_teardown(
                request.ticket_id,
                created,
                _rw.remove_git_worktree(
                    project_dir, created, _rw.worktree_root(config.org_root)
                ),
            )


def invoke(request):
    return invoke_with_config(request, InvokerConfig.from_env())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude_invoker.py",
        description=(
            "claude_invoker.py — run ONE board ticket through the Claude Code CLI as the role "
            "the ticket is assigned to. This is the 'module:callable' seam orchestrator.py "
            "--dispatch requires: pass --invoker claude_invoker:invoke."
        ),
        epilog=(
            f"exit codes: {EXIT_OK} the agent ran · {EXIT_FAIL} the run failed · "
            f"{EXIT_USAGE} usage error"
        ),
    )
    parser.add_argument("ticket_id", help="ticket id such as DAS-1001")
    parser.add_argument("--role", default="", help="override the ticket's assignee")
    parser.add_argument("--model", default="", help="override the model org.yaml allocates")
    parser.add_argument("--board", type=Path, default=None, help="board/tickets directory")
    parser.add_argument("--goal", default="", help="wave goal handed to the agent")
    parser.add_argument("--run-id", default="manual", help="run id recorded in the prompt")
    parser.add_argument("--permission-mode", default="", help="claude --permission-mode value")
    parser.add_argument(
        "--allowed-tools",
        default=None,
        help="comma-separated claude --allowedTools grant; empty string grants no shell",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the command, run nothing")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    import orchestrator

    try:
        config = InvokerConfig.from_env()
    except InvokerError as exc:
        print(f"claude_invoker: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.board is not None:
        config = replace(config, board_dir=args.board.expanduser().resolve())
    if args.permission_mode:
        config = replace(config, permission_mode=args.permission_mode)
    if args.allowed_tools is not None:
        config = replace(
            config,
            allowed_tools=tuple(t.strip() for t in args.allowed_tools.split(",") if t.strip()),
        )
    if args.dry_run:
        config = replace(config, dry_run=True)

    try:
        ticket_path = find_ticket(config.board_dir, args.ticket_id)
        role, model = resolve_role_and_model(ticket_path, args.role, args.model, config.org_path)
        request = orchestrator.DispatchRequest(
            ticket_id=args.ticket_id,
            role=role,
            model=model,
            zone=ticket_fields(ticket_path).get("zone", ""),
            run_id=args.run_id,
            attempt=1,
            goal=args.goal,
        )
        result = invoke_with_config(request, config)
    except (InvokerError, _wp.UnknownRoleError, FileNotFoundError, OSError) as exc:
        print(f"claude_invoker: {exc}", file=sys.stderr)
        return EXIT_FAIL

    if args.json:
        print(
            json.dumps(
                {
                    "ticket_id": args.ticket_id,
                    "role": role,
                    "model": model,
                    "ticket": str(ticket_path),
                    "output": result.output,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"{args.ticket_id} role={role} model={model} ticket={ticket_path.name}")
        print(result.output)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
