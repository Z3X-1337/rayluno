from __future__ import annotations

import json
from pathlib import Path

import pytest

from future_assistant.activation import (
    PRODUCTION_ACTIVATION_ENDPOINT,
    ActivationClient,
    ActivationConfig,
    ActivationConfigurationError,
    ActivationRejectedError,
    ActivationStateStore,
    ActivationStorageError,
    ActivationTransportError,
    InstallationIdentityStore,
    StoredActivation,
)

INSTALLATION_ID = "4f30eb03-f1db-4b4c-8eb5-29c98240f706"
REFRESH_TOKEN = "a" * 43
INSTANCE_ID = "instance-12345678"
LICENSE_TOKEN = '{"version":1,"license":"signed-value"}'


class FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, object], float]] = []

    def post_json(
        self,
        url: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.requests.append((url, dict(payload), timeout_seconds))
        return dict(self.response)


class FakeProtector:
    def protect(self, plaintext: bytes) -> bytes:
        return b"protected:" + plaintext[::-1]

    def unprotect(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(b"protected:"):
            raise ActivationStorageError("invalid")
        return ciphertext.removeprefix(b"protected:")[::-1]


def success_response() -> dict[str, object]:
    return {
        "ok": True,
        "license_token": LICENSE_TOKEN,
        "refresh_token": REFRESH_TOKEN,
        "instance_id": INSTANCE_ID,
    }


def test_config_requires_plain_https_endpoint() -> None:
    assert ActivationConfig(endpoint="https://activate.example.com/v1").configured
    for value in (
        "http://activate.example.com/v1",
        "https://user@activate.example.com/v1",
        "https://activate.example.com:8443/v1",
        "https://activate.example.com/v1?token=secret",
    ):
        with pytest.raises(ActivationConfigurationError):
            ActivationConfig(endpoint=value)


def test_config_pins_production_and_requires_explicit_source_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FUTURE_ASSISTANT_ACTIVATION_URL", raising=False)
    monkeypatch.delenv("FUTURE_ASSISTANT_ALLOW_ACTIVATION_OVERRIDE", raising=False)

    assert ActivationConfig.from_env().endpoint == PRODUCTION_ACTIVATION_ENDPOINT

    monkeypatch.setenv(
        "FUTURE_ASSISTANT_ACTIVATION_URL",
        "https://staging.example.test/api/license/activate",
    )
    assert ActivationConfig.from_env().endpoint == PRODUCTION_ACTIVATION_ENDPOINT

    monkeypatch.setenv("FUTURE_ASSISTANT_ALLOW_ACTIVATION_OVERRIDE", "1")
    assert (
        ActivationConfig.from_env().endpoint == "https://staging.example.test/api/license/activate"
    )

    monkeypatch.setattr("future_assistant.activation.sys.frozen", True, raising=False)
    assert ActivationConfig.from_env().endpoint == PRODUCTION_ACTIVATION_ENDPOINT


def test_client_exchanges_purchase_key_without_logging_or_mutating_it() -> None:
    transport = FakeTransport(success_response())
    client = ActivationClient(
        ActivationConfig(endpoint="https://activate.example.com/v1"),
        transport=transport,
    )

    grant = client.activate(
        "38b1460a-5104-4067-a91d-77b872934d51",
        INSTALLATION_ID,
        app_version="0.1.0",
    )

    assert grant.refresh_token == REFRESH_TOKEN
    _, payload, timeout = transport.requests[0]
    assert payload == {
        "protocol": 1,
        "action": "activate",
        "purchase_key": "38b1460a-5104-4067-a91d-77b872934d51",
        "installation_id": INSTALLATION_ID,
        "app_version": "0.1.0",
    }
    assert timeout == 15.0


def test_client_refreshes_with_opaque_token() -> None:
    transport = FakeTransport(success_response())
    client = ActivationClient(
        ActivationConfig(endpoint="https://activate.example.com/v1"),
        transport=transport,
    )

    client.refresh(REFRESH_TOKEN, INSTALLATION_ID, app_version="0.1.0")

    assert transport.requests[0][1]["action"] == "refresh"
    assert "purchase_key" not in transport.requests[0][1]


def test_client_deactivates_with_opaque_refresh_token() -> None:
    transport = FakeTransport({"ok": True, "deactivated": True})
    client = ActivationClient(
        ActivationConfig(endpoint="https://activate.example.com/v1"),
        transport=transport,
    )

    client.deactivate(REFRESH_TOKEN, INSTALLATION_ID, app_version="0.1.0")

    assert transport.requests[0][1] == {
        "protocol": 1,
        "action": "deactivate",
        "refresh_token": REFRESH_TOKEN,
        "installation_id": INSTALLATION_ID,
        "app_version": "0.1.0",
    }


def test_client_maps_structured_rejection_without_provider_detail() -> None:
    client = ActivationClient(
        ActivationConfig(endpoint="https://activate.example.com/v1"),
        transport=FakeTransport({"ok": False, "code": "license_expired"}),
    )

    with pytest.raises(ActivationRejectedError, match="license_expired"):
        client.activate("38b1460a-5104-4067-a91d-77b872934d51", INSTALLATION_ID, app_version="1")


def test_client_rejects_unknown_success_fields() -> None:
    response = success_response()
    response["customer_email"] = "should-not-cross-boundary@example.com"
    client = ActivationClient(
        ActivationConfig(endpoint="https://activate.example.com/v1"),
        transport=FakeTransport(response),
    )

    with pytest.raises(ActivationTransportError):
        client.activate("38b1460a-5104-4067-a91d-77b872934d51", INSTALLATION_ID, app_version="1")


def test_installation_identity_is_random_and_stable(tmp_path: Path) -> None:
    store = InstallationIdentityStore(tmp_path)

    first = store.load_or_create()
    second = store.load_or_create()

    assert first == second
    assert json.loads(store.path.read_text(encoding="utf-8"))["installation_id"] == first


def test_protected_activation_state_round_trip_and_removal(tmp_path: Path) -> None:
    store = ActivationStateStore(tmp_path, protector=FakeProtector())
    state = StoredActivation(
        installation_id=INSTALLATION_ID,
        refresh_token=REFRESH_TOKEN,
        instance_id=INSTANCE_ID,
    )

    store.save(state)

    assert store.load() == state
    assert REFRESH_TOKEN.encode() not in store.path.read_bytes()
    assert store.remove() is True
    assert store.remove() is False


def test_protected_activation_state_fails_closed_on_tampering(tmp_path: Path) -> None:
    store = ActivationStateStore(tmp_path, protector=FakeProtector())
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_bytes(b"dGFtcGVyZWQ=\n")

    with pytest.raises(ActivationStorageError):
        store.load()
