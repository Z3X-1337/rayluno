"""Small local-state security primitives shared by privacy-sensitive subsystems."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any


def secure_directory(path: str | Path) -> Path:
    """Create a private directory and apply restrictive POSIX bits when supported."""

    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        directory.chmod(0o700)
    return directory


def secure_file(path: str | Path) -> Path:
    """Apply restrictive POSIX bits; Windows ACLs remain the primary control there."""

    target = Path(path)
    with suppress(OSError):
        target.chmod(0o600)
    return target


def atomic_write_bytes(path: str | Path, contents: bytes) -> Path:
    """Atomically replace a sensitive file after flushing it to stable storage."""

    target = Path(path)
    secure_directory(target.parent)
    temporary: Path | None = None
    descriptor = -1
    try:
        descriptor, raw_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        secure_file(temporary)
        os.replace(temporary, target)
        temporary = None
        secure_file(target)
        return target
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        if temporary is not None:
            with suppress(FileNotFoundError):
                temporary.unlink()


def load_or_create_key(path: str | Path, *, size: int = 32) -> bytes:
    """Load an exact-size local secret or create it once without overwriting races."""

    if isinstance(size, bool) or not isinstance(size, int) or size < 16:
        raise ValueError("local security keys must contain at least 16 bytes")
    target = Path(path)
    secure_directory(target.parent)
    try:
        key = target.read_bytes()
    except FileNotFoundError:
        candidate = secrets.token_bytes(size)
        descriptor = -1
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(candidate)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
        key = target.read_bytes()
    if len(key) != size:
        raise ValueError("local security key has an invalid length")
    secure_file(target)
    return key


def canonical_json(value: Any) -> bytes:
    """Serialize bounded local metadata deterministically for HMAC operations."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def keyed_digest(key: bytes, value: Mapping[str, object] | object) -> str:
    """Return a non-reversible, installation-scoped HMAC-SHA256 fingerprint."""

    if not isinstance(key, bytes) or len(key) < 16:
        raise ValueError("fingerprint key is invalid")
    return hmac.new(key, canonical_json(value), hashlib.sha256).hexdigest()


__all__ = [
    "atomic_write_bytes",
    "canonical_json",
    "keyed_digest",
    "load_or_create_key",
    "secure_directory",
    "secure_file",
]
