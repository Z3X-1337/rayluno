from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from future_assistant.updates import (
    DownloadIntegrityError,
    DownloadSizeError,
    NoUpdateAvailableError,
    ReleaseManifest,
    SecureUpdateClient,
    TransportSecurityError,
    UpdateCheckResult,
    UpdateDownloader,
    VerifiedManifest,
)


class FakeResponse:
    def __init__(self, content: bytes, final_url: str) -> None:
        self._stream = io.BytesIO(content)
        self.final_url = final_url

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


class FakeTransport:
    def __init__(self, responses: dict[str, tuple[bytes, str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, float]] = []

    @contextmanager
    def open(self, url: str, *, timeout: float) -> Iterator[FakeResponse]:
        self.calls.append((url, timeout))
        content, final_url = self.responses[url]
        yield FakeResponse(content, final_url)


def _verified(content: bytes, **overrides: object) -> VerifiedManifest:
    values: dict[str, object] = {
        "schema_version": 1,
        "product": "future-assistant",
        "channel": "stable",
        "version": "1.2.0",
        "url": "https://updates.example.test/setup.exe",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "min_os": "10.0.19041",
    }
    values.update(overrides)
    return VerifiedManifest(ReleaseManifest.from_mapping(values), "key-1", "f" * 64)


def test_download_is_streamed_verified_and_atomically_replaces_destination(tmp_path: Path) -> None:
    content = b"a secure installer" * 100
    manifest = _verified(content)
    transport = FakeTransport({manifest.release.url: (content, manifest.release.url)})
    destination = tmp_path / "ready" / "setup.exe"
    destination.parent.mkdir()
    destination.write_bytes(b"older staged installer")

    result = UpdateDownloader(transport=transport, chunk_size=17).download(manifest, destination)

    assert destination.read_bytes() == content
    assert result.path == destination
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert result.size == len(content)
    assert not list(destination.parent.glob("*.part"))


def test_hash_mismatch_preserves_previous_file_and_cleans_temporary_file(tmp_path: Path) -> None:
    content = b"downloaded but corrupted"
    manifest = _verified(content, sha256="0" * 64)
    transport = FakeTransport({manifest.release.url: (content, manifest.release.url)})
    destination = tmp_path / "setup.exe"
    destination.write_bytes(b"known good previous file")

    with pytest.raises(DownloadIntegrityError):
        UpdateDownloader(transport=transport).download(manifest, destination)

    assert destination.read_bytes() == b"known good previous file"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    ("actual", "declared"),
    [(b"too long", 3), (b"short", 999)],
)
def test_download_must_match_exact_signed_size(
    tmp_path: Path, actual: bytes, declared: int
) -> None:
    manifest = _verified(actual, size=declared)
    transport = FakeTransport({manifest.release.url: (actual, manifest.release.url)})

    with pytest.raises(DownloadSizeError):
        UpdateDownloader(transport=transport, chunk_size=2).download(
            manifest, tmp_path / "setup.exe"
        )

    assert not (tmp_path / "setup.exe").exists()
    assert not list(tmp_path.glob("*.part"))


def test_downloader_rejects_https_to_http_redirect_before_writing(tmp_path: Path) -> None:
    content = b"installer"
    manifest = _verified(content)
    transport = FakeTransport(
        {manifest.release.url: (content, "http://mirror.example.test/setup.exe")}
    )

    with pytest.raises(TransportSecurityError):
        UpdateDownloader(transport=transport).download(manifest, tmp_path / "setup.exe")

    assert not (tmp_path / "setup.exe").exists()


class FakeVerifier:
    def __init__(self, verified: VerifiedManifest) -> None:
        self.verified = verified
        self.received: list[bytes] = []

    def verify(self, envelope_bytes: bytes, policy: object) -> VerifiedManifest:
        del policy
        self.received.append(envelope_bytes)
        return self.verified


def test_client_uses_injected_transport_and_does_not_download_current_version() -> None:
    from future_assistant.updates import ManifestPolicy

    manifest_url = "https://updates.example.test/stable.json"
    manifest = _verified(b"installer", version="1.0.0")
    verifier = FakeVerifier(manifest)
    transport = FakeTransport({manifest_url: (b"signed envelope", manifest_url)})
    client = SecureUpdateClient(
        manifest_url=manifest_url,
        verifier=verifier,
        policy=ManifestPolicy(
            expected_product="future-assistant",
            channel="stable",
            current_version="1.0.0",
            os_version="10.0.22631",
        ),
        transport=transport,
    )

    check = client.check()

    assert check.update_available is False
    assert verifier.received == [b"signed envelope"]
    with pytest.raises(NoUpdateAvailableError):
        client.download(check, "never-created.exe")


def test_client_rejects_stale_check_before_any_installer_request(tmp_path: Path) -> None:
    from future_assistant.updates import ManifestPolicy

    manifest = _verified(b"installer", version="2.0.0")
    transport = FakeTransport({})
    client = SecureUpdateClient(
        manifest_url="https://updates.example.test/stable.json",
        verifier=FakeVerifier(manifest),
        policy=ManifestPolicy(
            expected_product="future-assistant",
            channel="stable",
            current_version="1.0.0",
            os_version="10.0.22631",
        ),
        transport=transport,
    )
    stale = UpdateCheckResult(manifest, "0.9.0", True)

    with pytest.raises(NoUpdateAvailableError, match="stale"):
        client.download(stale, tmp_path / "setup.exe")

    assert transport.calls == []


def test_manifest_response_is_size_limited() -> None:
    from future_assistant.updates import ManifestPolicy

    manifest_url = "https://updates.example.test/stable.json"
    transport = FakeTransport({manifest_url: (b"x" * 20, manifest_url)})
    client = SecureUpdateClient(
        manifest_url=manifest_url,
        verifier=FakeVerifier(_verified(b"installer")),
        policy=ManifestPolicy(
            expected_product="future-assistant",
            channel="stable",
            current_version="1.0.0",
            os_version="10.0.22631",
        ),
        transport=transport,
        max_manifest_bytes=10,
    )

    with pytest.raises(DownloadSizeError):
        client.check()


def test_explicit_downgrade_policy_marks_an_older_release_available() -> None:
    from future_assistant.updates import ManifestPolicy

    manifest_url = "https://updates.example.test/recovery.json"
    manifest = _verified(b"installer", version="1.0.0")
    transport = FakeTransport({manifest_url: (b"signed envelope", manifest_url)})
    client = SecureUpdateClient(
        manifest_url=manifest_url,
        verifier=FakeVerifier(manifest),
        policy=ManifestPolicy(
            expected_product="future-assistant",
            channel="stable",
            current_version="2.0.0",
            os_version="10.0.22631",
            allow_downgrade=True,
        ),
        transport=transport,
    )

    assert client.check().update_available is True
