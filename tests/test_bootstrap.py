from __future__ import annotations

from future_assistant.bootstrap import apply_product_settings
from future_assistant.config import AssistantConfig
from future_assistant.localization import Language
from future_assistant.product_settings import ProductSettings
from future_assistant.voice import VoiceSettings


def test_saved_product_settings_configure_both_languages() -> None:
    settings = ProductSettings(
        name="Nova",
        language="en",
        wake_phrase="يا نوفا",
        english_wake_phrase="Hey Nova",
        stt_backend="faster-whisper",
        stt_model="small",
        ollama_model="qwen3.5:2b",
        tts_voice="Mark",
    )

    config, voice = apply_product_settings(
        AssistantConfig(audit_path=None),
        VoiceSettings(),
        settings,
        environment={},
    )

    assert config.assistant_name == "Nova"
    assert config.language is Language.EN
    assert config.wake_words == ("يا نوفا", "نوفا", "Hey Nova", "Nova")
    assert config.ollama_model == "qwen3.5:2b"
    assert voice.language is Language.EN
    assert voice.wake_phrase == "يا نوفا"
    assert voice.english_wake_phrase == "Hey Nova"
    assert voice.stt_backend == "faster-whisper"
    assert voice.whisper_model == "small"
    assert voice.tts_voice_name == "Mark"


def test_explicit_environment_values_win_over_saved_settings() -> None:
    environment = {
        "FUTURE_ASSISTANT_NAME": "Environment Name",
        "FUTURE_ASSISTANT_LANGUAGE": "ar",
        "FUTURE_ASSISTANT_WAKE_WORDS": "custom",
        "FUTURE_ASSISTANT_WAKE_PHRASE": "wake ar",
        "FUTURE_ASSISTANT_ENGLISH_WAKE_PHRASE": "wake en",
        "FUTURE_ASSISTANT_STT_BACKEND": "whispercpp",
        "FUTURE_ASSISTANT_WHISPER_MODEL": "base",
        "FUTURE_ASSISTANT_OLLAMA_MODEL": "environment-model",
        "FUTURE_ASSISTANT_TTS_VOICE": "Naayf",
    }
    original_config = AssistantConfig(
        assistant_name="Environment Name",
        language=Language.AR,
        wake_words=("custom",),
        ollama_model="environment-model",
        audit_path=None,
    )
    original_voice = VoiceSettings(
        language=Language.AR,
        wake_phrase="wake ar",
        english_wake_phrase="wake en",
        stt_backend="whispercpp",
        whisper_model="base",
        tts_voice_name="Naayf",
    )

    config, voice = apply_product_settings(
        original_config,
        original_voice,
        ProductSettings(name="Saved Name", language="en"),
        environment=environment,
    )

    assert config == original_config
    assert voice == original_voice
