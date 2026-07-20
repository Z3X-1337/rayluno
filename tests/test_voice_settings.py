from __future__ import annotations

from pathlib import Path

import pytest

from future_assistant.localization import Language
from future_assistant.voice import (
    CompositeWakeWordDetector,
    VoiceConfigurationError,
    VoiceSettings,
    build_voice_loop,
)


def test_bilingual_voice_settings_build_two_wake_detectors(tmp_path: Path) -> None:
    arabic = tmp_path / "ar"
    english = tmp_path / "en"
    arabic.mkdir()
    english.mkdir()
    settings = VoiceSettings(
        vosk_model_path=arabic,
        vosk_english_model_path=english,
        language=Language.AUTO,
        tts_enabled=False,
    )

    loop = build_voice_loop(settings, on_command=lambda text: text)

    assert isinstance(loop.wake_detector, CompositeWakeWordDetector)
    assert len(loop.wake_detector.detectors) == 2
    assert loop.transcriber.language is None


def test_english_only_voice_does_not_require_arabic_model(tmp_path: Path) -> None:
    english = tmp_path / "en"
    english.mkdir()
    settings = VoiceSettings(
        vosk_english_model_path=english,
        language=Language.EN,
        tts_enabled=False,
    )

    loop = build_voice_loop(settings, on_command=lambda text: text)

    assert not isinstance(loop.wake_detector, CompositeWakeWordDetector)
    assert loop.wake_detector.wake_phrase == "hey rayluno"


def test_auto_language_requires_both_wake_models(tmp_path: Path) -> None:
    arabic = tmp_path / "ar"
    arabic.mkdir()
    settings = VoiceSettings(vosk_model_path=arabic, language=Language.AUTO)

    with pytest.raises(VoiceConfigurationError, match="الإنجليزية"):
        settings.validate()


def test_voice_settings_from_env_defaults_to_auto_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FUTURE_ASSISTANT_WHISPER_LANGUAGE", raising=False)
    monkeypatch.setenv("FUTURE_ASSISTANT_LANGUAGE", "en-US")

    settings = VoiceSettings.from_env()

    assert settings.language is Language.EN
    assert settings.whisper_language is None


def test_voice_settings_discovers_installed_user_models(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_root = tmp_path / "FutureAssistant" / "models"
    arabic = model_root / "vosk-model-ar-mgb2-0.4"
    english = model_root / "vosk-model-small-en-us-0.15"
    arabic.mkdir(parents=True)
    english.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("FUTURE_ASSISTANT_VOSK_MODEL_PATH", raising=False)
    monkeypatch.delenv("FUTURE_ASSISTANT_VOSK_ENGLISH_MODEL_PATH", raising=False)

    settings = VoiceSettings.from_env()

    assert settings.vosk_model_path == arabic
    assert settings.vosk_english_model_path == english
