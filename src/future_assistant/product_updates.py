"""Product-facing update checks that stage, but never execute, signed installers."""

from __future__ import annotations

import ctypes
import os
import platform
import sys
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from threading import RLock

from . import __version__
from .identity import (
    COMPATIBILITY_DATA_DIRECTORY,
    COMPATIBILITY_DISTRIBUTION_MARKER,
    COMPATIBILITY_UPDATE_PRODUCT,
    PRODUCT_NAME,
    environment_value,
)
from .updates import (
    Ed25519ManifestVerifier,
    ManifestPolicy,
    NoUpdateAvailableError,
    SecureUpdateClient,
    UpdateCheckResult,
    UpdateError,
)

UPDATE_KEY_ID = "stable-2026"
UPDATE_PRODUCT = COMPATIBILITY_UPDATE_PRODUCT
ERROR_INSUFFICIENT_BUFFER = 122
APPMODEL_ERROR_NO_PACKAGE = 15700
DISTRIBUTION_MARKER = COMPATIBILITY_DISTRIBUTION_MARKER
STORE_DISTRIBUTION = "microsoft-store"
SIDELOAD_DISTRIBUTION = "msix-sideload"


def is_msix_packaged() -> bool:
    """Return whether this process has Windows package identity."""

    if os.name != "nt":
        return False
    try:
        get_package_name = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentPackageFullName
    except (AttributeError, OSError):
        return False
    length = ctypes.c_uint32(0)
    get_package_name.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
    get_package_name.restype = ctypes.c_long
    result = get_package_name(ctypes.byref(length), None)
    if result == APPMODEL_ERROR_NO_PACKAGE:
        return False
    if result != ERROR_INSUFFICIENT_BUFFER or length.value == 0:
        return False
    package_name = ctypes.create_unicode_buffer(length.value)
    return get_package_name(ctypes.byref(length), package_name) == 0 and bool(package_name.value)


def packaged_distribution_channel(*, executable: Path | None = None) -> str | None:
    """Return the signed package channel, or ``None`` for a direct installation.

    Package identity alone does not prove that Microsoft Store delivered the
    package: a development or enterprise-sideloaded MSIX has the same Windows
    identity APIs. The MSIX builder therefore places a channel marker beside
    the executable inside the signed package payload.
    """

    if not is_msix_packaged():
        return None
    executable_path = executable or Path(sys.executable)
    marker = executable_path.resolve().parent / DISTRIBUTION_MARKER
    try:
        channel = marker.read_text(encoding="utf-8").strip().casefold()
    except (OSError, UnicodeError):
        return "msix-unknown"
    if channel in {STORE_DISTRIBUTION, SIDELOAD_DISTRIBUTION}:
        return channel
    return "msix-unknown"


def default_update_directory() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / COMPATIBILITY_DATA_DIRECTORY / "updates"


@dataclass(frozen=True, slots=True)
class ProductUpdateStatus:
    configured: bool
    managed_by_store: bool = False
    checked: bool = False
    available: bool = False
    current_version: str = __version__
    version: str | None = None
    size: int | None = None
    staged_path: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "configured": self.configured,
            "managed_by_store": self.managed_by_store,
            "checked": self.checked,
            "available": self.available,
            "current_version": self.current_version,
            "version": self.version,
            "size": self.size,
            "staged": self.staged_path is not None,
        }


class ProductUpdateService:
    def __init__(
        self,
        client: SecureUpdateClient | None,
        *,
        destination: Path | None = None,
        managed_by_store: bool = False,
    ) -> None:
        if client is not None and managed_by_store:
            raise ValueError("Store-managed updates cannot use the direct update client")
        self._client = client
        self._destination = destination or default_update_directory()
        self._managed_by_store = managed_by_store
        self._last_check: UpdateCheckResult | None = None
        self._staged_path: Path | None = None
        self._lock = RLock()

    @property
    def configured(self) -> bool:
        return self._client is not None

    @property
    def managed_by_store(self) -> bool:
        return self._managed_by_store

    def current_status(self) -> ProductUpdateStatus:
        with self._lock:
            if self._last_check is None:
                return ProductUpdateStatus(
                    configured=self.configured,
                    managed_by_store=self.managed_by_store,
                )
            release = self._last_check.manifest.release
            return ProductUpdateStatus(
                configured=True,
                checked=True,
                available=self._last_check.update_available,
                version=release.version,
                size=release.size,
                staged_path=str(self._staged_path) if self._staged_path else None,
            )

    def check(self) -> ProductUpdateStatus:
        if self.managed_by_store:
            return ProductUpdateStatus(configured=False, managed_by_store=True)
        if self._client is None:
            return ProductUpdateStatus(configured=False)
        with self._lock:
            self._last_check = self._client.check()
            self._staged_path = None
            release = self._last_check.manifest.release
            return ProductUpdateStatus(
                configured=True,
                checked=True,
                available=self._last_check.update_available,
                version=release.version,
                size=release.size,
            )

    def stage(self) -> ProductUpdateStatus:
        with self._lock:
            if self.managed_by_store:
                raise RuntimeError("updates are managed by Microsoft Store")
            if self._client is None or self._last_check is None:
                raise RuntimeError("a successful update check is required before staging")
            if not self._last_check.update_available:
                raise NoUpdateAvailableError("the checked release is not newer")
            release = self._last_check.manifest.release
            destination = self._destination / f"{PRODUCT_NAME}-Setup-{release.version}.exe"
            downloaded = self._client.download(self._last_check, destination)
            self._staged_path = downloaded.path
            return ProductUpdateStatus(
                configured=True,
                checked=True,
                available=True,
                version=release.version,
                size=release.size,
                staged_path=str(downloaded.path),
            )


def build_default_update_service() -> ProductUpdateService:
    distribution_channel = packaged_distribution_channel()
    if distribution_channel == STORE_DISTRIBUTION:
        # Store packages use Store servicing. Never stage the direct EXE
        # installer from inside them, even if a direct-install environment
        # value is still present.
        return ProductUpdateService(None, managed_by_store=True)
    if distribution_channel is not None:
        # Development and enterprise sideload packages are not Store-managed,
        # but applying the direct NSIS installer from inside MSIX is unsafe and
        # can create two independently serviced installations.
        return ProductUpdateService(None)
    manifest_url = environment_value("UPDATE_MANIFEST_URL").strip()
    if not manifest_url:
        return ProductUpdateService(None)
    public_key = files("future_assistant").joinpath("assets/updates-public.pem").read_bytes()
    verifier = Ed25519ManifestVerifier({UPDATE_KEY_ID: public_key})
    os_version = platform.version()
    try:
        parts = [int(item) for item in os_version.split(".")]
    except ValueError:
        parts = [10, 0, 19041]
    parts = (parts + [0, 0, 0])[:3]
    normalized_os = ".".join(str(item) for item in parts)
    policy = ManifestPolicy(
        expected_product=UPDATE_PRODUCT,
        channel="stable",
        current_version=__version__,
        os_version=normalized_os,
    )
    return ProductUpdateService(
        SecureUpdateClient(
            manifest_url=manifest_url,
            verifier=verifier,
            policy=policy,
        )
    )


def safe_update_error(error: Exception) -> str:
    """Map updater failures to a single non-sensitive product boundary."""

    if isinstance(error, UpdateError):
        return "تعذّر التحقق من التحديث بأمان."
    return "تعذّر تجهيز التحديث."
