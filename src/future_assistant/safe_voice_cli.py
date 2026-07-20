"""Crash-resistant Windows voice entry point using Vosk for command transcription."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from . import cli
from .localization import Language
from .ui import window as desktop_window
from .voice.errors import VoiceConfigurationError
from .voice.loop import ErrorCallback, VoiceLoop, WakeCallback
from .voice.microphone import MicrophoneStream
from .voice.recorder import UtteranceRecorder, UtteranceRecorderConfig
from .voice.settings import CommandHandler, VoiceSettings
from .voice.tts import WindowsOneCoreSpeaker
from .voice.vosk_transcription import VoskTranscriber
from .voice.wakeword import CompositeWakeWordDetector, VoskWakeWordDetector

_ORIGINAL_BUILD_VOICE_LOOP = desktop_window.build_voice_loop


def _command_model(settings: VoiceSettings) -> Path:
    if settings.language is Language.EN:
        candidate = settings.vosk_english_model_path
    elif settings.language is Language.AR:
        candidate = settings.vosk_model_path
    elif (settings.whisper_language or "").casefold().startswith("en"):
        candidate = settings.vosk_english_model_path
    else:
        candidate = settings.vosk_model_path
    if candidate is None or not candidate.is_dir():
        raise VoiceConfigurationError(
            "تعذر اختيار نموذج Vosk للتفريغ. اضبط RAYLUNO_LANGUAGE=ar أو en "
            "وتحقق من مسار نموذج اللغة."
        )
    return candidate


def _build_safe_voice_loop(
    settings: VoiceSettings,
    *,
    on_command: CommandHandler,
    on_wake: WakeCallback | None = None,
    on_error: ErrorCallback | None = None,
) -> VoiceLoop:
    if settings.stt_backend != "vosk":
        return _ORIGINAL_BUILD_VOICE_LOOP(
            settings,
            on_command=on_command,
            on_wake=on_wake,
            on_error=on_error,
        )

    replace(settings, stt_backend="whispercpp").validate()
    transcriber = VoskTranscriber(model_path=_command_model(settings))
    speaker = None
    if settings.tts_enabled and sys.platform == "win32":
        speaker = WindowsOneCoreSpeaker(voice_name_contains=settings.tts_voice_name)

    detectors: list[VoskWakeWordDetector] = []
    if settings.language in {Language.AR, Language.AUTO}:
        assert settings.vosk_model_path is not None
        detectors.append(
            VoskWakeWordDetector(
                model_path=settings.vosk_model_path,
                wake_phrase=settings.wake_phrase,
                constrained_grammar=settings.vosk_use_grammar,
            )
        )
    if settings.language in {Language.EN, Language.AUTO}:
        assert settings.vosk_english_model_path is not None
        detectors.append(
            VoskWakeWordDetector(
                model_path=settings.vosk_english_model_path,
                wake_phrase=settings.english_wake_phrase,
                constrained_grammar=settings.vosk_english_use_grammar,
            )
        )
    wake_detector = (
        detectors[0] if len(detectors) == 1 else CompositeWakeWordDetector(tuple(detectors))
    )
    return VoiceLoop(
        stream_factory=lambda: MicrophoneStream(device=settings.microphone_device),
        wake_detector=wake_detector,
        recorder=UtteranceRecorder(
            UtteranceRecorderConfig(rms_threshold=settings.rms_threshold)
        ),
        transcriber=transcriber,
        on_command=on_command,
        speaker=speaker,
        on_wake=on_wake,
        on_error=on_error,
    )


def main(argv: Sequence[str] | None = None) -> int:
    desktop_window.build_voice_loop = _build_safe_voice_loop
    try:
        return cli.main(argv)
    finally:
        desktop_window.build_voice_loop = _ORIGINAL_BUILD_VOICE_LOOP


if __name__ == "__main__":
    raise SystemExit(main())
