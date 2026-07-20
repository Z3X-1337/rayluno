"""Offline-verifiable commercial licensing primitives.

Only public-key verification lives in the distributable product. The private-key
issuer is deliberately kept under the repository's non-packaged ``tools`` folder.
"""

from .errors import (
    InvalidLicenseSignatureError,
    InvalidLicenseTokenError,
    InvalidPublicKeyError,
    LicenseClockError,
    LicenseClockRollbackError,
    LicenseExpiredError,
    LicenseNotInstalledError,
    LicenseNotYetValidError,
    LicenseStorageError,
    LicensingDependencyError,
    LicensingError,
)
from .models import LicenseClaims, LicenseEdition, VerifiedLicense
from .store import LicenseStore, default_license_directory
from .verifier import LicenseTimePolicy, LicenseVerifier

__all__ = [
    "InvalidLicenseSignatureError",
    "InvalidLicenseTokenError",
    "InvalidPublicKeyError",
    "LicenseClaims",
    "LicenseClockError",
    "LicenseClockRollbackError",
    "LicenseEdition",
    "LicenseExpiredError",
    "LicenseNotInstalledError",
    "LicenseNotYetValidError",
    "LicenseStorageError",
    "LicenseStore",
    "LicenseTimePolicy",
    "LicenseVerifier",
    "LicensingDependencyError",
    "LicensingError",
    "VerifiedLicense",
    "default_license_directory",
]
