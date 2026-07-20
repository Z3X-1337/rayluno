"""Product-facing Free/Pro entitlement boundary with fail-closed behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Protocol

from .licensing import (
    LicenseEdition,
    LicenseExpiredError,
    LicenseNotInstalledError,
    LicenseStore,
    LicenseVerifier,
    LicensingDependencyError,
    LicensingError,
    VerifiedLicense,
)

FREE_FEATURES = frozenset({"commands.basic", "privacy.local"})
PRO_FEATURES = frozenset({"ai.local", "automation.pro", "updates.pro", "voice.local"})


class EntitlementState(StrEnum):
    FREE = "free"
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EntitlementSnapshot:
    state: EntitlementState
    edition: LicenseEdition
    features: tuple[str, ...]
    expires_at: int | None = None

    @property
    def pro_active(self) -> bool:
        return self.state is EntitlementState.ACTIVE and self.edition is LicenseEdition.PRO

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def to_public_dict(self) -> dict[str, object]:
        """Return only UI-safe entitlement facts, never token or customer identifiers."""

        return {
            "state": self.state.value,
            "edition": self.edition.value,
            "features": list(self.features),
            "expires_at": self.expires_at,
            "pro_active": self.pro_active,
        }


class _Verifier(Protocol):
    def verify(
        self,
        token: str | bytes,
        *,
        now: int | None = None,
        trusted_time_floor: int | None = None,
    ) -> VerifiedLicense: ...


class _LicenseStore(Protocol):
    def install(
        self,
        token: str | bytes,
        verifier: _Verifier,
        *,
        now: int | None = None,
    ) -> VerifiedLicense: ...

    def verify_installed(
        self,
        verifier: _Verifier,
        *,
        now: int | None = None,
    ) -> VerifiedLicense: ...

    def remove(self) -> bool: ...


def _free_snapshot(state: EntitlementState = EntitlementState.FREE) -> EntitlementSnapshot:
    return EntitlementSnapshot(
        state=state,
        edition=LicenseEdition.FREE,
        features=tuple(sorted(FREE_FEATURES)),
    )


def _verified_snapshot(verified: VerifiedLicense) -> EntitlementSnapshot:
    signed_features = frozenset(verified.claims.features)
    features = FREE_FEATURES | signed_features
    return EntitlementSnapshot(
        state=EntitlementState.ACTIVE,
        edition=verified.edition,
        features=tuple(sorted(features)),
        expires_at=verified.claims.expires_at,
    )


class EntitlementService:
    """Load and install signed licenses while always retaining a safe Free mode."""

    def __init__(self, verifier: _Verifier, store: _LicenseStore) -> None:
        self._verifier = verifier
        self._store = store

    def status(self, *, now: int | None = None) -> EntitlementSnapshot:
        try:
            verified = self._store.verify_installed(self._verifier, now=now)
        except LicenseNotInstalledError:
            return _free_snapshot()
        except LicenseExpiredError:
            return _free_snapshot(EntitlementState.EXPIRED)
        except LicensingDependencyError:
            return _free_snapshot(EntitlementState.UNAVAILABLE)
        except LicensingError:
            return _free_snapshot(EntitlementState.INVALID)
        return _verified_snapshot(verified)

    def install(self, token: str | bytes, *, now: int | None = None) -> EntitlementSnapshot:
        verified = self._store.install(token, self._verifier, now=now)
        return _verified_snapshot(verified)

    def remove(self) -> bool:
        return self._store.remove()

    def has_feature(self, feature: str, *, now: int | None = None) -> bool:
        return self.status(now=now).has_feature(feature)


def build_default_entitlement_service(
    *,
    store: LicenseStore | None = None,
) -> EntitlementService:
    """Build the commercial verifier from the packaged public key."""

    pem = files("future_assistant").joinpath("assets/license-public.pem").read_bytes()
    return EntitlementService(LicenseVerifier.from_pem(pem), store or LicenseStore())
