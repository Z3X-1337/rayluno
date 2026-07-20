"""Secure, signed Windows update primitives.

This package only checks and stages releases. It intentionally exposes no API
that launches an installer.
"""

from .client import SecureUpdateClient
from .downloader import DownloadedUpdate, UpdateDownloader
from .errors import (
    ChannelMismatchError,
    DowngradeBlockedError,
    DownloadError,
    DownloadIntegrityError,
    DownloadSizeError,
    IncompatibleOSError,
    ManifestValidationError,
    NoUpdateAvailableError,
    SignatureVerificationError,
    TransportSecurityError,
    UnknownSigningKeyError,
    UpdateDependencyError,
    UpdateError,
    UpdatePolicyError,
    UpdateTransportError,
)
from .models import (
    DEFAULT_MAX_DOWNLOAD_SIZE,
    MANIFEST_SCHEMA_VERSION,
    ManifestPolicy,
    ReleaseManifest,
    SemanticVersion,
    UpdateCheckResult,
    VerifiedManifest,
    WindowsVersion,
)
from .signing import (
    Ed25519ManifestVerifier,
    build_signed_envelope,
    canonical_signed_payload,
    serialize_signed_envelope,
)
from .transport import UpdateTransport, UrllibUpdateTransport

__all__ = [
    "DEFAULT_MAX_DOWNLOAD_SIZE",
    "MANIFEST_SCHEMA_VERSION",
    "ChannelMismatchError",
    "DownloadedUpdate",
    "DownloadError",
    "DownloadIntegrityError",
    "DownloadSizeError",
    "DowngradeBlockedError",
    "Ed25519ManifestVerifier",
    "IncompatibleOSError",
    "ManifestPolicy",
    "ManifestValidationError",
    "NoUpdateAvailableError",
    "ReleaseManifest",
    "SecureUpdateClient",
    "SemanticVersion",
    "SignatureVerificationError",
    "TransportSecurityError",
    "UnknownSigningKeyError",
    "UpdateCheckResult",
    "UpdateDependencyError",
    "UpdateDownloader",
    "UpdateError",
    "UpdatePolicyError",
    "UpdateTransport",
    "UpdateTransportError",
    "UrllibUpdateTransport",
    "VerifiedManifest",
    "WindowsVersion",
    "build_signed_envelope",
    "canonical_signed_payload",
    "serialize_signed_envelope",
]
