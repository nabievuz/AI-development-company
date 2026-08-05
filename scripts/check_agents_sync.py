#!/usr/bin/env python3


from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT


VALID_MODELS: frozenset[str] = frozenset({"opus", "sonnet", "haiku"})


SKIP_KEYS: frozenset[str] = frozenset()

_REPO_ROOT = ROOT


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    data: dict[str, str] = {}
    for key, value in _KV_RE.findall(m.group(1)):
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        data[key] = value
    return data


def load_shims(agents_dir: Path) -> dict[str, dict[str, str]]:
    shims: dict[str, dict[str, str]] = {}
    for path in sorted(agents_dir.glob("*.md")):
        key = path.stem
        if key in SKIP_KEYS:
            continue
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        shims[key] = fm
    return shims


_ROUTING_ROW_RE = re.compile(
    r"^\|\s*`([a-z0-9-]+)`\s*\|[^\n]*\|\s*([^\n|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def load_routing(routing_path: Path) -> dict[str, str]:
    text = routing_path.read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in _ROUTING_ROW_RE.finditer(text)}


_MODEL_ROW_RE = re.compile(
    r"^\|\s*`?([a-z0-9-]+)`?\s*\|\s*(opus|sonnet|haiku)\s*\|",
    re.MULTILINE,
)


def load_policy_models(policy_path: Path) -> dict[str, str] | None:
    if not policy_path.exists():
        return None
    text = policy_path.read_text(encoding="utf-8")
    return dict(_MODEL_ROW_RE.findall(text))


def check_sync(
    shims: dict[str, dict[str, str]],
    routing: dict[str, str],
    policy_models: dict[str, str] | None,
) -> list[str]:
    errors: list[str] = []

    shim_keys = set(shims.keys())
    routing_keys = set(routing.keys())


    for key in sorted(routing_keys - shim_keys):
        errors.append(
            f"{key}: present in ROUTING.md but no .claude/agents/{key}.md shim found"
        )


    for key in sorted(shim_keys - routing_keys):
        errors.append(
            f"{key}: shim .claude/agents/{key}.md exists but key missing from ROUTING.md"
        )


    for key, fm in sorted(shims.items()):

        shim_name = fm.get("name", "").strip()
        if shim_name and shim_name != key:
            errors.append(
                f"{key}: shim 'name:' field is '{shim_name}' but filename stem is '{key}'"
            )
        if not shim_name:
            errors.append(f"{key}: shim is missing 'name:' frontmatter field")


        shim_model = fm.get("model", "").strip()
        if not shim_model:
            errors.append(f"{key}: shim is missing 'model:' frontmatter field")
        elif shim_model not in VALID_MODELS:
            errors.append(
                f"{key}: shim model '{shim_model}' is not a valid tier "
                f"(must be one of {sorted(VALID_MODELS)})"
            )


        if policy_models is not None and shim_model in VALID_MODELS:
            expected = policy_models.get(key)
            if expected is None:
                errors.append(
                    f"{key}: no row found in model-allocation policy for this role"
                )
            elif shim_model != expected:
                errors.append(
                    f"{key}: shim model '{shim_model}' differs from policy "
                    f"'{expected}' — re-run scripts/gen_subagents.py"
                )

    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_agents_sync",
        description="check_agents_sync.py — detect drift between .claude/agents/* shims,\nboard/ROUTING.md, and the model-allocation policy.\n\nCompares three artefacts that ``scripts/gen_subagents.py`` keeps in sync:\n\n1. ``.claude/agents/<key>.md`` — Claude Code subagent shim files.\n2. ``board/ROUTING.md`` — role-to-reviewer routing table (generated header\n   marks it as authoritative).\n3. ``governance/policies/model-allocation.md`` — model assignment table\n   (board-level policy; may not be present in sparse worktrees).\n\nPolicy-file tolerance\n---------------------\n``governance/policies/model-allocation.md`` is folded post-checkpoint and\nis NOT present in this worktree yet.  When the file is absent the script\nprints ``policy not yet in-tree`` and exits 0 — the model-consistency check\nis skipped.  The shim ↔ ROUTING.md cross-check always runs regardless.\n\nDrift detected (exits 1)\n------------------------\n* A role key appears in ROUTING.md but has no matching shim file.\n* A shim file exists but its key is absent from ROUTING.md (unless the\n  key is in the known SKIP set of external-runtime pilots).\n* A shim file's ``name:`` frontmatter field does not match its filename stem.\n* A shim file's ``model:`` field is not one of the three valid tiers\n  (opus / sonnet / haiku).\n* When the policy file IS present: a shim model does not match the\n  policy-table row for that role key.\n\nUsage::\n\n    python3 scripts/check_agents_sync.py [options]\n\n    --agents   PATH  Path to .claude/agents/ directory (default: auto-detected).\n    --routing  PATH  Path to board/ROUTING.md (default: auto-detected).\n    --policy   PATH  Path to governance/policies/model-allocation.md\n                     (default: auto-detected; absence is tolerated — exit 0).\n    --strict         Treat a missing policy file as an error (exit 1).\n\nExit codes: 0 = in sync (or policy absent without --strict), 1 = drift found,\n2 = usage / IO error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--agents",
        type=Path,
        default=_REPO_ROOT / ".claude" / "agents",
        help="Path to .claude/agents/ directory (default: repo-root auto-detected)",
    )
    p.add_argument(
        "--routing",
        type=Path,
        default=_REPO_ROOT / "board" / "ROUTING.md",
        help="Path to board/ROUTING.md (default: repo-root auto-detected)",
    )
    p.add_argument(
        "--policy",
        type=Path,
        default=_REPO_ROOT / "governance" / "policies" / "model-allocation.md",
        help=(
            "Path to governance/policies/model-allocation.md "
            "(default: repo-root auto-detected; absence is tolerated)"
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat a missing policy file as an error (default: tolerated, exit 0)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    agents_dir: Path = args.agents
    routing_path: Path = args.routing
    policy_path: Path = args.policy


    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        return 2
    if not routing_path.is_file():
        print(f"ERROR: ROUTING.md not found: {routing_path}", file=sys.stderr)
        return 2


    try:
        shims = load_shims(agents_dir)
    except OSError as exc:
        print(f"ERROR reading agents directory: {exc}", file=sys.stderr)
        return 2

    try:
        routing = load_routing(routing_path)
    except OSError as exc:
        print(f"ERROR reading ROUTING.md: {exc}", file=sys.stderr)
        return 2

    policy_models: dict[str, str] | None = None
    if not policy_path.exists():
        if args.strict:
            print(
                f"ERROR: policy file not found: {policy_path} "
                "(pass --strict; use without --strict to tolerate absence)",
                file=sys.stderr,
            )
            return 2
        print(
            f"check_agents_sync: policy not yet in-tree "
            f"({policy_path.name} absent) — model-consistency check skipped."
        )
    else:
        try:
            policy_models = load_policy_models(policy_path)
        except OSError as exc:
            print(f"ERROR reading policy file: {exc}", file=sys.stderr)
            return 2


    errors = check_sync(shims, routing, policy_models)

    if errors:
        print(
            f"check_agents_sync: {len(errors)} drift violation(s) found:\n",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  FAIL  {e}", file=sys.stderr)
        return 1

    role_count = len(shims)
    policy_note = "" if policy_models is None else f" (policy: {len(policy_models)} rows)"
    print(
        f"check_agents_sync: OK — {role_count} shim(s) in sync with ROUTING.md{policy_note}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
