from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path

DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0
LOCK_SUFFIX = ".lock"

_LOCK_POLL_SECONDS = 0.002
_DEFAULT_FILE_MODE = 0o644


class LockTimeout(TimeoutError):
    pass


def lock_path_for(target: Path | str) -> Path:
    target = Path(target)
    return target.with_name(target.name + LOCK_SUFFIX)


@contextlib.contextmanager
def exclusive_lock(
    target: Path | str,
    *,
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> Iterator[Path]:
    lock_file = lock_path_for(target)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, _DEFAULT_FILE_MODE)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire exclusive lock on {lock_file} within {timeout}s"
                    ) from exc
                time.sleep(_LOCK_POLL_SECONDS)
        yield lock_file
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        with contextlib.suppress(OSError):
            os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_text(
    path: Path | str,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        preserved_mode = os.stat(path).st_mode & 0o777
    except OSError:
        preserved_mode = _DEFAULT_FILE_MODE
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, preserved_mode)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise
    _fsync_directory(path.parent)


def locked_update_text(
    path: Path | str,
    transform: Callable[[str], str],
    *,
    missing_ok: bool = True,
    default: str = "",
    encoding: str = "utf-8",
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> str:
    path = Path(path)
    with exclusive_lock(path, timeout=timeout):
        if path.exists():
            current = path.read_text(encoding=encoding)
        elif missing_ok:
            current = default
        else:
            raise FileNotFoundError(f"cannot update missing file: {path}")
        updated = transform(current)
        if updated != current or not path.exists():
            atomic_write_text(path, updated, encoding=encoding)
        return updated


def append_text_durably(path: Path | str, text: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=encoding) as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def locked_append_text(
    path: Path | str,
    text: str,
    *,
    encoding: str = "utf-8",
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> None:
    with exclusive_lock(path, timeout=timeout):
        append_text_durably(path, text, encoding=encoding)


def locked_read_text(
    path: Path | str,
    *,
    default: str = "",
    encoding: str = "utf-8",
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> str:
    path = Path(path)
    with exclusive_lock(path, timeout=timeout):
        if not path.exists():
            return default
        return path.read_text(encoding=encoding)
