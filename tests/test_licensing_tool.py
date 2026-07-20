from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from future_assistant.licensing import LicenseEdition, LicenseVerifier

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ISSUER = PROJECT_ROOT / "tools" / "issue_license.py"


def write_private_key(path: Path, *, password: bytes | None = None) -> Ed25519PrivateKey:
    private_key = Ed25519PrivateKey.generate()
    encryption: serialization.KeySerializationEncryption
    if password is None:
        encryption = serialization.NoEncryption()
    else:
        encryption = serialization.BestAvailableEncryption(password)
    path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            encryption,
        )
    )
    return private_key


def run_tool(
    *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    command_environment = os.environ.copy()
    command_environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    if environment:
        command_environment.update(environment)
    return subprocess.run(
        [sys.executable, str(ISSUER), *arguments],
        cwd=PROJECT_ROOT,
        env=command_environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )


def test_operator_tool_issues_a_verifiable_pro_token(tmp_path: Path) -> None:
    private_path = tmp_path / "operator-private.pem"
    output_path = tmp_path / "issued" / "license.json"
    private_key = write_private_key(private_path)
    customer_hash = hashlib.sha256(b"customer-42").hexdigest()

    completed = run_tool(
        "--private-key",
        str(private_path),
        "--license-id",
        "lic_tool_000001",
        "--edition",
        "pro",
        "--customer-hash",
        customer_hash,
        "--issued-at",
        "2027-01-01T00:00:00Z",
        "--expires-at",
        "2030-01-01T00:00:00Z",
        "--device-limit",
        "3",
        "--feature",
        "voice.premium",
        "--feature",
        "automation.pro",
        "--output",
        str(output_path),
    )

    assert completed.returncode == 0, completed.stderr
    verifier = LicenseVerifier(private_key.public_key())
    verified = verifier.verify(output_path.read_text(encoding="utf-8"), now=1_800_000_000)
    assert verified.edition is LicenseEdition.PRO
    assert verified.claims.device_limit == 3
    assert verified.claims.features == ("automation.pro", "voice.premium")
    assert private_path.read_bytes() not in output_path.read_bytes()


def test_tool_supports_encrypted_private_key_via_environment_only(tmp_path: Path) -> None:
    password = b"correct horse battery staple"
    private_path = tmp_path / "encrypted.pem"
    output_path = tmp_path / "license.json"
    write_private_key(private_path, password=password)

    completed = run_tool(
        "--private-key",
        str(private_path),
        "--private-key-password-env",
        "LICENSE_KEY_PASSWORD",
        "--license-id",
        "lic_tool_000002",
        "--edition",
        "free",
        "--customer-hash",
        "c" * 64,
        "--issued-at",
        "1800000000",
        "--expires-at",
        "1900000000",
        "--output",
        str(output_path),
        environment={"LICENSE_KEY_PASSWORD": password.decode("ascii")},
    )

    assert completed.returncode == 0, completed.stderr
    assert output_path.exists()


def test_tool_has_no_default_private_key_and_creates_no_output(tmp_path: Path) -> None:
    output_path = tmp_path / "license.json"

    completed = run_tool(
        "--license-id",
        "lic_tool_000003",
        "--edition",
        "free",
        "--customer-hash",
        "d" * 64,
        "--expires-at",
        "1900000000",
        "--output",
        str(output_path),
    )

    assert completed.returncode == 2
    assert "--private-key" in completed.stderr
    assert not output_path.exists()


def test_tool_refuses_to_overwrite_private_key_with_output(tmp_path: Path) -> None:
    private_path = tmp_path / "private.pem"
    write_private_key(private_path)
    original_bytes = private_path.read_bytes()

    completed = run_tool(
        "--private-key",
        str(private_path),
        "--license-id",
        "lic_tool_000004",
        "--edition",
        "pro",
        "--customer-hash",
        "e" * 64,
        "--issued-at",
        "1800000000",
        "--expires-at",
        "1900000000",
        "--output",
        str(private_path),
        "--force",
    )

    assert completed.returncode == 2
    assert "must never be the private-key path" in completed.stderr
    assert private_path.read_bytes() == original_bytes
