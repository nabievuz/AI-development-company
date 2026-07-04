"""tests/test_result_cache.py — pytest suite for scripts/cache/result_cache.py.

Coverage (ORGANISM P6 / DAS-1450 acceptance criteria):

    1. Cache write → hit (non-expired entry is returned).
    2. TTL expiry → miss (expired entry treated as absent).
    3. Different key → miss (prompt/digest change yields a new key).
    4. Corrupt/missing file → miss (graceful degradation).
    5. Event store receives a ``cache_hit`` event on a hit with a ticket_id.
    6. No event is logged when ticket_id is None.
    7. cache_dir is created on first write.
    8. put → get round-trip preserves the result dict intact.
    9. key() helper is deterministic and order-independent on input_digests.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable (scripts/cache/ is a sub-package).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cache.result_cache import (  # noqa: E402
    ResultCache,
    _cache_key,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROMPT = "Validate ticket DAS-9999 for routing."
DIGESTS = ["abc123", "def456"]
RESULT = {"status": "pass", "confidence": 0.97, "notes": "all checks green"}


@pytest.fixture()
def cache(tmp_path: Path) -> ResultCache:
    """A ResultCache backed by a temp directory (never touches board/.cache)."""
    return ResultCache(cache_dir=tmp_path / "cache")


# ---------------------------------------------------------------------------
# 1. Cache write → hit
# ---------------------------------------------------------------------------


def test_get_returns_none_before_put(cache: ResultCache) -> None:
    """get() returns None when no entry has been written yet."""
    assert cache.get(PROMPT, DIGESTS) is None


def test_put_then_get_returns_result(cache: ResultCache) -> None:
    """put() followed by get() returns the stored result dict."""
    cache.put(PROMPT, DIGESTS, RESULT)
    result = cache.get(PROMPT, DIGESTS)
    assert result == RESULT


def test_put_then_get_preserves_nested_structure(cache: ResultCache) -> None:
    """get() returns the exact dict that was put, including nested structures."""
    nested = {"a": [1, 2, {"b": True}], "c": None}
    cache.put(PROMPT, DIGESTS, nested)
    assert cache.get(PROMPT, DIGESTS) == nested


# ---------------------------------------------------------------------------
# 2. TTL expiry → miss
# ---------------------------------------------------------------------------


def test_expired_entry_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    """An entry whose written_at is older than ttl_seconds is treated as a miss."""
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=60)
    # Rewrite the entry's written_at to be 2 hours in the past.
    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    old_time = (datetime.now(tz=UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["written_at"] = old_time
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) is None


def test_entry_just_within_ttl_is_a_hit(cache: ResultCache, tmp_path: Path) -> None:
    """An entry written 50 s ago with ttl=60 s is still a valid hit."""
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=60)
    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    recent_time = (datetime.now(tz=UTC) - timedelta(seconds=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["written_at"] = recent_time
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) == RESULT


def test_unparseable_written_at_is_treated_as_expired(cache: ResultCache, tmp_path: Path) -> None:
    """An entry with a corrupt written_at is treated as expired (safe default)."""
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=86400)
    key = _cache_key(PROMPT, DIGESTS)
    entry_path = (tmp_path / "cache") / f"{key}.json"
    data = json.loads(entry_path.read_text())
    data["written_at"] = "not-a-timestamp"
    entry_path.write_text(json.dumps(data, indent=2) + "\n")

    assert cache.get(PROMPT, DIGESTS) is None


# ---------------------------------------------------------------------------
# 3. Different key → miss
# ---------------------------------------------------------------------------


def test_different_prompt_is_a_miss(cache: ResultCache) -> None:
    """A different prompt yields a different key — original entry is not returned."""
    cache.put(PROMPT, DIGESTS, RESULT)
    assert cache.get("A different prompt entirely.", DIGESTS) is None


def test_different_digests_is_a_miss(cache: ResultCache) -> None:
    """Different input digests yield a different key."""
    cache.put(PROMPT, DIGESTS, RESULT)
    assert cache.get(PROMPT, ["xyz999"]) is None


# ---------------------------------------------------------------------------
# 4. Corrupt/missing file → miss
# ---------------------------------------------------------------------------


def test_corrupt_json_file_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    """A JSON-corrupt cache file is silently treated as a miss."""
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text("not-valid-json{{{{", encoding="utf-8")
    assert cache.get(PROMPT, DIGESTS) is None


def test_missing_result_field_is_a_miss(cache: ResultCache, tmp_path: Path) -> None:
    """A cache entry without a 'result' field is treated as a miss."""
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    bad = {"key": key, "written_at": "2026-07-03T00:00:00Z", "ttl_seconds": 86400}
    (cache_dir / f"{key}.json").write_text(json.dumps(bad), encoding="utf-8")
    assert cache.get(PROMPT, DIGESTS) is None


# ---------------------------------------------------------------------------
# 5. Event store receives cache_hit event on a hit with ticket_id
# ---------------------------------------------------------------------------


def test_hit_with_ticket_id_logs_event(cache: ResultCache) -> None:
    """A cache hit with a ticket_id appends a cache_hit event to the event store."""
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
    """run_id is forwarded to the cache_hit event when provided."""
    mock_store = MagicMock()
    cache._event_store = mock_store

    cache.put(PROMPT, DIGESTS, RESULT)
    cache.get(PROMPT, DIGESTS, ticket_id="DAS-1450", run_id="run-abc")

    ev = mock_store.append.call_args[0][0]
    assert ev.get("run_id") == "run-abc"


# ---------------------------------------------------------------------------
# 6. No event logged when ticket_id is None
# ---------------------------------------------------------------------------


def test_hit_without_ticket_id_does_not_log(cache: ResultCache) -> None:
    """A cache hit without a ticket_id does not log any event."""
    mock_store = MagicMock()
    cache._event_store = mock_store

    cache.put(PROMPT, DIGESTS, RESULT)
    result = cache.get(PROMPT, DIGESTS)  # ticket_id omitted

    assert result == RESULT
    mock_store.append.assert_not_called()


def test_miss_never_logs_event(cache: ResultCache) -> None:
    """A cache miss never logs an event regardless of ticket_id."""
    mock_store = MagicMock()
    cache._event_store = mock_store

    result = cache.get(PROMPT, DIGESTS, ticket_id="DAS-1450")

    assert result is None
    mock_store.append.assert_not_called()


# ---------------------------------------------------------------------------
# 7. cache_dir is created on first write
# ---------------------------------------------------------------------------


def test_cache_dir_created_on_first_put(tmp_path: Path) -> None:
    """put() creates board/.cache/ (or any cache_dir) on first use."""
    new_dir = tmp_path / "deep" / "new" / "cache"
    assert not new_dir.exists()
    cache = ResultCache(cache_dir=new_dir)
    cache.put(PROMPT, DIGESTS, RESULT)
    assert new_dir.is_dir()
    key = _cache_key(PROMPT, DIGESTS)
    assert (new_dir / f"{key}.json").exists()


# ---------------------------------------------------------------------------
# 8. put → get round-trip: entry schema
# ---------------------------------------------------------------------------


def test_entry_schema_has_required_fields(cache: ResultCache, tmp_path: Path) -> None:
    """Written JSON entry has key, result, written_at, and ttl_seconds fields."""
    cache.put(PROMPT, DIGESTS, RESULT, ttl_seconds=3600)
    key = _cache_key(PROMPT, DIGESTS)
    cache_dir = tmp_path / "cache"
    entry_path = cache_dir / f"{key}.json"
    data = json.loads(entry_path.read_text())
    assert data["key"] == key
    assert data["result"] == RESULT
    assert "written_at" in data
    assert data["ttl_seconds"] == 3600


# ---------------------------------------------------------------------------
# 9. key() helper: deterministic and order-independent
# ---------------------------------------------------------------------------


def test_key_is_deterministic(cache: ResultCache) -> None:
    """key() returns the same hex digest for the same inputs."""
    k1 = cache.key(PROMPT, DIGESTS)
    k2 = cache.key(PROMPT, DIGESTS)
    assert k1 == k2
    assert len(k1) == 64  # hex SHA-256 = 64 chars


def test_key_is_order_independent_on_digests(cache: ResultCache) -> None:
    """Digest list order does not affect the cache key (sorted before hashing)."""
    k1 = cache.key(PROMPT, ["abc", "def"])
    k2 = cache.key(PROMPT, ["def", "abc"])
    assert k1 == k2


def test_key_differs_on_prompt_change(cache: ResultCache) -> None:
    """A different prompt yields a different key."""
    k1 = cache.key(PROMPT, DIGESTS)
    k2 = cache.key("Other prompt.", DIGESTS)
    assert k1 != k2


def test_key_differs_on_digest_change(cache: ResultCache) -> None:
    """A different digest list yields a different key."""
    k1 = cache.key(PROMPT, ["abc"])
    k2 = cache.key(PROMPT, ["xyz"])
    assert k1 != k2
