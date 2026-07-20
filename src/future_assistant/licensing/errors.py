"""Typed failures raised by the commercial licensing boundary."""

from __future__ import annotations


class LicensingError(Exception):
    """Base class for licensing failures safe to handle at a product boundary."""


class LicensingDependencyError(LicensingError):
    """Raised when the optional cryptographic dependency is unavailable."""


class InvalidLicenseTokenError(LicensingError, ValueError):
    """Raised when a token is malformed or uses an unsupported schema."""


class InvalidLicenseSignatureError(LicensingError):
    """Raised when an Ed25519 signature does not authenticate the token."""


class InvalidPublicKeyError(LicensingError, ValueError):
    """Raised when a verifier is configured with a non-Ed25519 public key."""


class LicenseExpiredError(LicensingError):
    """Raised when the license is past its signed expiration timestamp."""


class LicenseClockError(LicensingError):
    """Raised when the local clock cannot be trusted for offline validation."""


class LicenseNotYetValidError(LicenseClockError):
    """Raised when a license appears to have been issued too far in the future."""


class LicenseClockRollbackError(LicenseClockError):
    """Raised when wall-clock time moved behind the persisted trusted floor."""


class LicenseStorageError(LicensingError):
    """Raised when installed license or clock-state storage is invalid."""


class LicenseNotInstalledError(LicenseStorageError):
    """Raised when an operation needs an installed token but none exists."""
