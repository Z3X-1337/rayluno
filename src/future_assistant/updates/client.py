"""High-level check/download facade for the secure update subsystem."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .downloader import DownloadedUpdate, UpdateDownloader
from .errors import NoUpdateAvailableError
from .models import ManifestPolicy, SemanticVersion, UpdateCheckResult, VerifiedManifest
from .signing import MAX_SIGNED_MANIFEST_BYTES
from .transport import UpdateTransport, UrllibUpdateTransport, read_limited_response


class ManifestVerifier(Protocol):
    def verify(self, envelope_bytes: bytes, policy: ManifestPolicy) -> VerifiedManifest: ...


class SecureUpdateClient:
    """Fetch signed metadata and stage installers; never execute installers."""

    def __init__(
        self,
        *,
        manifest_url: str,
        verifier: ManifestVerifier,
        policy: ManifestPolicy,
        transport: UpdateTransport | None = None,
        timeout: float = 30.0,
        max_manifest_bytes: int = MAX_SIGNED_MANIFEST_BYTES,
    ) -> None:
        if timeout <= 0 or max_manifest_bytes <= 0:
            raise ValueError("update client limits must be positive")
        self._manifest_url = manifest_url
        self._verifier = verifier
        self._policy = policy
        self._transport = transport or UrllibUpdateTransport()
        self._timeout = timeout
        self._max_manifest_bytes = max_manifest_bytes

    def check(self) -> UpdateCheckResult:
        envelope = read_limited_response(
            self._transport,
            self._manifest_url,
            max_bytes=self._max_manifest_bytes,
            timeout=self._timeout,
        )
        manifest = self._verifier.verify(envelope, self._policy)
        self._policy.validate(manifest.release)
        available = self._is_available(manifest)
        return UpdateCheckResult(manifest, self._policy.current_version, available)

    def download(self, check: UpdateCheckResult, destination: str | Path) -> DownloadedUpdate:
        if not check.update_available:
            raise NoUpdateAvailableError(
                "the checked release is not newer than the installed version"
            )
        if check.current_version != self._policy.current_version:
            raise NoUpdateAvailableError("the update check is stale for the installed version")
        self._policy.validate(check.manifest.release)
        if not self._is_available(check.manifest):
            raise NoUpdateAvailableError(
                "the checked release is not installable under local policy"
            )
        downloader = UpdateDownloader(
            transport=self._transport,
            max_download_size=self._policy.max_download_size,
            timeout=self._timeout,
        )
        return downloader.download(check.manifest, destination)

    def _is_available(self, manifest: VerifiedManifest) -> bool:
        current = SemanticVersion.parse(self._policy.current_version)
        target = SemanticVersion.parse(manifest.release.version)
        return current < target or (self._policy.allow_downgrade and target < current)
