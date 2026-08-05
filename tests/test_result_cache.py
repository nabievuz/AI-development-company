from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cache.result_cache import (
    ResultCache,
    _cache_key,
)


PROMPT = "Validate ticket DAS-9999 for routing."
DIGESTS = ["abc123", "def456"]
RESULT = {"status": "pass", "confidence": 0.97, "notes": "all checks green"}


@pytest.fixture()
def cache(tmp_path: Path) -> ResultCache:
    return ResultCache(cache_dir=tmp_path / "cache")


def test_get_returns_none_before_put(cache: ResultCache) -> None:
    assert cache.get(PROMPT, DIGESTS) is None


def test_put_then_get_returns_result(cache: ResultCache) -> None:
    cache.put(PROMPT, DIGESTS, RESULT)
    result = cache.get(PROMPT, DIGESTS)
    assert result == RESULT


def test_put_then_get_preserves_nested_structure(cache: ResultCache) -> None:
    nested = {"a": [1, 2, {"b": True}], "c": None}
    cache.put(PROMPT, DIGESTS, nested)
    assert cache.get(PROMPT, DIGESTS) == nested


def test_expired_entry_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=60)

    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    old_time = (datetime.now(tz=UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["written_at"] = old_time
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) is None


def test_entry_just_within_ttl_is_a_hit(cache: ResultCache, tmp_path: Path) -> None:
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=60)
    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    recent_time = (datetime.now(tz=UTC) - timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["written_at"] = recent_time
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) == RESULT


def test_unparseable_written_at_is_treated_as_expired(cache: ResultCache, tmp_path: Path) -> None:
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=86400)
    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    data["written_at"] = "not-a-timestamp"
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) is None


def test_different_prompt_is_a_miss(cache: ResultCache) -> None:
    cache.put(PROMPT, DIGESTS, RESULT)
    assert cache.get("A different prompt entirely.", DIGESTS) is None


def test_different_digests_is_a_miss(cache: ResultCache) -> None:
    cache.put(PROMPT, DIGESTS, RESULT)
    assert cache.get(PROMPT, ["xyz999"]) is None


def test_corrupt_json_file_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text("not-valid-json{{{{", encoding="utf-8")
    assert cache.get(PROMPT, DIGESTS) is None


def test_missing_result_field_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    bad = {"key": key, "written_at": "2026-07-03T00:00:00Z", "ttl_seconds": 86400}
    (cache_dir / f"{key}.json").write_text(json.dumps(bad), encoding="utf-8")
    assert cache.get(PROMPT, DIGESTS) is None


def test_hit_with_ticket_id_logs_event(cache: ResultCache) -> None:
    mock_store = MagicMock()
    cache._event_store = mock_store

    cache.put(PROMPT, DIGESTS, RESULT)
    result = cache.get(PROMPT, DIGESTS, ticket_id="DAS-1450")

    assert result == RESULT
    assert mock_store.append.call_count == 1
    ev = mock_store.append.call_args[0][0]
    assert ev["event_type"] == "cache_hit"
    assert ev["cached"] is True
    assert ev["ticket_id"] == "DAS-1450"
    assert ev["cache_key"] == _cache_key(PROMPT, DIGESTS)


def test_hit_with_run_id_is_forwarded_to_event(cache: ResultCache) -> None:
    mock_store = MagicMock()
    cache._event_store = mock_store

    cache.put(PROMPT, DIGESTS, RESULT)
    cache.get(PROMPT, DIGESTS, ticket_id="DAS-1450", run_id="run-abc")

    ev = mock_store.append.call_args[0][0]
    assert ev.get("run_id") == "run-abc"


def test_hit_without_ticket_id_does_not_log(cache: ResultCache) -> None:
    mock_store = MagicMock()
    cache._event_store = mock_store

    cache.put(PROMPT, DIGESTS, RESULT)
    result = cache.get(PROMPT, DIGESTS)

    assert result == RESULT
    mock_store.append.assert_not_called()


def test_miss_never_logs_event(cache: ResultCache) -> None:
    mock_store = MagicMock()
    cache._event_store = mock_store

    result = cache.get(PROMPT, DIGESTS, ticket_id="DAS-1450")

    assert result is None
    mock_store.append.assert_not_called()


def test_cache_dir_created_on_first_put(tmp_path: Path) -> None:
    new_dir = tmp_path / "deep" / "new" / "cache"
    assert not new_dir.exists()
    cache = ResultCache(cache_dir=new_dir)
    cache.put(PROMPT, DIGESTS, RESULT)
    assert new_dir.is_dir()
    key = _cache_key(PROMPT, DIGESTS)
    assert (new_dir / f"{key}.json").exists()


def test_entry_schema_has_required_fields(cache: ResultCache, tmp_path: Path) -> None:
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=3600)
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    entry_path = cache_dir / f"{key}.json"
    data = json.loads(entry_path.read_text())
    assert data["key"] == key
    assert data["result"] == RESULT
    assert "written_at" in data
    assert data["ttl_seconds"] == 3600


def test_key_is_deterministic(cache: ResultCache) -> None:
    k1 = cache.key(PROMPT, DIGESTS)
    k2 = cache.key(PROMPT, DIGESTS)
    assert k1 == k2
    assert len(k1) == 64


def test_key_is_order_independent_on_digests(cache: ResultCache) -> None:
    k1 = cache.key(PROMPT, ["abc", "def"])
    k2 = cache.key(PROMPT, ["def", "abc"])
    assert k1 == k2


def test_key_differs_on_prompt_change(cache: ResultCache) -> None:
    k1 = cache.key(PROMPT, DIGESTS)
    k2 = cache.key("Other prompt.", DIGESTS)
    assert k1 != k2


def test_key_differs_on_digest_change(cache: ResultCache) -> None:
    k1 = cache.key(PROMPT, ["abc"])
    k2 = cache.key(PROMPT, ["xyz"])
    assert k1 != k2
