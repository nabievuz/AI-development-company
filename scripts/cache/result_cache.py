"""scripts/cache/result_cache.py — Content-addressed result cache (ORGANISM P6).

Eliminates redundant validator/research dispatches that share the same prompt
and input digests within a wave or across reruns.

Design
------
- **Cache key:** ``sha256(prompt + "".join(sorted(input_digests)))``.
  Concatenating a sorted, stable digest list means any input change yields
  a new key; the sort removes ordering sensitivity.
- **Store:** one JSON file per entry at ``board/.cache/<sha256>.json``.
  The directory is gitignored engine-internal wave state (ADR 0011 posture,
  alongside ``board/.events.jsonl`` and ``board/.wave-log``).
- **Entry schema**::

      {
        "key":         "<hex-sha256>",
        "result":      { ... },        # arbitrary dict returned by the dispatch
        "written_at":  "2026-07-03T12:00:00Z",
        "ttl_seconds": 86400
      }

- **TTL:** entries older than ``ttl_seconds`` from ``written_at`` are treated
  as misses and eligible for overwrite.  Default TTL is 24 h (configurable).
- **Observability:** a cache hit is logged as a ``cache_hit`` event
  (``event_type: "cache_hit"``, ``cached: True``) via ``EventStore`` from
  ``dgox/events.py``.  A miss/execute path is unchanged.

Usage::

    from cache.result_cache import ResultCache

    cache = ResultCache()
    result = cache.get(prompt, input_digests, ticket_id="DAS-1234")
    if result is None:
        result = run_expensive_dispatch(prompt)
        cache.put(prompt, input_digests, result)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Self-locating root (same pattern as dgox/events.py — LAW A).
# ---------------------------------------------------------------------------


def _resolve_root() -> Path:
    override = os.environ.get("DASLAB_ROOT")
    if override:
        return Path(override).resolve()
    try:
        import subprocess

        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if top:
            return Path(top).resolve()
    except Exception:
        pass
    # Fallback: scripts/cache/result_cache.py → scripts/cache/ → scripts/ → root
    return Path(__file__).resolve().parents[2]


_ROOT = _resolve_root()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default cache directory (gitignored — added to .gitignore in DAS-1450).
DEFAULT_CACHE_DIR: Path = _ROOT / "board" / ".cache"

#: Default TTL: 24 hours.  Conservative — a wave rarely spans more than an hour
#: but reruns several hours later should still benefit from the cache.
DEFAULT_TTL_SECONDS: int = 86_400


# ---------------------------------------------------------------------------
# Key helper
# ---------------------------------------------------------------------------


def _cache_key(prompt: str, input_digests: list[str]) -> str:
    """Return the hex SHA-256 cache key for *prompt* + *input_digests*.

    The key is ``sha256(prompt + sorted_digests_concatenated)`` where the
    digests are sorted to remove ordering sensitivity.  Any change to the
    prompt or any input digest yields a different key.
    """
    payload = prompt + "".join(sorted(input_digests))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# ResultCache class
# ---------------------------------------------------------------------------


class ResultCache:
    """Content-addressed result cache backed by ``board/.cache/``.

    Each entry is a single JSON file named ``<sha256-key>.json``.  The
    ``ResultCache`` never modifies existing entries; a cache *put* simply
    writes (or overwrites) the file for that key.

    Args:
        cache_dir:    Directory to store cache entries (default: ``board/.cache``).
        event_store:  ``EventStore`` instance for hit logging.  If *None*, an
                      ``EventStore`` at the default path is constructed lazily on
                      the first hit that supplies a ``ticket_id``.
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        event_store: Any | None = None,
    ) -> None:
        self._cache_dir: Path = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self._event_store: Any | None = event_store  # injected or lazy-constructed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def key(self, prompt: str, input_digests: list[str]) -> str:
        """Return the cache key for *prompt* + *input_digests* without doing I/O."""
        return _cache_key(prompt, input_digests)

    def get(
        self,
        prompt: str,
        input_digests: list[str],
        *,
        ticket_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Look up a cached result; return it or *None* on a miss/expiry.

        On a **hit** (valid, non-expired entry):

        - Returns the stored ``result`` dict.
        - If *ticket_id* is provided, logs a ``cache_hit`` event via the
          ``EventStore`` (appended to ``board/.events.jsonl``).

        On a **miss** (file absent, unreadable, or expired):

        - Returns *None*.
        - Nothing is logged; the caller proceeds with the real dispatch.

        Args:
            prompt:        The dispatch prompt string.
            input_digests: List of stable content digests for every input the
                           dispatch consumes.
            ticket_id:     DAS-NNNN identifier used for event logging.  If
                           *None*, hit logging is skipped silently.
            run_id:        Optional run correlation key forwarded to the event.
        """
        k = _cache_key(prompt, input_digests)
        entry = self._load_entry(k)
        if entry is None:
            return None

        # TTL check: compare written_at + ttl_seconds against now.
        if self._is_expired(entry):
            return None

        # Cache hit — log event if ticket_id was supplied.
        if ticket_id is not None:
            self._log_hit(k, ticket_id, run_id=run_id)

        return entry["result"]

    def put(
        self,
        prompt: str,
        input_digests: list[str],
        result: dict[str, Any],
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Store *result* in the cache under the key for *prompt* + *input_digests*.

        Creates ``board/.cache/`` on first write.  Overwrites any existing entry
        for the same key (including expired ones).

        Args:
            prompt:        The dispatch prompt string.
            input_digests: List of stable content digests for every input.
            result:        The result dict to cache (must be JSON-serialisable).
            ttl_seconds:   TTL for this entry (default: ``DEFAULT_TTL_SECONDS``).
        """
        k = _cache_key(prompt, input_digests)
        entry: dict[str, Any] = {
            "key": k,
            "result": result,
            "written_at": _utcnow(),
            "ttl_seconds": ttl_seconds,
        }
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_dir / f"{k}.json"
        path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _entry_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _load_entry(self, key: str) -> dict[str, Any] | None:
        """Load and parse a cache entry; return *None* on any failure."""
        path = self._entry_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict) or "result" not in data or "written_at" not in data:
            return None
        return data

    @staticmethod
    def _is_expired(entry: dict[str, Any]) -> bool:
        """Return *True* if the entry has outlived its TTL."""
        written_at_str: str = entry.get("written_at", "")
        ttl: int = int(entry.get("ttl_seconds", DEFAULT_TTL_SECONDS))
        try:
            # ISO-8601 UTC ending in 'Z' — replace Z with +00:00 for fromisoformat.
            written_at = datetime.fromisoformat(written_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            # Unparseable timestamp → treat as expired (safe default).
            return True
        now = datetime.now(tz=UTC)
        age_seconds = (now - written_at).total_seconds()
        return age_seconds > ttl

    def _get_event_store(self) -> Any:
        """Return (and lazily construct) the EventStore."""
        if self._event_store is None:
            # Import lazily to avoid circular imports and keep module lightweight.
            from dgox.events import EventStore  # type: ignore[import]

            self._event_store = EventStore()
        return self._event_store

    def _log_hit(self, cache_key: str, ticket_id: str, *, run_id: str | None = None) -> None:
        """Append a ``cache_hit`` event to the event store (best-effort)."""
        try:
            from dgox.events import build_cache_hit  # type: ignore[import]

            store = self._get_event_store()
            ev = build_cache_hit(
                ticket_id=ticket_id,
                cache_key=cache_key,
                created_at=_utcnow(),
                run_id=run_id,
            )
            store.append(ev)
        except Exception:
            # Event logging is advisory (ADR 0011 shadow-mode posture) — never
            # let a logging failure break the dispatch path.
            pass


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string ending in 'Z'."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
