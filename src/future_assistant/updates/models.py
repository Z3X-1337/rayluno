"""Strict, dependency-free models for signed Windows update manifests."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import total_ordering
from typing import Any
from urllib.parse import urlsplit

from .errors import (
    ChannelMismatchError,
    DowngradeBlockedError,
    IncompatibleOSError,
    ManifestValidationError,
    TransportSecurityError,
    UpdatePolicyError,
)

MANIFEST_SCHEMA_VERSION = 1
DEFAULT_MAX_DOWNLOAD_SIZE = 1024 * 1024 * 1024

_PRODUCT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_CHANNEL_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}")
_KEY_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_WINDOWS_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")

_MANIFEST_FIELDS = {
    "schema_version",
    "product",
    "channel",
    "version",
    "url",
    "sha256",
    "size",
    "min_os",
}


def validate_https_url(url: str) -> str:
    """Validate an HTTPS URL used for either a manifest or an installer."""

    if not isinstance(url, str) or not url or len(url) > 2048:
        raise TransportSecurityError("update URL must be a non-empty string up to 2048 chars")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise TransportSecurityError("update URL is malformed") from exc
    if parsed.scheme != "https" or not parsed.hostname:
        raise TransportSecurityError("updates require an HTTPS URL with a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise TransportSecurityError("update URLs must not contain credentials")
    if parsed.fragment:
        raise TransportSecurityError("update URLs must not contain fragments")
    if any(character.isspace() or ord(character) == 0x7F for character in url):
        raise TransportSecurityError("update URL contains whitespace or control characters")
    del port  # Accessing it above validates its numeric range.
    return url


def validate_key_id(key_id: str) -> str:
    if not isinstance(key_id, str) or _KEY_ID_RE.fullmatch(key_id) is None:
        raise ManifestValidationError("key_id has an invalid format")
    return key_id


@total_ordering
@dataclass(frozen=True, slots=True, eq=False)
class SemanticVersion:
    """Semantic Version 2.0 precedence (build metadata is ignored)."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> SemanticVersion:
        if not isinstance(value, str):
            raise ManifestValidationError("version must be a semantic-version string")
        match = _SEMVER_RE.fullmatch(value)
        if match is None:
            raise ManifestValidationError("version must use strict Semantic Versioning")
        prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
        build = tuple(match.group(5).split(".")) if match.group(5) else ()
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease, build)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self._core == other._core and self.prerelease == other.prerelease

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        if self._core != other._core:
            return self._core < other._core
        return _prerelease_is_lower(self.prerelease, other.prerelease)

    def __hash__(self) -> int:
        return hash((*self._core, self.prerelease))

    @property
    def _core(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch


def _prerelease_is_lower(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if not left:
        return False
    if not right:
        return True
    for left_item, right_item in zip(left, right, strict=False):
        if left_item == right_item:
            continue
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            return int(left_item) < int(right_item)
        if left_numeric != right_numeric:
            return left_numeric
        return left_item < right_item
    return len(left) < len(right)


@dataclass(frozen=True, slots=True)
class WindowsVersion:
    parts: tuple[int, int, int, int]

    @classmethod
    def parse(cls, value: str) -> WindowsVersion:
        if not isinstance(value, str) or _WINDOWS_VERSION_RE.fullmatch(value) is None:
            raise ManifestValidationError("Windows version must look like 10.0.19041")
        raw = [int(part) for part in value.split(".")]
        raw.extend([0] * (4 - len(raw)))
        return cls(tuple(raw))  # type: ignore[arg-type]

    def __lt__(self, other: WindowsVersion) -> bool:
        return self.parts < other.parts


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """The exact signed release metadata accepted by the updater."""

    schema_version: int
    product: str
    channel: str
    version: str
    url: str
    sha256: str
    size: int
    min_os: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseManifest:
        if not isinstance(value, Mapping):
            raise ManifestValidationError("manifest must be a JSON object")
        if set(value) != _MANIFEST_FIELDS:
            missing = sorted(_MANIFEST_FIELDS - set(value))
            unknown = sorted(set(value) - _MANIFEST_FIELDS)
            raise ManifestValidationError(
                f"manifest fields are not exact (missing={missing}, unknown={unknown})"
            )
        schema_version = value["schema_version"]
        if type(schema_version) is not int or schema_version != MANIFEST_SCHEMA_VERSION:
            raise ManifestValidationError("unsupported manifest schema_version")
        product = value["product"]
        if not isinstance(product, str) or _PRODUCT_RE.fullmatch(product) is None:
            raise ManifestValidationError("product has an invalid format")
        channel = value["channel"]
        if not isinstance(channel, str) or _CHANNEL_RE.fullmatch(channel) is None:
            raise ManifestValidationError("channel has an invalid format")
        version = value["version"]
        SemanticVersion.parse(version)
        url = value["url"]
        validate_https_url(url)
        sha256 = value["sha256"]
        if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
            raise ManifestValidationError("sha256 must contain 64 lowercase hexadecimal chars")
        size = value["size"]
        if type(size) is not int or size <= 0 or size > 2**63 - 1:
            raise ManifestValidationError("size must be a positive 64-bit integer")
        min_os = value["min_os"]
        WindowsVersion.parse(min_os)
        return cls(schema_version, product, channel, version, url, sha256, size, min_os)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "schema_version": self.schema_version,
            "product": self.product,
            "channel": self.channel,
            "version": self.version,
            "url": self.url,
            "sha256": self.sha256,
            "size": self.size,
            "min_os": self.min_os,
        }


@dataclass(frozen=True, slots=True)
class ManifestPolicy:
    """Pinned local expectations applied after signature verification."""

    expected_product: str
    channel: str
    current_version: str
    os_version: str
    allow_downgrade: bool = False
    max_download_size: int = DEFAULT_MAX_DOWNLOAD_SIZE

    def __post_init__(self) -> None:
        if (
            not isinstance(self.expected_product, str)
            or _PRODUCT_RE.fullmatch(self.expected_product) is None
        ):
            raise ValueError("expected_product has an invalid format")
        if not isinstance(self.channel, str) or _CHANNEL_RE.fullmatch(self.channel) is None:
            raise ValueError("channel has an invalid format")
        SemanticVersion.parse(self.current_version)
        WindowsVersion.parse(self.os_version)
        if type(self.allow_downgrade) is not bool:
            raise TypeError("allow_downgrade must be bool")
        if type(self.max_download_size) is not int or self.max_download_size <= 0:
            raise ValueError("max_download_size must be a positive integer")

    def validate(self, manifest: ReleaseManifest) -> None:
        if manifest.product != self.expected_product:
            raise UpdatePolicyError("manifest product does not match this application")
        if manifest.channel != self.channel:
            raise ChannelMismatchError("manifest channel does not match the selected channel")
        target = SemanticVersion.parse(manifest.version)
        current = SemanticVersion.parse(self.current_version)
        if self.channel == "stable" and target.prerelease:
            raise UpdatePolicyError("stable channel cannot install a prerelease version")
        if target < current and not self.allow_downgrade:
            raise DowngradeBlockedError("downgrades are blocked by default")
        if manifest.size > self.max_download_size:
            raise UpdatePolicyError("declared installer size exceeds the local limit")
        if WindowsVersion.parse(self.os_version) < WindowsVersion.parse(manifest.min_os):
            raise IncompatibleOSError("this update requires a newer Windows version")


@dataclass(frozen=True, slots=True)
class VerifiedManifest:
    """A manifest that passed signature, schema, and local policy checks."""

    release: ReleaseManifest
    key_id: str
    signed_payload_sha256: str


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    manifest: VerifiedManifest
    current_version: str
    update_available: bool
