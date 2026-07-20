from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from future_assistant.licensing import (
    InvalidLicenseSignatureError,
    InvalidLicenseTokenError,
    InvalidPublicKeyError,
    LicenseClaims,
    LicenseClockRollbackError,
    LicenseEdition,
    LicenseExpiredError,
    LicenseNotYetValidError,
    LicenseTimePolicy,
    LicenseVerifier,
)
from future_assistant.licensing.codec import (
    canonical_json_bytes,
    encode_token,
    signing_message,
    unsigned_document,
)

ISSUED_AT = 1_800_000_000
EXPIRES_AT = 1_900_000_000
CUSTOMER_HASH = "a" * 64


def make_claims(**changes: object) -> LicenseClaims:
    values: dict[str, object] = {
        "license_id": "lic_2026_000001",
        "edition": LicenseEdition.PRO,
        "customer_hash": CUSTOMER_HASH,
        "issued_at": ISSUED_AT,
        "expires_at": EXPIRES_AT,
        "device_limit": 2,
        "features": ("automation.pro", "voice.premium"),
    }
    values.update(changes)
    return LicenseClaims(**values)  # type: ignore[arg-type]


def issue(private_key: Ed25519PrivateKey, claims: LicenseClaims | None = None) -> str:
    document = unsigned_document(claims or make_claims())
    return encode_token(document, private_key.sign(signing_message(document)))


@pytest.fixture
def key_pair() -> tuple[Ed25519PrivateKey, LicenseVerifier]:
    private_key = Ed25519PrivateKey.generate()
    raw_public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_key, LicenseVerifier.from_raw_public_key(raw_public)


def test_canonical_json_is_stable_compact_and_unicode_safe() -> None:
    first = {"z": "العربية", "a": {"second": 2, "first": 1}}
    second = {"a": {"first": 1, "second": 2}, "z": "العربية"}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_bytes(first).decode("utf-8") == (
        '{"a":{"first":1,"second":2},"z":"العربية"}'
    )


@pytest.mark.parametrize("edition", [LicenseEdition.FREE, LicenseEdition.PRO])
def test_valid_signature_returns_exact_free_or_pro_entitlements(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
    edition: LicenseEdition,
) -> None:
    private_key, verifier = key_pair

    verified = verifier.verify(
        issue(private_key, make_claims(edition=edition)),
        now=ISSUED_AT + 10,
    )

    assert verified.edition is edition
    assert verified.claims.device_limit == 2
    assert verified.has_feature("voice.premium") is True
    assert verified.has_feature("unknown") is False
    assert verified.verified_at == ISSUED_AT + 10


def test_pem_loader_accepts_ed25519_and_rejects_other_key_types() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    verifier = LicenseVerifier.from_pem(public_pem)
    assert verifier.verify(issue(private_key), now=ISSUED_AT).claims.license_id == (
        "lic_2026_000001"
    )

    from cryptography.hazmat.primitives.asymmetric import ec

    ec_pem = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    with pytest.raises(InvalidPublicKeyError, match="Ed25519"):
        LicenseVerifier.from_pem(ec_pem)


def test_claim_tampering_fails_signature_verification(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = key_pair
    document = json.loads(issue(private_key))
    document["claims"]["edition"] = "free"
    tampered = json.dumps(document, sort_keys=True, separators=(",", ":"))

    with pytest.raises(InvalidLicenseSignatureError):
        verifier.verify(tampered, now=ISSUED_AT)


def test_signature_from_a_different_key_is_rejected(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    _private_key, verifier = key_pair

    with pytest.raises(InvalidLicenseSignatureError):
        verifier.verify(issue(Ed25519PrivateKey.generate()), now=ISSUED_AT)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda token: token.replace(
            '"alg":"Ed25519"',
            '"alg":"Ed25519","alg":"Ed25519"',
        ),
        lambda token: token.replace('"alg":"Ed25519"', '"alg":"HS256"'),
        lambda token: token.replace('"version":1', '"version":true'),
        lambda token: token.replace('"signature":"', '"extra":true,"signature":"'),
        lambda token: token.replace('"signature":"', '"signature":"!'),
    ],
)
def test_malformed_or_ambiguous_envelopes_are_rejected(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
    mutation: Callable[[str], str],
) -> None:
    private_key, verifier = key_pair
    malformed = mutation(issue(private_key))

    with pytest.raises(InvalidLicenseTokenError):
        verifier.verify(malformed, now=ISSUED_AT)


def test_unknown_claim_is_rejected_before_signature_check(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = key_pair
    document = json.loads(issue(private_key))
    document["claims"]["admin"] = True

    with pytest.raises(InvalidLicenseTokenError, match="unknown or missing"):
        verifier.verify(json.dumps(document), now=ISSUED_AT)


def test_expiry_is_strict_after_the_signed_second(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, verifier = key_pair
    token = issue(private_key)

    assert verifier.verify(token, now=EXPIRES_AT).claims.expires_at == EXPIRES_AT
    with pytest.raises(LicenseExpiredError):
        verifier.verify(token, now=EXPIRES_AT + 1)


def test_future_issue_and_clock_rollback_are_rejected(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    private_key, _verifier = key_pair
    verifier = LicenseVerifier(
        private_key.public_key(),
        policy=LicenseTimePolicy(
            maximum_future_issue_seconds=10,
            maximum_rollback_seconds=5,
        ),
    )
    token = issue(private_key)

    with pytest.raises(LicenseNotYetValidError):
        verifier.verify(token, now=ISSUED_AT - 11)
    with pytest.raises(LicenseClockRollbackError):
        verifier.verify(token, now=ISSUED_AT, trusted_time_floor=ISSUED_AT + 6)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"customer_hash": "ABC"}, "customer_hash"),
        ({"expires_at": ISSUED_AT}, "later"),
        ({"device_limit": 0}, "device_limit"),
        ({"features": ("z.feature", "a.feature")}, "unique and sorted"),
        ({"features": ("valid", "valid")}, "unique and sorted"),
        ({"features": ("Bad Feature",)}, "feature identifier"),
    ],
)
def test_claim_schema_rejects_unsafe_values(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(InvalidLicenseTokenError, match=message):
        make_claims(**changes)


def test_token_size_limit_is_enforced(
    key_pair: tuple[Ed25519PrivateKey, LicenseVerifier],
) -> None:
    _private_key, verifier = key_pair

    with pytest.raises(InvalidLicenseTokenError, match="too large"):
        verifier.verify("x" * 20_000, now=ISSUED_AT)
