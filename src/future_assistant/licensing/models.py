"""Strict immutable models for signed Free and Pro license claims."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .errors import InvalidLicenseTokenError

_LICENSE_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_CUSTOMER_HASH_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_FEATURE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_CLAIM_KEYS: Final[frozenset[str]] = frozenset(
    {
        "license_id",
        "edition",
        "customer_hash",
        "issued_at",
        "expires_at",
        "device_limit",
        "features",
    }
)
_MAX_TIMESTAMP: Final = 253_402_300_799  # 9999-12-31T23:59:59Z


class LicenseEdition(StrEnum):
    """Commercial editions encoded in signed claims."""

    FREE = "free"
    PRO = "pro"


def _strict_integer(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidLicenseTokenError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise InvalidLicenseTokenError(f"{field} is outside the supported range")
    return value


def _clean_identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _LICENSE_ID_PATTERN.fullmatch(value):
        raise InvalidLicenseTokenError(f"{field} has an invalid format")
    return value


@dataclass(frozen=True, slots=True)
class LicenseClaims:
    """The complete signed entitlement document.

    Timestamps are UTC Unix seconds. ``customer_hash`` is a lowercase SHA-256
    digest of an operator-chosen stable customer reference, never raw PII.
    """

    license_id: str
    edition: LicenseEdition
    customer_hash: str
    issued_at: int
    expires_at: int
    device_limit: int
    features: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "license_id",
            _clean_identifier(self.license_id, field="license_id"),
        )
        if not isinstance(self.edition, LicenseEdition):
            raise InvalidLicenseTokenError("edition must be free or pro")
        if not isinstance(self.customer_hash, str) or not _CUSTOMER_HASH_PATTERN.fullmatch(
            self.customer_hash
        ):
            raise InvalidLicenseTokenError("customer_hash must be a lowercase SHA-256 digest")
        issued_at = _strict_integer(
            self.issued_at,
            field="issued_at",
            minimum=0,
            maximum=_MAX_TIMESTAMP,
        )
        expires_at = _strict_integer(
            self.expires_at,
            field="expires_at",
            minimum=1,
            maximum=_MAX_TIMESTAMP,
        )
        if expires_at <= issued_at:
            raise InvalidLicenseTokenError("expires_at must be later than issued_at")
        _strict_integer(
            self.device_limit,
            field="device_limit",
            minimum=1,
            maximum=10_000,
        )
        if not isinstance(self.features, tuple):
            raise InvalidLicenseTokenError("features must be a JSON array")
        if len(self.features) > 256:
            raise InvalidLicenseTokenError("features contains too many entries")
        if any(
            not isinstance(feature, str)
            or len(feature) > 100
            or not _FEATURE_PATTERN.fullmatch(feature)
            for feature in self.features
        ):
            raise InvalidLicenseTokenError("features contains an invalid feature identifier")
        if tuple(sorted(set(self.features))) != self.features:
            raise InvalidLicenseTokenError("features must be unique and sorted")

    def to_mapping(self) -> dict[str, object]:
        return {
            "license_id": self.license_id,
            "edition": self.edition.value,
            "customer_hash": self.customer_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "device_limit": self.device_limit,
            "features": list(self.features),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> LicenseClaims:
        if not isinstance(value, Mapping):
            raise InvalidLicenseTokenError("claims must be a JSON object")
        if set(value) != _CLAIM_KEYS:
            raise InvalidLicenseTokenError("claims contains unknown or missing fields")
        edition_value = value["edition"]
        try:
            edition = LicenseEdition(edition_value)
        except (TypeError, ValueError) as exc:
            raise InvalidLicenseTokenError("edition must be free or pro") from exc
        features_value = value["features"]
        if not isinstance(features_value, list):
            raise InvalidLicenseTokenError("features must be a JSON array")
        return cls(
            license_id=value["license_id"],  # type: ignore[arg-type]
            edition=edition,
            customer_hash=value["customer_hash"],  # type: ignore[arg-type]
            issued_at=value["issued_at"],  # type: ignore[arg-type]
            expires_at=value["expires_at"],  # type: ignore[arg-type]
            device_limit=value["device_limit"],  # type: ignore[arg-type]
            features=tuple(features_value),
        )

    def has_feature(self, feature: str) -> bool:
        """Return whether the exact signed feature identifier is enabled."""

        return feature in self.features


@dataclass(frozen=True, slots=True)
class VerifiedLicense:
    """Claims plus the local time at which their signature was checked."""

    claims: LicenseClaims
    verified_at: int

    @property
    def edition(self) -> LicenseEdition:
        return self.claims.edition

    def has_feature(self, feature: str) -> bool:
        return self.claims.has_feature(feature)
