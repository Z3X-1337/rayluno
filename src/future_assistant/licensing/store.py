"""Atomic per-user storage for an authenticated token and offline clock floor."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from typing import Final

from ..identity import COMPATIBILITY_DATA_DIRECTORY
from .codec import MAX_TOKEN_BYTES, normalize_token
from .errors import (
    LicenseClockError,
    LicenseNotInstalledError,
    LicenseStorageError,
)
from .models import VerifiedLicense
from .verifier import LicenseVerifier

APP_DIRECTORY_NAME: Final = COMPATIBILITY_DATA_DIRECTORY
LICENSE_DIRECTORY_NAME: Final = "license"
TOKEN_FILE_NAME: Final = "license.json"
CLOCK_FILE_NAME: Final = "clock.json"
CLOCK_SCHEMA_VERSION: Final = 1
_MAX_TIMESTAMP: Final = 253_402_300_799


def default_license_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / APP_DIRECTORY_NAME / LICENSE_DIRECTORY_NAME


def _atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    descriptor = -1
    try:
        descriptor, raw_temporary_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(raw_temporary_path)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        with suppress(OSError):
            temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                temporary_path.unlink()


class LicenseStore:
    """Install only verified tokens and track a monotonic wall-clock floor."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = Path(directory) if directory is not None else default_license_directory()
        self._lock = threading.RLock()

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def token_path(self) -> Path:
        return self._directory / TOKEN_FILE_NAME

    @property
    def clock_path(self) -> Path:
        return self._directory / CLOCK_FILE_NAME

    def _load_clock_floor(self) -> int | None:
        try:
            raw = self.clock_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise LicenseStorageError("could not read license clock state") from exc
        if len(raw) > 1_024:
            raise LicenseClockError("license clock state is invalid")

        def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
            document: dict[str, object] = {}
            for key, value in pairs:
                if key in document:
                    raise LicenseClockError("license clock state contains duplicate keys")
                document[key] = value
            return document

        try:
            document = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        except LicenseClockError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LicenseClockError("license clock state is invalid") from exc
        if not isinstance(document, dict) or set(document) != {"version", "last_seen_at"}:
            raise LicenseClockError("license clock state is invalid")
        last_seen = document["last_seen_at"]
        if (
            isinstance(document["version"], bool)
            or not isinstance(document["version"], int)
            or document["version"] != CLOCK_SCHEMA_VERSION
            or isinstance(last_seen, bool)
            or not isinstance(last_seen, int)
            or not 0 <= last_seen <= _MAX_TIMESTAMP
        ):
            raise LicenseClockError("license clock state is invalid")
        return last_seen

    def _save_clock_floor(self, timestamp: int) -> None:
        document = {
            "version": CLOCK_SCHEMA_VERSION,
            "last_seen_at": timestamp,
        }
        contents = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        _atomic_write(self.clock_path, contents)

    def load_token(self) -> str:
        """Load the installed token without treating it as authenticated."""

        try:
            raw = self.token_path.read_bytes()
        except FileNotFoundError as exc:
            raise LicenseNotInstalledError("no license token is installed") from exc
        except OSError as exc:
            raise LicenseStorageError("could not read installed license token") from exc
        if not raw or len(raw) > MAX_TOKEN_BYTES + 1:
            raise LicenseStorageError("installed license token is empty or too large")
        try:
            return raw.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise LicenseStorageError("installed license token is not UTF-8") from exc

    def install(
        self,
        token: str | bytes,
        verifier: LicenseVerifier,
        *,
        now: int | None = None,
    ) -> VerifiedLicense:
        """Verify first, then atomically replace the installed token."""

        with self._lock:
            floor = self._load_clock_floor()
            verified = verifier.verify(token, now=now, trusted_time_floor=floor)
            canonical = normalize_token(token).encode("utf-8") + b"\n"
            try:
                # Advance time first: if token replacement fails, the previous
                # valid token remains and a newer clock floor is harmless.
                self._save_clock_floor(max(floor or 0, verified.verified_at))
                _atomic_write(self.token_path, canonical)
            except OSError as exc:
                raise LicenseStorageError("could not atomically install license token") from exc
            return verified

    def verify_installed(
        self,
        verifier: LicenseVerifier,
        *,
        now: int | None = None,
    ) -> VerifiedLicense:
        """Verify the current token and advance the persisted clock floor."""

        with self._lock:
            token = self.load_token()
            floor = self._load_clock_floor()
            verified = verifier.verify(token, now=now, trusted_time_floor=floor)
            next_floor = max(floor or 0, verified.verified_at)
            if next_floor != floor:
                try:
                    self._save_clock_floor(next_floor)
                except OSError as exc:
                    raise LicenseStorageError("could not update license clock state") from exc
            return verified

    def remove(self) -> bool:
        """Remove the token but retain clock history to resist reinstall rollback."""

        with self._lock:
            try:
                self.token_path.unlink()
            except FileNotFoundError:
                return False
            except OSError as exc:
                raise LicenseStorageError("could not remove installed license token") from exc
            return True
