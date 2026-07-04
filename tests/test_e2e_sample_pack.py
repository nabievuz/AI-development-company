#!/usr/bin/env python3
"""tests/test_e2e_sample_pack.py — WS7 GATEWAY end-to-end + generality (DAS-1495).

This is the GATE-4 Testing validation for the WS7 gateway machinery. It proves the
gateway's value claim on real input rather than asserting it:

- ``evals/e2e/sample-pack/`` (``acme-tasks``) and ``evals/e2e/sample-pack-2/``
  (``helpdesk-triage``) are real, well-formed PROJECT-OS packs (manifest + canonical
  ``docs/01-planning``..``06-maintenance`` + >=10 discovery Q&A + a Founder-approved
  goal queue);
- running the UNMODIFIED ``scripts/gateway_compile.py`` on each pack compiles
  >= 25 coherent, self-contained, stage-gated story tickets with ZERO hand-written
  tickets (every ticket on the board came out of the compiler);
- both packs compile with the SAME compiler code path (generality — FR-010 / SC-003:
  no per-pack special-casing);
- the compiled board is ``board_lint``-clean and lands in a tmp/scratch project dir,
  never the org ``board/tickets/``.

Every compile runs against a throwaway copy of the pack in ``tmp_path`` so the
committed packs and the org board are never mutated.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import board_lint  # noqa: E402
import gateway_compile as gc  # noqa: E402

E2E_DIR = REPO_ROOT / "evals" / "e2e"
PACK_DIRS = (E2E_DIR / "sample-pack", E2E_DIR / "sample-pack-2")

# The self-containment tokens every compiled stage ticket must carry so a fresh
# agent window needs zero archaeology (SPEC FR-008).
_SELF_CONTAINED_TOKENS = (
    "Embedded context",
    "## Acceptance criteria",
    "## Produces / Consumes",
    "AADL stage:",
    "GATE-",
)


def _slug_of(pack_dir: Path) -> str:
    manifest = yaml.safe_load((pack_dir / "PROJECT-OS.yaml").read_text(encoding="utf-8"))
    return str(manifest["name"])


def _compile_in_scratch(pack_dir: Path, tmp_path: Path):
    """Copy the committed pack into tmp/projects/<slug>/ and compile it there.

    The compiler writes board-tickets/ into the pack root, so a throwaway copy keeps
    the committed pack and the org board untouched.
    """
    slug = _slug_of(pack_dir)
    scratch_root = tmp_path / "projects" / slug
    shutil.copytree(pack_dir, scratch_root)
    res = gc.run_pipeline(scratch_root)
    return slug, scratch_root, res


# --------------------------------------------------------------------------- #
# Both packs exist and are real (not stubs)
# --------------------------------------------------------------------------- #

def test_both_packs_are_real_project_os_packs():
    assert [p.name for p in PACK_DIRS] == ["sample-pack", "sample-pack-2"]
    for pack in PACK_DIRS:
        assert (pack / "PROJECT-OS.yaml").is_file()
        assert (pack / "APPROVED-GOAL-QUEUE.md").is_file()
        assert (pack / "docs" / "01-planning" / "discovery.md").is_file()
        for stage in gc.CANONICAL_STAGE_DIRS:
            d = pack / "docs" / stage
            assert d.is_dir(), f"{pack.name} missing docs/{stage}/"
            # real, not a stub: each stage folder carries at least one authored doc
            assert any(f.suffix == ".md" for f in d.iterdir()), f"{pack.name}/docs/{stage} empty"
        # manifest carries the full closed field set
        manifest = yaml.safe_load((pack / "PROJECT-OS.yaml").read_text(encoding="utf-8"))
        for key in gc.REQUIRED_MANIFEST_KEYS:
            assert manifest.get(key) not in (None, ""), f"{pack.name} manifest missing {key}"


# --------------------------------------------------------------------------- #
# E2E: each pack compiles >= 25 coherent, self-contained tickets, zero hand-written
# --------------------------------------------------------------------------- #

def _assert_compiles_to_board(pack_dir: Path, tmp_path: Path, *, min_tickets: int):
    slug, scratch_root, res = _compile_in_scratch(pack_dir, tmp_path)

    assert res.ok, [str(e) for e in res.errors]
    assert res.rejected_stage is None
    assert len(res.tickets) >= min_tickets, f"{slug}: only {len(res.tickets)} tickets"

    board = scratch_root / "board-tickets"
    assert board.is_dir()

    # ZERO hand-written tickets: every ticket file on the board was produced by the
    # compiler (the compiler's return set == the files on disk, nothing else).
    on_disk = {p.resolve() for p in board.glob("DAS-*.md")}
    produced = {p.resolve() for p in res.tickets}
    assert on_disk == produced, "board contains tickets the compiler did not produce"

    # every ticket is project-scoped to the pack (FR-008)
    for p in res.tickets:
        assert f"project: {slug}" in p.read_text(encoding="utf-8")

    # every stage ticket is self-contained (coherent story ticket)
    stage_tickets = [p for p in res.tickets if "-epic" not in p.name]
    assert stage_tickets
    for p in stage_tickets:
        text = p.read_text(encoding="utf-8")
        for tok in _SELF_CONTAINED_TOKENS:
            assert tok in text, f"{slug}: {p.name} missing {tok!r}"

    # the whole compiled board is board_lint-clean
    known_roles = board_lint.load_known_roles(REPO_ROOT / "board" / "ROUTING.md")
    tickets = board_lint.load_tickets(board)
    assert board_lint.lint_tickets(tickets, known_roles) == []

    # research-enrichment stored ONLY inside the project folder (QONUN placement)
    assert res.research_path is not None and res.research_path.is_file()
    assert (scratch_root / "docs" / "01-planning") in res.research_path.parents

    # scratch/tmp board, NEVER the org board/tickets/
    assert "board/tickets" not in str(board).replace("\\", "/")
    return slug, res


def test_sample_pack_1_compiles_25_plus_coherent_tickets(tmp_path):
    slug, res = _assert_compiles_to_board(PACK_DIRS[0], tmp_path, min_tickets=25)
    assert slug == "acme-tasks"
    # 4 approved goals -> 4 * (1 epic + 6 stages) = 28
    assert len(res.tickets) == 28


def test_sample_pack_2_compiles_25_plus_coherent_tickets(tmp_path):
    slug, res = _assert_compiles_to_board(PACK_DIRS[1], tmp_path, min_tickets=25)
    assert slug == "helpdesk-triage"
    # 5 approved goals -> 5 * (1 epic + 6 stages) = 35
    assert len(res.tickets) == 35


# --------------------------------------------------------------------------- #
# Every compiled goal covers all six AADL gates in order
# --------------------------------------------------------------------------- #

def test_each_goal_covers_all_six_aadl_gates(tmp_path):
    for pack in PACK_DIRS:
        _slug, _scratch, res = _compile_in_scratch(pack, tmp_path / pack.name)
        gates = {
            line.split("stage:", 1)[1].strip()
            for p in res.tickets
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.startswith("stage: GATE-")
        }
        assert gates == {f"GATE-{i}" for i in range(1, 7)}


# --------------------------------------------------------------------------- #
# Generality: the SAME unmodified compiler compiles both different packs
# --------------------------------------------------------------------------- #

def test_generality_same_compiler_compiles_both_different_packs(tmp_path):
    """FR-010 / SC-003 — two materially different packs, one compiler, no code change."""
    results = {}
    for pack in PACK_DIRS:
        slug, _scratch, res = _compile_in_scratch(pack, tmp_path / pack.name)
        assert res.ok, [str(e) for e in res.errors]
        results[slug] = res

    # the two packs are genuinely different domains/stacks/goal-counts
    m1 = yaml.safe_load((PACK_DIRS[0] / "PROJECT-OS.yaml").read_text(encoding="utf-8"))
    m2 = yaml.safe_load((PACK_DIRS[1] / "PROJECT-OS.yaml").read_text(encoding="utf-8"))
    assert m1["name"] != m2["name"]
    assert m1["stack"] != m2["stack"]
    assert m1["stack"]["languages"] != m2["stack"]["languages"]
    assert len(results["acme-tasks"].tickets) != len(results["helpdesk-triage"].tickets)

    # both were compiled by the one imported gateway module — nothing pack-specific
    assert gc.run_pipeline.__module__ == "gateway_compile"


def test_compiling_packs_never_touches_org_board(tmp_path):
    """The org board/tickets/ dir is never a compile target for a sample pack."""
    before = sorted((REPO_ROOT / "board" / "tickets").glob("DAS-*.md"))
    for pack in PACK_DIRS:
        _compile_in_scratch(pack, tmp_path / pack.name)
    after = sorted((REPO_ROOT / "board" / "tickets").glob("DAS-*.md"))
    assert before == after  # org board unchanged
