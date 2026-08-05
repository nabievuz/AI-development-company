from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import filelock

_WRITERS = 8
_READ_WRITE_GAP_SECONDS = 0.02


def _unlocked_append_line(path: Path, line: str) -> None:
    current = path.read_text(encoding="utf-8")
    time.sleep(_READ_WRITE_GAP_SECONDS)
    path.write_text(current + line, encoding="utf-8")


def _locked_append_line(path: Path, line: str) -> None:
    def _transform(current: str) -> str:
        time.sleep(_READ_WRITE_GAP_SECONDS)
        return current + line

    filelock.locked_update_text(path, _transform)


def test_unlocked_read_modify_write_loses_updates(tmp_path: Path) -> None:
    target = tmp_path / "ticket.md"
    target.write_text("", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=_WRITERS) as pool:
        list(pool.map(lambda i: _unlocked_append_line(target, f"line-{i}\n"), range(_WRITERS)))

    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) < _WRITERS


def test_locked_read_modify_write_loses_nothing(tmp_path: Path) -> None:
    target = tmp_path / "ticket.md"
    target.write_text("", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=_WRITERS) as pool:
        list(pool.map(lambda i: _locked_append_line(target, f"line-{i}\n"), range(_WRITERS)))

    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln]
    assert sorted(lines) == sorted(f"line-{i}" for i in range(_WRITERS))


def test_locked_append_text_loses_nothing(tmp_path: Path) -> None:
    target = tmp_path / "ledger.jsonl"

    with ThreadPoolExecutor(max_workers=_WRITERS) as pool:
        list(pool.map(lambda i: filelock.locked_append_text(target, f"entry-{i}\n"), range(_WRITERS)))

    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln]
    assert sorted(lines) == sorted(f"entry-{i}" for i in range(_WRITERS))


def test_atomic_write_text_replaces_content_and_leaves_no_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    filelock.atomic_write_text(target, "first")
    filelock.atomic_write_text(target, "second")

    assert target.read_text(encoding="utf-8") == "second"
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_atomic_write_text_preserves_file_mode(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    target.write_text("a", encoding="utf-8")
    target.chmod(0o640)
    filelock.atomic_write_text(target, "b")
    assert target.stat().st_mode & 0o777 == 0o640


def test_failed_transform_leaves_the_original_untouched(tmp_path: Path) -> None:
    target = tmp_path / "ticket.md"
    target.write_text("original", encoding="utf-8")

    def _boom(_current: str) -> str:
        raise RuntimeError("transform failed")

    with pytest.raises(RuntimeError, match="transform failed"):
        filelock.locked_update_text(target, _boom)

    assert target.read_text(encoding="utf-8") == "original"


def test_locked_update_text_on_missing_file_can_refuse(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(FileNotFoundError):
        filelock.locked_update_text(missing, lambda text: text, missing_ok=False)
    assert not missing.exists()


def test_locked_update_text_can_create_a_missing_file(tmp_path: Path) -> None:
    created = tmp_path / "new.md"
    filelock.locked_update_text(created, lambda text: text + "seeded", default="")
    assert created.read_text(encoding="utf-8") == "seeded"


def test_exclusive_lock_is_mutually_exclusive(tmp_path: Path) -> None:
    target = tmp_path / "guarded.md"
    target.write_text("", encoding="utf-8")
    overlaps = 0
    held = False

    def hold(_index: int) -> None:
        nonlocal overlaps, held
        with filelock.exclusive_lock(target):
            if held:
                overlaps += 1
            held = True
            time.sleep(_READ_WRITE_GAP_SECONDS)
            held = False

    with ThreadPoolExecutor(max_workers=_WRITERS) as pool:
        list(pool.map(hold, range(_WRITERS)))

    assert overlaps == 0


def test_exclusive_lock_times_out_instead_of_hanging(tmp_path: Path) -> None:
    target = tmp_path / "held.md"
    target.write_text("", encoding="utf-8")

    with filelock.exclusive_lock(target), ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_acquire_with_timeout, target)
        assert future.result(timeout=5) is True


def _acquire_with_timeout(target: Path) -> bool:
    try:
        with filelock.exclusive_lock(target, timeout=0.05):
            return False
    except filelock.LockTimeout:
        return True


def test_lock_path_is_a_sidecar_not_the_target(tmp_path: Path) -> None:
    target = tmp_path / "ticket.md"
    assert filelock.lock_path_for(target) == tmp_path / "ticket.md.lock"
