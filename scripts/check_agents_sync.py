#!/usr/bin/env python3
"""check_agents_sync.py — detect drift between .claude/agents/* shims,
board/ROUTING.md, and the model-allocation policy.

Compares three artefacts that ``scripts/gen_subagents.py`` keeps in sync:

1. ``.claude/agents/<key>.md`` — Claude Code subagent shim files.
2. ``board/ROUTING.md`` — role-to-reviewer routing table (generated header
   marks it as authoritative).
3. ``governance/policies/model-allocation.md`` — model assignment table
   (board-level policy; may not be present in sparse worktrees).

Policy-file tolerance
---------------------
``governance/policies/model-allocation.md`` is folded post-checkpoint and
is NOT present in this worktree yet.  When the file is absent the script
prints ``policy not yet in-tree`` and exits 0 — the model-consistency check
is skipped.  The shim ↔ ROUTING.md cross-check always runs regardless.

Drift detected (exits 1)
------------------------
* A role key appears in ROUTING.md but has no matching shim file.
* A shim file exists but its key is absent from ROUTING.md (unless the
  key is in the known SKIP set of external-runtime pilots).
* A shim file's ``name:`` frontmatter field does not match its filename stem.
* A shim file's ``model:`` field is not one of the three valid tiers
  (opus / sonnet / haiku).
* When the policy file IS present: a shim model does not match the
  policy-table row for that role key.

Usage::

    python3 scripts/check_agents_sync.py [options]

    --agents   PATH  Path to .claude/agents/ directory (default: auto-detected).
    --routing  PATH  Path to board/ROUTING.md (default: auto-detected).
    --policy   PATH  Path to governance/policies/model-allocation.md
                     (default: auto-detected; absence is tolerated — exit 0).
    --strict         Treat a missing policy file as an error (exit 1).

Exit codes: 0 = in sync (or policy absent without --strict), 1 = drift found,
2 = usage / IO error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _paths import ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODELS: frozenset[str] = frozenset({"opus", "sonnet", "haiku"})

# Role keys for external-runtime pilots that gen_subagents.py skips.
SKIP_KEYS: frozenset[str] = frozenset()

_REPO_ROOT = ROOT

# ---------------------------------------------------------------------------
# Frontmatter parser (shim files)
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):[^\S\n]*(.*?)[^\S\n]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return key->value dict from YAML frontmatter, or empty dict if absent."""
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


# ---------------------------------------------------------------------------
# Shim loader
# ---------------------------------------------------------------------------

def load_shims(agents_dir: Path) -> dict[str, dict[str, str]]:
    """Return ``{role_key: frontmatter}`` for every .md in *agents_dir*.

    Keys in ``SKIP_KEYS`` are excluded.
    """
    shims: dict[str, dict[str, str]] = {}
    for path in sorted(agents_dir.glob("*.md")):
        key = path.stem
        if key in SKIP_KEYS:
            continue
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        shims[key] = fm
    return shims


# ---------------------------------------------------------------------------
# ROUTING.md parser
# ---------------------------------------------------------------------------

_ROUTING_ROW_RE = re.compile(
    r"^\|\s*`([a-z0-9-]+)`\s*\|[^\n]*\|\s*([^\n|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def load_routing(routing_path: Path) -> dict[str, str]:
    """Return ``{role_key: reports_to}`` parsed from ROUTING.md.

    Matches rows whose first cell is a backtick-quoted role key and captures
    the last pipe-separated cell as the "reports_to" value.  The header row
    and divider row are skipped because their first cell either is unquoted or
    starts with ``---``.
    """
    text = routing_path.read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in _ROUTING_ROW_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Model-allocation policy parser
# ---------------------------------------------------------------------------

_MODEL_ROW_RE = re.compile(
    r"^\|\s*`?([a-z0-9-]+)`?\s*\|\s*(opus|sonnet|haiku)\s*\|",
    re.MULTILINE,
)


def load_policy_models(policy_path: Path) -> dict[str, str] | None:
    """Return ``{role_key: model}`` from the policy file, or None if absent."""
    if not policy_path.exists():
        return None
    text = policy_path.read_text(encoding="utf-8")
    return dict(_MODEL_ROW_RE.findall(text))


# ---------------------------------------------------------------------------
# Drift checks
# ---------------------------------------------------------------------------

def check_sync(
    shims: dict[str, dict[str, str]],
    routing: dict[str, str],
    policy_models: dict[str, str] | None,
) -> list[str]:
    """Run all drift checks and return a list of human-readable violation strings."""
    errors: list[str] = []

    shim_keys = set(shims.keys())
    routing_keys = set(routing.keys())

    # --- Cross-check: shims vs ROUTING.md ----------------------------------

    # Role in ROUTING.md but no shim file
    for key in sorted(routing_keys - shim_keys):
        errors.append(
            f"{key}: present in ROUTING.md but no .claude/agents/{key}.md shim found"
        )

    # Shim exists but not in ROUTING.md
    for key in sorted(shim_keys - routing_keys):
        errors.append(
            f"{key}: shim .claude/agents/{key}.md exists but key missing from ROUTING.md"
        )

    # --- Per-shim field validation -----------------------------------------

    for key, fm in sorted(shims.items()):
        # name field must match filename stem
        shim_name = fm.get("name", "").strip()
        if shim_name and shim_name != key:
            errors.append(
                f"{key}: shim 'name:' field is '{shim_name}' but filename stem is '{key}'"
            )
        if not shim_name:
            errors.append(f"{key}: shim is missing 'name:' frontmatter field")

        # model field must be a valid tier
        shim_model = fm.get("model", "").strip()
        if not shim_model:
            errors.append(f"{key}: shim is missing 'model:' frontmatter field")
        elif shim_model not in VALID_MODELS:
            errors.append(
                f"{key}: shim model '{shim_model}' is not a valid tier "
                f"(must be one of {sorted(VALID_MODELS)})"
            )

        # model must match policy table (when policy is present)
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_agents_sync",
        description=__doc__,
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


def main(argv: list[str] | None = None) -> int:  # noqa: UP007
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    agents_dir: Path = args.agents
    routing_path: Path = args.routing
    policy_path: Path = args.policy

    # --- Input validation ---------------------------------------------------

    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        return 2
    if not routing_path.is_file():
        print(f"ERROR: ROUTING.md not found: {routing_path}", file=sys.stderr)
        return 2

    # --- Load data ----------------------------------------------------------

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

    # --- Run drift checks ---------------------------------------------------

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
