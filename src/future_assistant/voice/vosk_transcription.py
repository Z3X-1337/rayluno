"""Offline command transcription using the same local Vosk models as wake detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, cast

from .errors import VoiceConfigurationError, VoiceDependencyError


class _Recognizer(Protocol):
    def AcceptWaveform(self, data: bytes) -> bool: ...  # noqa: N802

    def Result(self) -> str: ...  # noqa: N802

    def FinalResult(self) -> str: ...  # noqa: N802


class _VoskModule(Protocol):
    def Model(self, model_path: str) -> object: ...  # noqa: N802

    def KaldiRecognizer(  # noqa: N802
        self,
        model: object,
        sample_rate: float,
        *args: object,
    ) -> _Recognizer: ...


class VoskTranscriber:
    """Transcribe one complete in-memory PCM16 utterance without Whisper/CTranslate2."""

    def __init__(self, *, model_path: str | Path) -> None:
        self.model_path = Path(model_path).expanduser()
        self._module: _VoskModule | None = None
        self._model: object | None = None

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16_000) -> str:
        if sample_rate <= 0:
            raise VoiceConfigurationError("يجب أن يكون معدل أخذ العينات رقمًا موجبًا.")
        if len(pcm) % 2:
            raise ValueError("بيانات PCM16 يجب أن تحتوي عددًا زوجيًا من البايتات.")
        if not pcm:
            return ""

        module, model = self._get_model()
        try:
            recognizer = module.KaldiRecognizer(model, float(sample_rate))
            recognizer.AcceptWaveform(pcm)
            final_result = getattr(recognizer, "FinalResult", None)
            payload = final_result() if callable(final_result) else recognizer.Result()
        except Exception as exc:
            raise VoiceConfigurationError(
                "فشل تحويل الكلام إلى نص باستخدام Vosk. تحقق من نموذج اللغة والميكروفون."
            ) from exc
        return self._text_from_result(payload)

    def _get_model(self) -> tuple[_VoskModule, object]:
        if self._module is not None and self._model is not None:
            return self._module, self._model
        if not self.model_path.is_dir():
            raise VoiceConfigurationError(
                f"مسار نموذج Vosk غير صالح أو غير موجود: {self.model_path}"
            )
        try:
            import vosk
        except ImportError as exc:
            raise VoiceDependencyError(
                "تحويل الكلام إلى نص عبر Vosk غير متاح. ثبّت الحزمة الاختيارية 'vosk'."
            ) from exc

        module = cast("_VoskModule", vosk)
        try:
            set_log_level = getattr(module, "SetLogLevel", None)
            if callable(set_log_level):
                set_log_level(-1)
            model = module.Model(str(self.model_path))
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تحميل نموذج Vosk للتفريغ الصوتي. تحقق من اكتمال ملفات النموذج."
            ) from exc
        self._module = module
        self._model = model
        return module, model

    @staticmethod
    def _text_from_result(payload: str) -> str:
        try:
            result = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return ""
        value = result.get("text", "") if isinstance(result, dict) else ""
        return " ".join(value.split()) if isinstance(value, str) else ""


__all__ = ["VoskTranscriber"]
