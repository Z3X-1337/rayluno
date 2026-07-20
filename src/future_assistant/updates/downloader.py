"""Bounded, hash-verified, atomic update package downloads."""

from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .errors import DownloadError, DownloadIntegrityError, DownloadSizeError, UpdateTransportError
from .models import DEFAULT_MAX_DOWNLOAD_SIZE, VerifiedManifest, validate_https_url
from .transport import UpdateTransport, UrllibUpdateTransport


@dataclass(frozen=True, slots=True)
class DownloadedUpdate:
    """A verified installer staged on disk; it has not been executed."""

    path: Path
    version: str
    sha256: str
    size: int


class UpdateDownloader:
    def __init__(
        self,
        *,
        transport: UpdateTransport | None = None,
        max_download_size: int = DEFAULT_MAX_DOWNLOAD_SIZE,
        timeout: float = 60.0,
        chunk_size: int = 256 * 1024,
    ) -> None:
        if max_download_size <= 0 or timeout <= 0 or chunk_size <= 0:
            raise ValueError("download limits and timeout must be positive")
        self._transport = transport or UrllibUpdateTransport()
        self._max_download_size = max_download_size
        self._timeout = timeout
        self._chunk_size = chunk_size

    def download(self, manifest: VerifiedManifest, destination: str | Path) -> DownloadedUpdate:
        """Download and stage a verified release without launching its installer."""

        if not isinstance(manifest, VerifiedManifest):
            raise TypeError("download requires a VerifiedManifest")
        release = manifest.release
        validate_https_url(release.url)
        if release.size > self._max_download_size:
            raise DownloadSizeError("declared installer size exceeds the downloader limit")

        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            raise DownloadError("update destination cannot be a directory")
        temporary_path: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".part",
                dir=target.parent,
            )
            temporary_path = Path(raw_path)
            digest = hashlib.sha256()
            downloaded = 0
            with os.fdopen(descriptor, "wb") as output:
                with self._transport.open(release.url, timeout=self._timeout) as response:
                    validate_https_url(response.final_url)
                    while True:
                        chunk = response.read(self._chunk_size)
                        if not chunk:
                            break
                        if not isinstance(chunk, bytes):
                            raise UpdateTransportError("update transport returned non-byte data")
                        downloaded += len(chunk)
                        if downloaded > release.size or downloaded > self._max_download_size:
                            raise DownloadSizeError("installer exceeded its signed size")
                        output.write(chunk)
                        digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())

            if downloaded != release.size:
                raise DownloadSizeError("installer size does not match the signed manifest")
            actual_sha256 = digest.hexdigest()
            if not hmac.compare_digest(actual_sha256, release.sha256):
                raise DownloadIntegrityError("installer SHA-256 does not match the signed manifest")
            os.replace(temporary_path, target)
            temporary_path = None
            return DownloadedUpdate(target, release.version, actual_sha256, downloaded)
        except (DownloadError, UpdateTransportError):
            raise
        except OSError as exc:
            raise DownloadError("could not stage the downloaded installer") from exc
        finally:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
