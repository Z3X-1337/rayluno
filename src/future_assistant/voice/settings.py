"""Environment-backed configuration for the optional local voice pipeline."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..identity import (
    COMPATIBILITY_DATA_DIRECTORY,
    DEFAULT_WAKE_PHRASE_AR,
    DEFAULT_WAKE_PHRASE_EN,
    environment_value,
)
from ..localization import Language, normalize_language
from .errors import VoiceConfigurationError
from .loop import ErrorCallback, VoiceLoop, WakeCallback
from .microphone import MicrophoneStream
from .recorder import UtteranceRecorder, UtteranceRecorderConfig
from .transcription import FasterWhisperTranscriber
from .tts import WindowsOneCoreSpeaker
from .wakeword import CompositeWakeWordDetector, VoskWakeWordDetector
from .whispercpp import WhisperCppTranscriber

_ARABIC_VOSK_MODEL = "vosk-model-ar-mgb2-0.4"
_ENGLISH_VOSK_MODEL = "vosk-model-small-en-us-0.15"


def _model_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / COMPATIBILITY_DATA_DIRECTORY / "models")
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        roots.append(Path(frozen_root) / "models")
    return tuple(roots)


def _installed_model(name: str) -> Path | None:
    for root in _model_roots():
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return None


def _default_whisper_model() -> str:
    for root in _model_roots():
        candidate = root / "whisper" / "ggml-base.bin"
        if candidate.is_file():
            return str(candidate)
    return "base"


def _env_bool(suffix: str, default: bool) -> bool:
    value = environment_value(suffix)
    if not value:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on", "نعم"}


def _microphone_device(value: str | None) -> int | str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    try:
        return int(cleaned)
    except ValueError:
        return cleaned


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    """Small, explicit set of settings required to enable always-on voice."""

    vosk_model_path: Path | None = None
    vosk_english_model_path: Path | None = None
    language: Language = Language.AUTO
    wake_phrase: str = DEFAULT_WAKE_PHRASE_AR
    english_wake_phrase: str = DEFAULT_WAKE_PHRASE_EN
    vosk_use_grammar: bool = False
    vosk_english_use_grammar: bool = True
    whisper_model: str = "base"
    stt_backend: str = "whispercpp"
    whisper_language: str | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    microphone_device: int | str | None = None
    rms_threshold: float = 500.0
    tts_enabled: bool = True
    tts_voice_name: str | None = None

    @classmethod
    def from_env(cls) -> VoiceSettings:
        model_value = environment_value("VOSK_MODEL_PATH").strip()
        english_model_value = environment_value("VOSK_ENGLISH_MODEL_PATH").strip()
        whisper_language = environment_value("WHISPER_LANGUAGE", "auto").strip()
        voice_name = environment_value("TTS_VOICE").strip()
        arabic_model = (
            Path(model_value).expanduser() if model_value else _installed_model(_ARABIC_VOSK_MODEL)
        )
        english_model = (
            Path(english_model_value).expanduser()
            if english_model_value
            else _installed_model(_ENGLISH_VOSK_MODEL)
        )
        return cls(
            vosk_model_path=arabic_model,
            vosk_english_model_path=english_model,
            language=normalize_language(environment_value("LANGUAGE", "auto")),
            wake_phrase=environment_value("WAKE_PHRASE", DEFAULT_WAKE_PHRASE_AR).strip(),
            english_wake_phrase=environment_value(
                "ENGLISH_WAKE_PHRASE", DEFAULT_WAKE_PHRASE_EN
            ).strip(),
            vosk_use_grammar=_env_bool("VOSK_USE_GRAMMAR", False),
            vosk_english_use_grammar=_env_bool("VOSK_ENGLISH_USE_GRAMMAR", True),
            whisper_model=environment_value("WHISPER_MODEL", _default_whisper_model()).strip(),
            stt_backend=environment_value("STT_BACKEND", "whispercpp").strip().casefold(),
            whisper_language=(
                None if whisper_language.casefold() == "auto" else whisper_language or None
            ),
            whisper_device=environment_value("WHISPER_DEVICE", "cpu").strip(),
            whisper_compute_type=environment_value("WHISPER_COMPUTE_TYPE", "int8").strip(),
            microphone_device=_microphone_device(environment_value("MICROPHONE_DEVICE")),
            rms_threshold=float(environment_value("RMS_THRESHOLD", "500")),
            tts_enabled=_env_bool("TTS_ENABLED", True),
            tts_voice_name=voice_name or None,
        )

    def validate(self) -> None:
        require_arabic = self.language in {Language.AR, Language.AUTO}
        require_english = self.language in {Language.EN, Language.AUTO}
        if require_arabic and self.vosk_model_path is None:
            raise VoiceConfigurationError(
                "ميزة كلمة الاستيقاظ تحتاج مسار نموذج Vosk محلي. اضبط "
                "RAYLUNO_VOSK_MODEL_PATH أولًا."
            )
        if (
            require_arabic
            and self.vosk_model_path is not None
            and not self.vosk_model_path.is_dir()
        ):
            raise VoiceConfigurationError(f"مسار نموذج Vosk غير موجود: {self.vosk_model_path}")
        if require_english and self.vosk_english_model_path is None:
            raise VoiceConfigurationError(
                "ميزة الاستيقاظ الإنجليزية تحتاج نموذج Vosk محلي. اضبط "
                "RAYLUNO_VOSK_ENGLISH_MODEL_PATH أولًا."
            )
        if (
            require_english
            and self.vosk_english_model_path is not None
            and not self.vosk_english_model_path.is_dir()
        ):
            raise VoiceConfigurationError(
                f"مسار نموذج Vosk الإنجليزي غير موجود: {self.vosk_english_model_path}"
            )
        if require_arabic and not self.wake_phrase:
            raise VoiceConfigurationError("عبارة الاستيقاظ لا يمكن أن تكون فارغة.")
        if require_english and not self.english_wake_phrase:
            raise VoiceConfigurationError("عبارة الاستيقاظ الإنجليزية لا يمكن أن تكون فارغة.")
        if not self.whisper_model:
            raise VoiceConfigurationError("اسم نموذج Whisper لا يمكن أن يكون فارغًا.")
        if self.stt_backend not in {"whispercpp", "faster-whisper"}:
            raise VoiceConfigurationError("محرك STT يجب أن يكون whispercpp أو faster-whisper.")
        if self.rms_threshold < 0:
            raise VoiceConfigurationError("عتبة حساسية الميكروفون لا يمكن أن تكون سالبة.")


CommandHandler = Callable[[str], str | None]


def build_voice_loop(
    settings: VoiceSettings,
    *,
    on_command: CommandHandler,
    on_wake: WakeCallback | None = None,
    on_error: ErrorCallback | None = None,
) -> VoiceLoop:
    """Build the production voice pipeline without loading a model until it runs."""

    settings.validate()
    speaker = None
    if settings.tts_enabled and sys.platform == "win32":
        speaker = WindowsOneCoreSpeaker(voice_name_contains=settings.tts_voice_name)
    recorder_config = UtteranceRecorderConfig(rms_threshold=settings.rms_threshold)
    if settings.stt_backend == "faster-whisper":
        transcriber = FasterWhisperTranscriber(
            model_size_or_path=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            language=settings.whisper_language,
        )
    else:
        transcriber = WhisperCppTranscriber(
            model_size_or_path=settings.whisper_model,
            language=settings.whisper_language,
        )
    detectors: list[VoskWakeWordDetector] = []
    if settings.language in {Language.AR, Language.AUTO}:
        assert settings.vosk_model_path is not None  # validated above
        detectors.append(
            VoskWakeWordDetector(
                model_path=settings.vosk_model_path,
                wake_phrase=settings.wake_phrase,
                constrained_grammar=settings.vosk_use_grammar,
            )
        )
    if settings.language in {Language.EN, Language.AUTO}:
        assert settings.vosk_english_model_path is not None  # validated above
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
        recorder=UtteranceRecorder(recorder_config),
        transcriber=transcriber,
        on_command=on_command,
        speaker=speaker,
        on_wake=on_wake,
        on_error=on_error,
    )
