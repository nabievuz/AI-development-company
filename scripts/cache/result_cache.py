from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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

    return Path(__file__).resolve().parents[2]


_ROOT = _resolve_root()


DEFAULT_CACHE_DIR: Path = _ROOT / "board" / ".cache"


DEFAULT_TTL_SECONDS: int = 86_400


def _cache_key(prompt: str, input_digests: list[str]) -> str:
    payload = prompt + "".join(sorted(input_digests))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResultCache:

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        event_store: Any | None = None,
    ) -> None:
        self._cache_dir: Path = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self._event_store: Any | None = event_store


    def key(self, prompt: str, input_digests: list[str]) -> str:
        return _cache_key(prompt, input_digests)

    def get(
        self,
        prompt: str,
        input_digests: list[str],
        *,
        ticket_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any] | None:
        k = _cache_key(prompt, input_digests)
        entry = self._load_entry(k)
        if entry is None:
            return None


        if self._is_expired(entry):
            return None


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


    def _entry_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _load_entry(self, key: str) -> dict[str, Any] | None:
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
        written_at_str: str = entry.get("written_at", "")
        ttl: int = int(entry.get("ttl_seconds", DEFAULT_TTL_SECONDS))
        try:

            written_at = datetime.fromisoformat(written_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):

            return True
        now = datetime.now(tz=UTC)
        age_seconds = (now - written_at).total_seconds()
        return age_seconds > ttl

    def _get_event_store(self) -> Any:
        if self._event_store is None:

            from dgox.events import EventStore

            self._event_store = EventStore()
        return self._event_store

    def _log_hit(self, cache_key: str, ticket_id: str, *, run_id: str | None = None) -> None:
        try:
            from dgox.events import build_cache_hit

            store = self._get_event_store()
            ev = build_cache_hit(
                ticket_id=ticket_id,
                cache_key=cache_key,
                created_at=_utcnow(),
                run_id=run_id,
            )
            store.append(ev)
        except Exception:


            pass


def _utcnow() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
