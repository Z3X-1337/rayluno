"""Canonical JSON and Ed25519 signing/verification for update manifests."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Protocol

from .errors import (
    ManifestValidationError,
    SignatureVerificationError,
    UnknownSigningKeyError,
    UpdateDependencyError,
)
from .models import ManifestPolicy, ReleaseManifest, VerifiedManifest, validate_key_id

MAX_SIGNED_MANIFEST_BYTES = 64 * 1024
_ENVELOPE_FIELDS = {"key_id", "manifest", "signature"}


class Ed25519PrivateKeyLike(Protocol):
    def sign(self, data: bytes) -> bytes: ...


def _reject_json_constant(value: str) -> None:
    raise ManifestValidationError(f"non-standard JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestValidationError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def strict_json_object(
    data: bytes, *, max_bytes: int = MAX_SIGNED_MANIFEST_BYTES
) -> dict[str, Any]:
    if not isinstance(data, bytes):
        raise TypeError("signed JSON data must be bytes")
    if not data or len(data) > max_bytes:
        raise ManifestValidationError("signed manifest is empty or exceeds its size limit")
    try:
        text = data.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("signed manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ManifestValidationError("signed manifest envelope must be a JSON object")
    return value


def canonical_signed_payload(key_id: str, manifest: Mapping[str, Any]) -> bytes:
    """Return the one canonical byte representation signed by release tooling."""

    validate_key_id(key_id)
    try:
        return json.dumps(
            {"key_id": key_id, "manifest": dict(manifest)},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError("manifest cannot be encoded as canonical JSON") from exc


def build_signed_envelope(
    manifest: ReleaseManifest,
    *,
    key_id: str,
    private_key: Ed25519PrivateKeyLike,
) -> dict[str, Any]:
    payload = canonical_signed_payload(key_id, manifest.to_dict())
    signature = private_key.sign(payload)
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise SignatureVerificationError("signer did not return a 64-byte Ed25519 signature")
    return {
        "key_id": key_id,
        "manifest": manifest.to_dict(),
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def serialize_signed_envelope(envelope: Mapping[str, Any], *, pretty: bool = False) -> bytes:
    if pretty:
        text = json.dumps(envelope, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
    else:
        text = json.dumps(
            envelope,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return (text + "\n").encode("utf-8")


class Ed25519ManifestVerifier:
    """Verify signed envelopes against a pinned Ed25519 public-key mapping."""

    def __init__(self, public_keys: Mapping[str, bytes]) -> None:
        if not public_keys:
            raise ValueError("at least one trusted update public key is required")
        self._keys = {
            validate_key_id(key_id): _load_public_key(value)
            for key_id, value in public_keys.items()
        }

    def verify(self, envelope_bytes: bytes, policy: ManifestPolicy) -> VerifiedManifest:
        envelope = strict_json_object(envelope_bytes)
        if set(envelope) != _ENVELOPE_FIELDS:
            raise ManifestValidationError("signed envelope fields are not exact")
        key_id = validate_key_id(envelope["key_id"])
        manifest_value = envelope["manifest"]
        if not isinstance(manifest_value, dict):
            raise ManifestValidationError("envelope manifest must be a JSON object")
        signature_value = envelope["signature"]
        if not isinstance(signature_value, str):
            raise ManifestValidationError("signature must be base64 text")
        try:
            signature = base64.b64decode(signature_value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ManifestValidationError("signature is not strict base64") from exc
        if len(signature) != 64:
            raise ManifestValidationError("Ed25519 signature must be exactly 64 bytes")
        public_key = self._keys.get(key_id)
        if public_key is None:
            raise UnknownSigningKeyError("manifest uses an unknown signing key")
        payload = canonical_signed_payload(key_id, manifest_value)
        invalid_signature = _invalid_signature_type()
        try:
            public_key.verify(signature, payload)
        except invalid_signature as exc:
            raise SignatureVerificationError("manifest signature is invalid") from exc
        manifest = ReleaseManifest.from_mapping(manifest_value)
        policy.validate(manifest)
        return VerifiedManifest(
            release=manifest,
            key_id=key_id,
            signed_payload_sha256=hashlib.sha256(payload).hexdigest(),
        )


def _load_public_key(value: bytes) -> Any:
    if not isinstance(value, bytes):
        raise TypeError("trusted public keys must be bytes (raw 32-byte or PEM)")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise UpdateDependencyError(
            "Ed25519 verification requires the 'cryptography' package"
        ) from exc
    try:
        if len(value) == 32:
            return Ed25519PublicKey.from_public_bytes(value)
        key = serialization.load_pem_public_key(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted update public key is not valid Ed25519 material") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("trusted update public key must be Ed25519")
    return key


def _invalid_signature_type() -> type[Exception]:
    try:
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:  # pragma: no cover - keys cannot load without this package.
        raise UpdateDependencyError("cryptography became unavailable during verification") from exc
    return InvalidSignature
