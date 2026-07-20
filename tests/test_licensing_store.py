from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from future_assistant.licensing import (
    InvalidLicenseSignatureError,
    LicenseClaims,
    LicenseClockError,
    LicenseClockRollbackError,
    LicenseEdition,
    LicenseNotInstalledError,
    LicenseStorageError,
    LicenseStore,
    LicenseVerifier,
    default_license_directory,
)
from future_assistant.licensing.codec import encode_token, signing_message, unsigned_document

CUSTOMER_HASH = "b" * 64


def issue(private_key: Ed25519PrivateKey, *, license_id: str = "lic_store_000001") -> str:
    claims = LicenseClaims(
        license_id=license_id,
        edition=LicenseEdition.PRO,
        customer_hash=CUSTOMER_HASH,
        issued_at=1_000,
        expires_at=10_000,
        device_limit=1,
        features=("automation.pro",),
    )
    document = unsigned_document(claims)
    return encode_token(document, private_key.sign(signing_message(document)))


@pytest.fixture
def signer_and_verifier() -> tuple[Ed25519PrivateKey, LicenseVerifier]:
    private_key = Ed25519PrivateKey.generate()
    raw_public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_key, LicenseVerifier.from_raw_public_key(raw_public)


def test_default_directory_uses_local_app_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_license_directory() == tmp_path / "FutureAssistant" / "license"


def test_install_verifies_then_atomically_stores_canonical_token_and_clock(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path / "state")
    spaced_token = json.dumps(json.loads(issue(private_key)), indent=2)

    verified = store.install(spaced_token, verifier, now=1_500)

    assert verified.claims.license_id == "lic_store_000001"
    assert store.load_token() == issue(private_key)
    assert json.loads(store.clock_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "last_seen_at": 1_500,
    }
    assert list(store.directory.glob("*.tmp")) == []


def test_invalid_replacement_never_overwrites_previous_token(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    original = issue(private_key)
    store.install(original, verifier, now=1_500)

    attacker_token = issue(Ed25519PrivateKey.generate(), license_id="lic_store_attacker")
    with pytest.raises(InvalidLicenseSignatureError):
        store.install(attacker_token, verifier, now=1_501)

    assert store.load_token() == original


def test_replace_failure_preserves_previous_token_and_cleans_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    original = issue(private_key)
    store.install(original, verifier, now=1_500)

    original_replace = __import__("os").replace

    def fail_token_replace(source: Path, destination: Path) -> None:
        if Path(destination) == store.token_path:
            raise OSError("simulated replace failure")
        original_replace(source, destination)

    monkeypatch.setattr("future_assistant.licensing.store.os.replace", fail_token_replace)

    with pytest.raises(LicenseStorageError, match="atomically install"):
        store.install(issue(private_key, license_id="lic_store_000002"), verifier, now=1_501)

    assert store.load_token() == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_persisted_clock_floor_detects_rollback(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    store.install(issue(private_key), verifier, now=2_000)

    with pytest.raises(LicenseClockRollbackError):
        store.verify_installed(verifier, now=1_699)

    assert json.loads(store.clock_path.read_text(encoding="utf-8"))["last_seen_at"] == 2_000


def test_verification_advances_but_never_reduces_clock_floor(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    store.install(issue(private_key), verifier, now=2_000)

    store.verify_installed(verifier, now=2_200)
    store.verify_installed(verifier, now=2_000)

    assert json.loads(store.clock_path.read_text(encoding="utf-8"))["last_seen_at"] == 2_200


def test_corrupt_clock_state_fails_closed(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    store.install(issue(private_key), verifier, now=2_000)
    store.clock_path.write_text('{"version":1,"last_seen_at":"yesterday"}', encoding="utf-8")

    with pytest.raises(LicenseClockError, match="invalid"):
        store.verify_installed(verifier, now=2_100)


def test_duplicate_clock_keys_fail_closed(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    store.install(issue(private_key), verifier, now=2_000)
    store.clock_path.write_text(
        '{"version":1,"last_seen_at":2000,"last_seen_at":0}',
        encoding="utf-8",
    )

    with pytest.raises(LicenseClockError, match="duplicate"):
        store.verify_installed(verifier, now=2_100)


def test_remove_retains_clock_history_and_reports_absence(
    tmp_path: Path,
    signer_and_verifier: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = signer_and_verifier
    store = LicenseStore(tmp_path)
    store.install(issue(private_key), verifier, now=2_000)

    assert store.remove() is True
    assert store.remove() is False
    assert store.clock_path.exists()
    with pytest.raises(LicenseNotInstalledError):
        store.load_token()
