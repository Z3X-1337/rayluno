from __future__ import annotations

import json
from pathlib import Path

import pytest

from future_assistant.product_settings import (
    ALLOWED_SETTING_KEYS,
    SCHEMA_VERSION,
    ProductSettings,
    ProductSettingsStore,
    SettingsValidationError,
    default_settings_path,
)


def test_default_path_uses_local_app_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_settings_path() == tmp_path / "FutureAssistant" / "settings.json"


def test_defaults_are_local_private_and_telemetry_is_opt_in() -> None:
    settings = ProductSettings()

    assert settings.name == "رايلونو"
    assert settings.language == "auto"
    assert settings.wake_phrase == "يا رايلونو"
    assert settings.english_wake_phrase == "Hey Rayluno"
    assert settings.telemetry_opt_in is False
    assert set(settings.to_dict()) == ALLOWED_SETTING_KEYS
    assert not any(
        "secret" in key or "token" in key or "password" in key or "api_key" in key
        for key in settings.to_dict()
    )


def test_save_and_load_round_trip_with_versioned_schema(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "settings.json"
    store = ProductSettingsStore(path)
    settings = ProductSettings(
        name="  JARVIS  ",
        language="EN",
        wake_phrase="  Hey Jarvis  ",
        english_wake_phrase="Computer",
        stt_backend="FASTER-WHISPER",
        stt_model="small",
        ollama_model="qwen3.5:9b",
        tts_voice="Arabic Voice",
        telemetry_opt_in=True,
    )

    assert store.save(settings) == path
    assert store.load() == ProductSettings(
        name="JARVIS",
        language="en",
        wake_phrase="Hey Jarvis",
        english_wake_phrase="Computer",
        stt_backend="faster-whisper",
        stt_model="small",
        ollama_model="qwen3.5:9b",
        tts_voice="Arabic Voice",
        telemetry_opt_in=True,
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document == {
        "schema_version": SCHEMA_VERSION,
        "settings": settings.to_dict(),
    }


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        '{"schema_version": 999, "settings": {}}',
        '{"schema_version": 1, "settings": {"api_key": "do-not-keep"}}',
        '{"schema_version": 1, "settings": {"telemetry_opt_in": "yes"}}',
    ],
)
def test_load_tolerates_corrupt_or_unsafe_documents(
    tmp_path: Path,
    contents: str,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(contents, encoding="utf-8")

    assert ProductSettingsStore(path).load() == ProductSettings()


def test_unknown_keys_are_rejected_in_untrusted_mapping() -> None:
    with pytest.raises(SettingsValidationError, match="unknown setting keys"):
        ProductSettings.from_mapping({"name": "Jarvis", "access_token": "secret"})


def test_version_one_settings_are_migrated_to_bilingual_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    legacy = ProductSettings().to_dict()
    legacy.pop("language")
    legacy.pop("english_wake_phrase")
    path.write_text(
        json.dumps({"schema_version": 1, "settings": legacy}, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = ProductSettingsStore(path).load()

    assert loaded.language == "auto"
    assert loaded.english_wake_phrase == "Hey Rayluno"


def test_beta_brand_defaults_migrate_without_overwriting_custom_values(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    legacy = ProductSettings(
        name="المساعد",
        wake_phrase="يا مساعد",
        english_wake_phrase="hey assistant",
    ).to_dict()
    path.write_text(
        json.dumps({"schema_version": 2, "settings": legacy}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert ProductSettingsStore(path).load() == ProductSettings()

    legacy.update(
        {
            "name": "اسمي الخاص",
            "wake_phrase": "يا حاسوبي",
            "english_wake_phrase": "Computer",
        }
    )
    path.write_text(
        json.dumps({"schema_version": 2, "settings": legacy}, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded = ProductSettingsStore(path).load()
    assert loaded.name == "اسمي الخاص"
    assert loaded.wake_phrase == "يا حاسوبي"
    assert loaded.english_wake_phrase == "Computer"


@pytest.mark.parametrize("language", ["fr", "", "automatic-ish"])
def test_rejects_unsupported_language(language: str) -> None:
    with pytest.raises(SettingsValidationError, match="language must be one of"):
        ProductSettings(language=language)


def test_export_contains_only_validated_allowlisted_values(tmp_path: Path) -> None:
    source = tmp_path / "settings.json"
    destination = tmp_path / "exports" / "jarvis-settings.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "settings": {"name": "Jarvis", "password": "never export me"},
            }
        ),
        encoding="utf-8",
    )

    ProductSettingsStore(source).export(destination)

    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert exported["settings"] == ProductSettings().to_dict()
    assert "never export me" not in destination.read_text(encoding="utf-8")


def test_save_is_atomic_and_preserves_previous_file_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text("original", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("future_assistant.product_settings.os.replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        ProductSettingsStore(path).save(ProductSettings(name="New name"))

    assert path.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob("*.tmp")) == []


def test_delete_reports_if_settings_existed(tmp_path: Path) -> None:
    store = ProductSettingsStore(tmp_path / "settings.json")
    store.save(ProductSettings())

    assert store.delete() is True
    assert store.delete() is False
    assert store.load() == ProductSettings()
