#!/usr/bin/env python3
"""Sign one release manifest with an explicitly supplied Ed25519 private key.

The operator-only private key is never generated, searched for, or bundled by
this tool. Keep it outside the repository and outside published build output.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import suppress
from pathlib import Path

try:
    from future_assistant.updates import (
        ReleaseManifest,
        UpdateError,
        build_signed_envelope,
        serialize_signed_envelope,
    )
    from future_assistant.updates.signing import strict_json_object
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from future_assistant.updates import (
        ReleaseManifest,
        UpdateError,
        build_signed_envelope,
        serialize_signed_envelope,
    )
    from future_assistant.updates.signing import strict_json_object

MAX_PRIVATE_KEY_BYTES = 65_536
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_private_key(path: Path, password_environment: str | None) -> object:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise RuntimeError("install the rayluno-assistant update crypto dependency") from exc

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
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(raw_temporary_path)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an Ed25519-signed update manifest")
    parser.add_argument("manifest", type=Path, help="unsigned release manifest JSON")
    parser.add_argument("--output", type=Path, required=True, help="signed envelope JSON")
    parser.add_argument("--private-key", type=Path, required=True, help="external Ed25519 PEM")
    parser.add_argument("--key-id", required=True, help="trusted public-key identifier")
    parser.add_argument(
        "--password-env",
        help="name of an environment variable containing the PEM password",
    )
    parser.add_argument("--force", action="store_true", help="replace an existing output")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        output = arguments.output.resolve()
        private_key_path = arguments.private_key.resolve()
        if output == private_key_path:
            raise RuntimeError("output must never overwrite the private key")
        try:
            private_key_path.relative_to(PROJECT_ROOT)
        except ValueError:
            pass
        else:
            raise RuntimeError("private key must be stored outside the project directory")
        manifest_bytes = arguments.manifest.read_bytes()
        manifest = ReleaseManifest.from_mapping(strict_json_object(manifest_bytes))
        private_key = _load_private_key(private_key_path, arguments.password_env)
        envelope = build_signed_envelope(
            manifest,
            key_id=arguments.key_id,
            private_key=private_key,
        )
        _atomic_output(
            output,
            serialize_signed_envelope(envelope, pretty=True),
            force=arguments.force,
        )
    except (OSError, RuntimeError, TypeError, ValueError, UpdateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"signed update manifest written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
