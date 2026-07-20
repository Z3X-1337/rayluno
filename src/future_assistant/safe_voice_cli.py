"""Crash-resistant Windows voice entry point using local Vosk transcription."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock

from . import cli
from .localization import Language
from .ui import window as desktop_window
from .voice.errors import VoiceConfigurationError
from .voice.loop import (
    AudioStream,
    CommandCallback,
    ErrorCallback,
    Speaker,
    StreamFactory,
    Transcriber,
    WakeCallback,
    VoiceLoop,
)
from .voice.microphone import MicrophoneStream
from .voice.recorder import UtteranceRecorder, UtteranceRecorderConfig
from .voice.settings import CommandHandler, VoiceSettings
from .voice.tts import WindowsOneCoreSpeaker
from .voice.vosk_transcription import VoskTranscriber

_ORIGINAL_BUILD_VOICE_LOOP = desktop_window.build_voice_loop


class PushToTalkVoiceLoop:
    """Record, transcribe, and dispatch exactly one command per microphone click."""

    def __init__(
        self,
        *,
        stream_factory: StreamFactory,
        recorder: UtteranceRecorder,
        transcriber: Transcriber,
        on_command: CommandCallback,
        speaker: Speaker | None = None,
        on_wake: WakeCallback | None = None,
        on_error: ErrorCallback | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        self.stream_factory = stream_factory
        self.recorder = recorder
        self.transcriber = transcriber
        self.on_command = on_command
        self.speaker = speaker
        self.on_wake = on_wake
        self.on_error = on_error
        self.sample_rate = sample_rate
        self._stop_event = Event()
        self._state_lock = Lock()
        self._active_stream: AudioStream | None = None
        self._running = False

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._running

    def run(self) -> int:
        with self._state_lock:
            if self._running:
                raise RuntimeError("التسجيل الصوتي يعمل بالفعل.")
            self._running = True
            self._stop_event.clear()

        try:
            with self.stream_factory() as stream:
                with self._state_lock:
                    self._active_stream = stream
                if self.on_wake is not None:
                    self.on_wake()
                utterance = self.recorder.record(
                    iter(stream),
                    stop_event=self._stop_event,
                )
                if not utterance or self._stop_event.is_set():
                    raise VoiceConfigurationError(
                        "لم ألتقط كلامًا واضحًا. اضغط زر الميكروفون وتحدث مباشرة "
                        "خلال ثلاث ثوانٍ."
                    )
                text = self.transcriber.transcribe(
                    utterance,
                    sample_rate=self.sample_rate,
                ).strip()
                if not text:
                    raise VoiceConfigurationError(
                        "تم تسجيل الصوت، لكن Vosk لم يستخرج نصًا واضحًا. تحدث قرب "
                        "الميكروفون وبجملة قصيرة."
                    )
                response = self.on_command(text)
                if self.speaker is not None and response and response.strip():
                    self.speaker.speak(response)
                return 1
        except Exception as exc:
            if self.on_error is None:
                raise
            self.on_error(exc)
            return 0
        finally:
            with self._state_lock:
                self._active_stream = None
                self._running = False

    def stop(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            stream = self._active_stream
        if stream is not None:
            with suppress(Exception):
                stream.close()


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
) -> VoiceLoop | PushToTalkVoiceLoop:
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

    return PushToTalkVoiceLoop(
        stream_factory=lambda: MicrophoneStream(device=settings.microphone_device),
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
