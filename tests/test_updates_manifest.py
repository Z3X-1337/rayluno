from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from future_assistant.updates import (
    ChannelMismatchError,
    DowngradeBlockedError,
    Ed25519ManifestVerifier,
    IncompatibleOSError,
    ManifestPolicy,
    ManifestValidationError,
    ReleaseManifest,
    SemanticVersion,
    SignatureVerificationError,
    TransportSecurityError,
    UnknownSigningKeyError,
    UpdatePolicyError,
    build_signed_envelope,
    canonical_signed_payload,
    serialize_signed_envelope,
)


def _manifest(**overrides: object) -> ReleaseManifest:
    payload = b"signed installer bytes"
    values: dict[str, object] = {
        "schema_version": 1,
        "product": "future-assistant",
        "channel": "stable",
        "version": "1.2.3",
        "url": "https://updates.example.test/stable/setup.exe?token=signed",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "min_os": "10.0.19041",
    }
    values.update(overrides)
    return ReleaseManifest.from_mapping(values)


def _policy(**overrides: object) -> ManifestPolicy:
    values: dict[str, object] = {
        "expected_product": "future-assistant",
        "channel": "stable",
        "current_version": "1.0.0",
        "os_version": "10.0.22631",
    }
    values.update(overrides)
    return ManifestPolicy(**values)  # type: ignore[arg-type]


def _signed(
    manifest: ReleaseManifest | None = None,
) -> tuple[bytes, Ed25519ManifestVerifier, Ed25519PrivateKey]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    envelope = build_signed_envelope(
        manifest or _manifest(), key_id="release-2026", private_key=private
    )
    return (
        serialize_signed_envelope(envelope),
        Ed25519ManifestVerifier({"release-2026": public}),
        private,
    )


def test_valid_ed25519_envelope_is_verified_against_local_policy() -> None:
    signed, verifier, _ = _signed()

    verified = verifier.verify(signed, _policy())

    assert verified.release.version == "1.2.3"
    assert verified.key_id == "release-2026"
    assert len(verified.signed_payload_sha256) == 64


def test_canonical_payload_is_stable_and_includes_key_id() -> None:
    left = canonical_signed_payload("key-1", {"z": 1, "a": "\u0639\u0631\u0628\u064a"})
    right = canonical_signed_payload("key-1", {"a": "\u0639\u0631\u0628\u064a", "z": 1})

    assert left == right
    assert left == '{"key_id":"key-1","manifest":{"a":"\u0639\u0631\u0628\u064a","z":1}}'.encode()


def test_manifest_tampering_invalidates_signature() -> None:
    signed, verifier, _ = _signed()
    envelope = json.loads(signed)
    envelope["manifest"]["version"] = "9.9.9"

    with pytest.raises(SignatureVerificationError):
        verifier.verify(serialize_signed_envelope(envelope), _policy())


def test_unknown_signing_key_is_rejected_even_with_well_formed_signature() -> None:
    signed, _, _ = _signed()
    other_key = Ed25519PrivateKey.generate()
    other_public = other_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )

    with pytest.raises(UnknownSigningKeyError):
        Ed25519ManifestVerifier({"other-key": other_public}).verify(signed, _policy())


def test_duplicate_json_keys_and_unknown_manifest_fields_are_rejected() -> None:
    public = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    )
    verifier = Ed25519ManifestVerifier({"key": public})
    duplicate = b'{"key_id":"key","key_id":"key","manifest":{},"signature":"AA=="}'

    with pytest.raises(ManifestValidationError, match="duplicate"):
        verifier.verify(duplicate, _policy())

    values = _manifest().to_dict()
    values["notes"] = "not part of schema"
    with pytest.raises(ManifestValidationError, match="fields"):
        ReleaseManifest.from_mapping(values)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("version", "v1.2.3", ManifestValidationError),
        ("url", "http://updates.example.test/setup.exe", TransportSecurityError),
        ("url", "https://user:secret@example.test/setup.exe", TransportSecurityError),
        ("url", "https://updates.example.test/setup file.exe", TransportSecurityError),
        ("sha256", "ABC", ManifestValidationError),
        ("size", True, ManifestValidationError),
        ("size", 0, ManifestValidationError),
        ("min_os", "Windows 11", ManifestValidationError),
    ],
)
def test_release_manifest_rejects_invalid_security_fields(
    field: str, value: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        _manifest(**{field: value})


def test_channel_product_size_and_stable_prerelease_policy_are_pinned() -> None:
    with pytest.raises(ChannelMismatchError):
        _policy(channel="beta").validate(_manifest())
    with pytest.raises(UpdatePolicyError, match="product"):
        _policy(expected_product="another-product").validate(_manifest())
    with pytest.raises(UpdatePolicyError, match="size"):
        _policy(max_download_size=2).validate(_manifest())
    with pytest.raises(UpdatePolicyError, match="prerelease"):
        _policy().validate(_manifest(version="1.2.3-rc.1"))


def test_downgrade_is_blocked_by_default_and_can_be_explicitly_enabled() -> None:
    old_release = _manifest(version="1.0.0")

    with pytest.raises(DowngradeBlockedError):
        _policy(current_version="2.0.0").validate(old_release)

    _policy(current_version="2.0.0", allow_downgrade=True).validate(old_release)


def test_newer_minimum_windows_version_is_rejected() -> None:
    with pytest.raises(IncompatibleOSError):
        _policy(os_version="10.0.19045").validate(_manifest(min_os="10.0.22631"))


def test_semver_precedence_handles_prereleases_and_ignores_build_metadata() -> None:
    assert SemanticVersion.parse("1.0.0-alpha.2") < SemanticVersion.parse("1.0.0-alpha.10")
    assert SemanticVersion.parse("1.0.0-rc.1") < SemanticVersion.parse("1.0.0")
    assert SemanticVersion.parse("1.0.0+build.1") == SemanticVersion.parse("1.0.0+build.2")
