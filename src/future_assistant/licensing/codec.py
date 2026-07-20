"""Canonical token encoding shared by the verifier and offline issuer tool."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping
from typing import Final

from .errors import InvalidLicenseTokenError
from .models import LicenseClaims

TOKEN_VERSION: Final = 1
TOKEN_ALGORITHM: Final = "Ed25519"
SIGNING_CONTEXT: Final = b"future-assistant-license-v1\x00"
MAX_TOKEN_BYTES: Final = 16_384
_SIGNATURE_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{86}$")
_PAYLOAD_KEYS: Final[frozenset[str]] = frozenset({"version", "alg", "claims"})
_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset({*_PAYLOAD_KEYS, "signature"})


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidLicenseTokenError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    """Serialize a JSON object deterministically for Ed25519 signing."""

    if not isinstance(value, Mapping):
        raise TypeError("canonical JSON input must be a mapping")
    try:
        encoded = json.dumps(
            dict(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise InvalidLicenseTokenError("license data is not canonical JSON") from exc
    return encoded


def unsigned_document(claims: LicenseClaims) -> dict[str, object]:
    return {
        "version": TOKEN_VERSION,
        "alg": TOKEN_ALGORITHM,
        "claims": claims.to_mapping(),
    }


def signing_message(document: Mapping[str, object]) -> bytes:
    """Bind the canonical payload to a product-specific signing context."""

    if set(document) != _PAYLOAD_KEYS:
        raise InvalidLicenseTokenError("unsigned license contains unknown or missing fields")
    version = document["version"]
    algorithm = document["alg"]
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != TOKEN_VERSION
        or not isinstance(algorithm, str)
        or algorithm != TOKEN_ALGORITHM
    ):
        raise InvalidLicenseTokenError("unsupported license version or algorithm")
    return SIGNING_CONTEXT + canonical_json_bytes(document)


def encode_signature(signature: bytes) -> str:
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise InvalidLicenseTokenError("Ed25519 signature must be 64 bytes")
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def decode_signature(encoded: object) -> bytes:
    if not isinstance(encoded, str) or not _SIGNATURE_PATTERN.fullmatch(encoded):
        raise InvalidLicenseTokenError("signature is not canonical base64url")
    try:
        signature = base64.b64decode(encoded + "==", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidLicenseTokenError("signature is not valid base64url") from exc
    if len(signature) != 64:
        raise InvalidLicenseTokenError("Ed25519 signature must be 64 bytes")
    return signature


def encode_token(document: Mapping[str, object], signature: bytes) -> str:
    """Return the compact canonical JSON token stored by the desktop product."""

    signing_message(document)
    envelope = {**dict(document), "signature": encode_signature(signature)}
    return canonical_json_bytes(envelope).decode("utf-8")


def decode_token(token: str | bytes) -> tuple[dict[str, object], bytes, LicenseClaims]:
    """Strictly parse an untrusted token without authenticating it."""

    if isinstance(token, str):
        try:
            raw = token.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise InvalidLicenseTokenError("license token contains invalid Unicode") from exc
    elif isinstance(token, bytes):
        raw = token
    else:
        raise InvalidLicenseTokenError("license token must be text or UTF-8 bytes")
    if not raw or len(raw) > MAX_TOKEN_BYTES:
        raise InvalidLicenseTokenError("license token is empty or too large")

    def reject_nonstandard_number(_value: str) -> object:
        raise InvalidLicenseTokenError("license token contains a non-standard JSON number")

    try:
        envelope = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=reject_nonstandard_number,
        )
    except InvalidLicenseTokenError:
        raise
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as exc:
        raise InvalidLicenseTokenError("license token is not valid UTF-8 JSON") from exc
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
        raise InvalidLicenseTokenError("license envelope contains unknown or missing fields")
    document = {key: envelope[key] for key in ("version", "alg", "claims")}
    signing_message(document)
    claims_value = document["claims"]
    if not isinstance(claims_value, dict):
        raise InvalidLicenseTokenError("claims must be a JSON object")
    claims = LicenseClaims.from_mapping(claims_value)
    return document, decode_signature(envelope["signature"]), claims


def normalize_token(token: str | bytes) -> str:
    """Return a canonical representation while preserving the original signature."""

    document, signature, _claims = decode_token(token)
    return encode_token(document, signature)
