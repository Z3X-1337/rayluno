from __future__ import annotations

from dataclasses import dataclass

import pytest

from future_assistant.entitlements import (
    FREE_FEATURES,
    EntitlementService,
    EntitlementState,
)
from future_assistant.licensing import (
    InvalidLicenseSignatureError,
    LicenseClaims,
    LicenseEdition,
    LicenseExpiredError,
    LicenseNotInstalledError,
    VerifiedLicense,
)


def _verified(edition: LicenseEdition = LicenseEdition.PRO) -> VerifiedLicense:
    return VerifiedLicense(
        LicenseClaims(
            license_id="license_0001",
            edition=edition,
            customer_hash="a" * 64,
            issued_at=100,
            expires_at=10_000,
            device_limit=2,
            features=("ai.local", "voice.local"),
        ),
        verified_at=500,
    )


class FakeVerifier:
    def verify(self, token, *, now=None, trusted_time_floor=None):  # noqa: ANN001, ANN201
        return _verified()


@dataclass
class FakeStore:
    result: VerifiedLicense | Exception
    removed: bool = False

    def verify_installed(self, verifier, *, now=None):  # noqa: ANN001, ANN201
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def install(self, token, verifier, *, now=None):  # noqa: ANN001, ANN201
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    def remove(self) -> bool:
        self.removed = True
        return True


def test_missing_license_is_useful_free_mode() -> None:
    service = EntitlementService(FakeVerifier(), FakeStore(LicenseNotInstalledError()))

    status = service.status()

    assert status.state is EntitlementState.FREE
    assert status.edition is LicenseEdition.FREE
    assert set(status.features) == FREE_FEATURES
    assert not status.has_feature("voice.local")
    assert not status.pro_active


def test_valid_pro_license_adds_only_signed_features() -> None:
    service = EntitlementService(FakeVerifier(), FakeStore(_verified()))

    status = service.status()

    assert status.state is EntitlementState.ACTIVE
    assert status.pro_active
    assert status.has_feature("commands.basic")
    assert status.has_feature("ai.local")
    assert not status.has_feature("automation.pro")
    public = status.to_public_dict()
    assert set(public) == {"state", "edition", "features", "expires_at", "pro_active"}
    assert "license_id" not in repr(public)
    assert "customer" not in repr(public)


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (LicenseExpiredError(), EntitlementState.EXPIRED),
        (InvalidLicenseSignatureError(), EntitlementState.INVALID),
    ],
)
def test_invalid_or_expired_license_fails_closed_to_free(
    error: Exception,
    state: EntitlementState,
) -> None:
    service = EntitlementService(FakeVerifier(), FakeStore(error))

    status = service.status()

    assert status.state is state
    assert status.edition is LicenseEdition.FREE
    assert not status.has_feature("ai.local")


def test_install_and_remove_delegate_to_verified_store() -> None:
    store = FakeStore(_verified())
    service = EntitlementService(FakeVerifier(), store)

    installed = service.install("signed-token")

    assert installed.pro_active
    assert service.remove() is True
    assert store.removed is True
