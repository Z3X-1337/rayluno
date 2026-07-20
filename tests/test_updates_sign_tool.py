from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from future_assistant.updates import Ed25519ManifestVerifier, ManifestPolicy


def test_signing_tool_requires_external_key_and_produces_verifiable_envelope(
    tmp_path: Path,
) -> None:
    content = b"release installer"
    private_key = Ed25519PrivateKey.generate()
    private_path = tmp_path / "operator-key.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "future-assistant",
                "channel": "stable",
                "version": "1.1.0",
                "url": "https://updates.example.test/setup.exe",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "min_os": "10.0.19041",
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "signed.json"
    project_root = Path(__file__).resolve().parents[1]

    command = [
        sys.executable,
        str(project_root / "tools" / "sign_update_manifest.py"),
        str(manifest_path),
        "--output",
        str(output_path),
        "--private-key",
        str(private_path),
        "--key-id",
        "release-test",
    ]
    completed = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    verified = Ed25519ManifestVerifier({"release-test": public}).verify(
        output_path.read_bytes(),
        ManifestPolicy(
            expected_product="future-assistant",
            channel="stable",
            current_version="1.0.0",
            os_version="10.0.22631",
        ),
    )
    assert verified.release.version == "1.1.0"
    assert private_path.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
    original_envelope = output_path.read_bytes()

    second_run = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert second_run.returncode == 2
    assert "--force" in second_run.stderr
    assert output_path.read_bytes() == original_envelope
