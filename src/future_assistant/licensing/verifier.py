"""Ed25519 signature and offline time-policy verification."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .codec import decode_token, signing_message
from .errors import (
    InvalidLicenseSignatureError,
    InvalidPublicKeyError,
    LicenseClockRollbackError,
    LicenseExpiredError,
    LicenseNotYetValidError,
    LicensingDependencyError,
)
from .models import VerifiedLicense

MAX_PUBLIC_KEY_BYTES: Final = 16_384


def _crypto_types() -> tuple[type, type, type]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:  # pragma: no cover - depends on external environment
        raise LicensingDependencyError(
            "Install the 'rayluno-assistant[licensing]' optional dependency."
        ) from exc
    return InvalidSignature, serialization, Ed25519PublicKey


@dataclass(frozen=True, slots=True)
class LicenseTimePolicy:
    """Small tolerances for network-free wall-clock validation."""

    maximum_future_issue_seconds: int = 300
    maximum_rollback_seconds: int = 300

    def __post_init__(self) -> None:
        for field_name in ("maximum_future_issue_seconds", "maximum_rollback_seconds"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 86_400:
                raise ValueError(f"{field_name} must be an integer between 0 and 86400")


def _timestamp(value: int | None) -> int:
    timestamp = int(time.time()) if value is None else value
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise ValueError("now must be a non-negative integer Unix timestamp")
    return timestamp


class LicenseVerifier:
    """Verify licenses using only a distributable Ed25519 public key."""

    def __init__(self, public_key: object, *, policy: LicenseTimePolicy | None = None) -> None:
        _invalid_signature, _serialization, public_key_type = _crypto_types()
        if not isinstance(public_key, public_key_type):
            raise InvalidPublicKeyError("public key must be an Ed25519 public key")
        self._public_key = public_key
        self._policy = policy or LicenseTimePolicy()

    @classmethod
    def from_pem(
        cls,
        pem: bytes,
        *,
        policy: LicenseTimePolicy | None = None,
    ) -> LicenseVerifier:
        if not isinstance(pem, bytes) or not pem or len(pem) > MAX_PUBLIC_KEY_BYTES:
            raise InvalidPublicKeyError("public-key PEM is empty or too large")
        _invalid_signature, serialization, _public_key_type = _crypto_types()
        try:
            public_key = serialization.load_pem_public_key(pem)
        except (TypeError, ValueError) as exc:
            raise InvalidPublicKeyError("could not parse public-key PEM") from exc
        return cls(public_key, policy=policy)

    @classmethod
    def from_pem_file(
        cls,
        path: Path,
        *,
        policy: LicenseTimePolicy | None = None,
    ) -> LicenseVerifier:
        try:
            pem = Path(path).read_bytes()
        except OSError as exc:
            raise InvalidPublicKeyError("could not read public-key PEM") from exc
        return cls.from_pem(pem, policy=policy)

    @classmethod
    def from_raw_public_key(
        cls,
        raw: bytes,
        *,
        policy: LicenseTimePolicy | None = None,
    ) -> LicenseVerifier:
        if not isinstance(raw, bytes) or len(raw) != 32:
            raise InvalidPublicKeyError("raw Ed25519 public key must be 32 bytes")
        _invalid_signature, _serialization, public_key_type = _crypto_types()
        try:
            public_key = public_key_type.from_public_bytes(raw)
        except ValueError as exc:
            raise InvalidPublicKeyError("could not parse raw Ed25519 public key") from exc
        return cls(public_key, policy=policy)

    def verify(
        self,
        token: str | bytes,
        *,
        now: int | None = None,
        trusted_time_floor: int | None = None,
    ) -> VerifiedLicense:
        """Authenticate claims and enforce signed expiry plus clock-integrity policy."""

        document, signature, claims = decode_token(token)
        invalid_signature, _serialization, _public_key_type = _crypto_types()
        try:
            self._public_key.verify(signature, signing_message(document))
        except invalid_signature as exc:
            raise InvalidLicenseSignatureError("license signature is invalid") from exc

        verified_at = _timestamp(now)
        if trusted_time_floor is not None:
            if (
                isinstance(trusted_time_floor, bool)
                or not isinstance(trusted_time_floor, int)
                or trusted_time_floor < 0
            ):
                raise ValueError("trusted_time_floor must be a non-negative integer timestamp")
            if verified_at + self._policy.maximum_rollback_seconds < trusted_time_floor:
                raise LicenseClockRollbackError("system clock moved behind the trusted time floor")
        if verified_at + self._policy.maximum_future_issue_seconds < claims.issued_at:
            raise LicenseNotYetValidError("license was issued too far in the future")
        if verified_at > claims.expires_at:
            raise LicenseExpiredError("license has expired")
        return VerifiedLicense(claims=claims, verified_at=verified_at)
