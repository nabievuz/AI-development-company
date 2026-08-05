from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_cache_prefix import (
    _DEFAULT_TOKENS_PER_CHAR,
    _MIN_TOKENS,
    _STABLE_PREFIX_END_MARKER,
    approx_tokens,
    check_volatile,
    extract_stable_prefix,
    run_checks,
    sha256_of,
)


_SENTINEL = _STABLE_PREFIX_END_MARKER


_LONG_CLEAN_PREFIX = "# DasLab dispatch preamble\n\n" + ("x" * 16500)


def _make_skill(tmp_path: Path, prefix_body: str, version: str = "") -> Path:
    skill = tmp_path / "SKILL.md"
    version_line = f"\nCACHE_PREFIX_VERSION: {version}\n" if version else ""
    skill.write_text(
        f"{prefix_body}\n{version_line}\n{_SENTINEL}\n\n"
        "# ADR 0006 docs (after the sentinel — not subject to byte-stability).\n",
        encoding="utf-8",
    )
    return skill


def _make_baseline(tmp_path: Path, prefix_hash: str, version: str = "") -> Path:
    baseline = tmp_path / ".cache_prefix_baseline"
    data: dict[str, str] = {
        "stable_prefix_sha256": prefix_hash,
        "cache_prefix_version": version,
        "note": "test fixture",
    }
    baseline.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return baseline


def test_extract_stable_prefix_with_sentinel() -> None:
    body = "preamble content"
    text = f"{body}\n{_SENTINEL}\nADR docs here"
    result = extract_stable_prefix(text)
    assert result == f"{body}\n"
    assert _SENTINEL not in result
    assert "ADR docs here" not in result


def test_extract_stable_prefix_without_sentinel() -> None:
    text = "no sentinel here at all"
    assert extract_stable_prefix(text) == text


def test_sha256_of_is_deterministic() -> None:
    text = "hello world"
    assert sha256_of(text) == sha256_of(text)
    assert sha256_of(text) != sha256_of(text + "!")


def test_approx_tokens() -> None:
    assert approx_tokens("a" * 4000, 0.25) == 1000
    assert approx_tokens("a" * 4096, 0.25) == 1024


def test_clean_prefix_passes(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v1")
    prefix = extract_stable_prefix(skill.read_text(encoding="utf-8"))
    baseline = _make_baseline(tmp_path, sha256_of(prefix), version="v1")
    assert run_checks(skill, baseline) == 0


def test_volatile_iso_timestamp(tmp_path: Path) -> None:
    body = _LONG_CLEAN_PREFIX + "\nRun at 2026-06-19T14:30:00 — volatile!\n"
    violations = check_volatile(body)
    assert any("ISO timestamp" in v for v in violations)


def test_volatile_uuid(tmp_path: Path) -> None:
    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    body = _LONG_CLEAN_PREFIX + f"\nrun-id={uuid_str}\n"
    violations = check_volatile(body)
    assert any("UUID" in v for v in violations)


def test_volatile_ticket_id(tmp_path: Path) -> None:
    body = _LONG_CLEAN_PREFIX + "\nWorking on DAS-1371 — volatile!\n"
    violations = check_volatile(body)
    assert any("ticket-id" in v for v in violations)


def test_volatile_wave_counter(tmp_path: Path) -> None:
    body = _LONG_CLEAN_PREFIX + "\nThis is wave-3 of the run.\n"
    violations = check_volatile(body)
    assert any("wave-counter" in v for v in violations)


def test_multiple_volatile_tokens_all_reported(tmp_path: Path) -> None:
    body = (
        _LONG_CLEAN_PREFIX
        + "\nRun at 2026-06-19T14:30:00 for DAS-9999 wave-1\n"
    )
    violations = check_volatile(body)
    labels = " ".join(violations)
    assert "ISO timestamp" in labels
    assert "ticket-id" in labels
    assert "wave-counter" in labels


def test_volatile_detection_exits_1_via_run_checks(tmp_path: Path) -> None:
    body = _LONG_CLEAN_PREFIX + "\n2026-06-19T00:00:00 timestamp in prefix\n"
    skill = _make_skill(tmp_path, body, version="v1")
    prefix = extract_stable_prefix(skill.read_text(encoding="utf-8"))
    baseline = _make_baseline(tmp_path, sha256_of(prefix), version="v1")
    assert run_checks(skill, baseline) == 1


def test_hash_drift_without_version_bump_exits_1(tmp_path: Path) -> None:

    old_hash = sha256_of("old prefix content\n")
    baseline = _make_baseline(tmp_path, old_hash, version="v1")

    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v1")
    assert run_checks(skill, baseline) == 1


def test_hash_drift_with_version_bump_exits_0(tmp_path: Path) -> None:
    old_hash = sha256_of("old prefix content\n")
    baseline = _make_baseline(tmp_path, old_hash, version="v1")

    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v2")
    assert run_checks(skill, baseline) == 0


def test_no_stored_hash_bootstraps_and_exits_0(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v1")

    baseline = tmp_path / "sub" / ".baseline"
    assert run_checks(skill, baseline) == 0
    assert baseline.exists(), "baseline file should have been created on first run"
    data = json.loads(baseline.read_text())
    assert "stable_prefix_sha256" in data


def test_min_length_check_short_prefix_exits_1(tmp_path: Path) -> None:

    short_body = "# Short preamble\n" + ("x" * 100)
    skill = _make_skill(tmp_path, short_body, version="v1")
    prefix = extract_stable_prefix(skill.read_text(encoding="utf-8"))
    baseline = _make_baseline(tmp_path, sha256_of(prefix), version="v1")
    assert run_checks(skill, baseline) == 1


def test_min_length_check_exact_boundary_passes(tmp_path: Path) -> None:

    boundary_body = "# Preamble\n" + ("x" * (16384 - len("# Preamble\n")))

    assert approx_tokens(boundary_body, _DEFAULT_TOKENS_PER_CHAR) >= _MIN_TOKENS
    skill = _make_skill(tmp_path, boundary_body, version="v1")
    prefix = extract_stable_prefix(skill.read_text(encoding="utf-8"))
    baseline = _make_baseline(tmp_path, sha256_of(prefix), version="v1")
    assert run_checks(skill, baseline) == 0


def test_fix_writes_new_baseline_and_exits_0(tmp_path: Path) -> None:
    old_hash = sha256_of("old content\n")
    baseline = _make_baseline(tmp_path, old_hash, version="v1")

    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v2")
    assert run_checks(skill, baseline, fix=True) == 0
    data = json.loads(baseline.read_text())

    prefix = extract_stable_prefix(skill.read_text(encoding="utf-8"))
    assert data["stable_prefix_sha256"] == sha256_of(prefix)
    assert data["cache_prefix_version"] == "v2"


def test_fix_on_missing_baseline_creates_it(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path, _LONG_CLEAN_PREFIX, version="v1")
    baseline = tmp_path / "new_baseline.json"
    assert not baseline.exists()
    assert run_checks(skill, baseline, fix=True) == 0
    assert baseline.exists()
    data = json.loads(baseline.read_text())
    assert "stable_prefix_sha256" in data


def test_live_skill_passes_all_checks() -> None:
    skill = _REPO_ROOT / ".claude" / "skills" / "daslab-cycle" / "SKILL.md"
    baseline = _REPO_ROOT / "scripts" / ".cache_prefix_baseline"
    assert skill.is_file(), f"skill not found: {skill}"
    assert baseline.is_file(), f"baseline not found: {baseline}"
    assert run_checks(skill, baseline) == 0
