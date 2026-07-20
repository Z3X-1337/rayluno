"""Resolve persisted product preferences without overriding explicit environment values."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace

from .config import AssistantConfig
from .identity import environment_has
from .localization import normalize_language
from .product_settings import ProductSettings
from .voice import VoiceSettings


def apply_product_settings(
    config: AssistantConfig,
    voice: VoiceSettings,
    settings: ProductSettings,
    *,
    environment: Mapping[str, str] | None = None,
) -> tuple[AssistantConfig, VoiceSettings]:
    """Merge settings into startup configuration; environment variables win."""

    environment = os.environ if environment is None else environment
    config_updates: dict[str, object] = {}
    voice_updates: dict[str, object] = {}

    if not environment_has("NAME", environment):
        config_updates["assistant_name"] = settings.name
    if not environment_has("LANGUAGE", environment):
        language = normalize_language(settings.language)
        config_updates["language"] = language
        voice_updates["language"] = language
    if not environment_has("WAKE_WORDS", environment):
        wake_words = (
            settings.wake_phrase,
            settings.wake_phrase.rsplit(maxsplit=1)[-1],
            settings.english_wake_phrase,
            settings.english_wake_phrase.rsplit(maxsplit=1)[-1],
        )
        config_updates["wake_words"] = tuple(dict.fromkeys(wake_words))
    if not environment_has("OLLAMA_MODEL", environment):
        config_updates["ollama_model"] = settings.ollama_model

    if not environment_has("WAKE_PHRASE", environment):
        voice_updates["wake_phrase"] = settings.wake_phrase
    if not environment_has("ENGLISH_WAKE_PHRASE", environment):
        voice_updates["english_wake_phrase"] = settings.english_wake_phrase
    if not environment_has("STT_BACKEND", environment):
        voice_updates["stt_backend"] = settings.stt_backend
    if not environment_has("WHISPER_MODEL", environment):
        voice_updates["whisper_model"] = settings.stt_model
    if not environment_has("TTS_VOICE", environment):
        voice_updates["tts_voice_name"] = settings.tts_voice

    return replace(config, **config_updates), replace(voice, **voice_updates)
