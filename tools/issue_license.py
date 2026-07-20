#!/usr/bin/env python3
"""Issue one Ed25519-signed license using an explicitly supplied private key.

This operator-only tool is outside ``src`` so it is not included in the product
package. It deliberately does not generate, discover, or default a private key.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from future_assistant.licensing.codec import (
    encode_token,
    signing_message,
    unsigned_document,
)
from future_assistant.licensing.models import LicenseClaims, LicenseEdition

MAX_PRIVATE_KEY_BYTES = 65_536


def _timestamp(value: str) -> int:
    if value.isdecimal():
        return int(value)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "use Unix seconds or an ISO-8601 timestamp such as 2027-01-01T00:00:00Z"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("ISO-8601 timestamps must include a UTC offset")
    return int(parsed.astimezone(UTC).timestamp())


def _load_private_key(path: Path, password_environment: str | None) -> object:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("install the rayluno-assistant[licensing] dependency") from exc

    try:
        pem = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"could not read private key: {path}") from exc
    if not pem or len(pem) > MAX_PRIVATE_KEY_BYTES:
        raise RuntimeError("private-key PEM is empty or too large")
    password: bytes | None = None
    if password_environment is not None:
        raw_password = os.environ.get(password_environment)
        if raw_password is None:
            raise RuntimeError(
                f"private-key password environment variable is not set: {password_environment}"
            )
        password = raw_password.encode("utf-8")
    try:
        private_key = serialization.load_pem_private_key(pem, password=password)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("could not decrypt or parse the private-key PEM") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise RuntimeError("private key must use Ed25519")
    return private_key


def _atomic_output(path: Path, contents: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise RuntimeError("output already exists; pass --force to replace it")
    temporary_path: Path | None = None
    descriptor = -1
    try:
        descriptor, raw_temporary_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(raw_temporary_path)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        with suppress(OSError):
            temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                temporary_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Issue a signed Rayluno license (operator use only)."
    )
    parser.add_argument(
        "--private-key",
        type=Path,
        required=True,
        help="explicit path to an existing Ed25519 private-key PEM",
    )
    parser.add_argument(
        "--private-key-password-env",
        metavar="NAME",
        help="read an encrypted PEM password from this environment variable",
    )
    parser.add_argument("--license-id", required=True)
    parser.add_argument(
        "--edition", required=True, choices=[edition.value for edition in LicenseEdition]
    )
    parser.add_argument(
        "--customer-hash",
        required=True,
        help="lowercase SHA-256 of a stable non-PII customer reference",
    )
    parser.add_argument(
        "--issued-at",
        type=_timestamp,
        help="Unix seconds or timezone-aware ISO-8601; defaults to current UTC time",
    )
    parser.add_argument(
        "--expires-at",
        type=_timestamp,
        required=True,
        help="Unix seconds or timezone-aware ISO-8601",
    )
    parser.add_argument("--device-limit", type=int, default=1)
    parser.add_argument(
        "--feature",
        action="append",
        default=[],
        help="signed feature identifier; repeat for multiple features",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force", action="store_true", help="atomically replace an existing output"
    )
    return parser


def run(arguments: argparse.Namespace) -> Path:
    private_key_path = arguments.private_key.expanduser().resolve()
    output_path = arguments.output.expanduser().resolve()
    if private_key_path == output_path:
        raise RuntimeError("output path must never be the private-key path")
    issued_at = int(time.time()) if arguments.issued_at is None else arguments.issued_at
    claims = LicenseClaims(
        license_id=arguments.license_id,
        edition=LicenseEdition(arguments.edition),
        customer_hash=arguments.customer_hash,
        issued_at=issued_at,
        expires_at=arguments.expires_at,
        device_limit=arguments.device_limit,
        features=tuple(sorted(set(arguments.feature))),
    )
    private_key = _load_private_key(private_key_path, arguments.private_key_password_env)
    document = unsigned_document(claims)
    signature = private_key.sign(signing_message(document))
    token = encode_token(document, signature).encode("utf-8") + b"\n"
    _atomic_output(output_path, token, force=arguments.force)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        output = run(arguments)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"License written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
