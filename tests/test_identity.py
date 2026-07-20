from __future__ import annotations

from pathlib import Path

import pytest

from future_assistant import activation
from future_assistant.config import AssistantConfig
from future_assistant.identity import (
    COMPATIBILITY_DATA_DIRECTORY,
    COMPATIBILITY_DISTRIBUTION_MARKER,
    COMPATIBILITY_UPDATE_PRODUCT,
    DEFAULT_WAKE_WORDS,
    PRODUCT_NAME,
    PRODUCT_NAME_AR,
    environment_value,
)
from future_assistant.licensing.codec import SIGNING_CONTEXT
from future_assistant.product_settings import default_settings_path
from future_assistant.product_updates import DISTRIBUTION_MARKER, UPDATE_PRODUCT


def test_customer_brand_and_wake_words_are_rayluno() -> None:
    assert PRODUCT_NAME == "Rayluno"
    assert PRODUCT_NAME_AR == "رايلونو"
    assert DEFAULT_WAKE_WORDS == ("يا رايلونو", "رايلونو", "Hey Rayluno", "Rayluno")
    assert AssistantConfig().wake_words == DEFAULT_WAKE_WORDS


def test_new_environment_name_wins_and_legacy_alias_still_works() -> None:
    assert environment_value("NAME", environment={"FUTURE_ASSISTANT_NAME": "Legacy"}) == "Legacy"
    assert (
        environment_value(
            "NAME",
            environment={
                "FUTURE_ASSISTANT_NAME": "Legacy",
                "RAYLUNO_NAME": "Preferred",
            },
        )
        == "Preferred"
    )


def test_assistant_config_accepts_new_environment_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FUTURE_ASSISTANT_NAME", "Legacy")
    monkeypatch.setenv("RAYLUNO_NAME", "Ray")
    monkeypatch.setenv("RAYLUNO_WAKE_WORDS", "Hey Rayluno,Rayluno")

    config = AssistantConfig.from_env()

    assert config.assistant_name == "Ray"
    assert config.wake_words == ("Hey Rayluno", "Rayluno")


def test_legacy_protocol_and_data_identifiers_remain_stable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert COMPATIBILITY_DATA_DIRECTORY == "FutureAssistant"
    assert default_settings_path() == tmp_path / "FutureAssistant" / "settings.json"
    assert SIGNING_CONTEXT == b"future-assistant-license-v1\x00"
    assert activation._DPAPI_ENTROPY == b"future-assistant-activation-state-v1"  # noqa: SLF001
    assert activation.PRODUCTION_ACTIVATION_ENDPOINT.endswith("/api/license/activate")
    assert UPDATE_PRODUCT == COMPATIBILITY_UPDATE_PRODUCT == "future-assistant"
    assert DISTRIBUTION_MARKER == COMPATIBILITY_DISTRIBUTION_MARKER
