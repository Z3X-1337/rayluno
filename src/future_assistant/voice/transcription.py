"""Offline speech transcription through the optional faster-whisper package."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

from .errors import VoiceConfigurationError, VoiceDependencyError


class _Segment(Protocol):
    text: str


class _WhisperModel(Protocol):
    def transcribe(
        self,
        audio: object,
        **kwargs: object,
    ) -> tuple[Iterable[_Segment], object]: ...


class FasterWhisperTranscriber:
    """Transcribe in-memory PCM16, loading model code and weights on first use."""

    def __init__(
        self,
        *,
        model_size_or_path: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
        beam_size: int = 1,
    ) -> None:
        if not model_size_or_path.strip():
            raise ValueError("يجب تحديد اسم نموذج Whisper أو مساره.")
        if beam_size < 1:
            raise ValueError("يجب أن تكون قيمة beam_size واحدًا على الأقل.")
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model: _WhisperModel | None = None

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16_000) -> str:
        """Return normalized text while never writing command audio to disk."""

        if sample_rate != 16_000:
            raise VoiceConfigurationError(
                "يتطلب Faster Whisper صوتًا بمعدل 16000 هرتز في هذه الطبقة."
            )
        if len(pcm) % 2:
            raise ValueError("بيانات PCM16 يجب أن تحتوي عددًا زوجيًا من البايتات.")
        if not pcm:
            return ""
        try:
            import numpy as np
        except ImportError as exc:
            raise VoiceDependencyError(
                "تحويل الصوت غير متاح. ثبّت الحزمة الاختيارية 'numpy'."
            ) from exc

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        audio *= 1.0 / 32768.0
        model = self._get_model()
        try:
            segments, _ = model.transcribe(
                audio,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=False,
                condition_on_previous_text=False,
                temperature=0.0,
            )
            return " ".join(
                segment.text.strip() for segment in segments if segment.text.strip()
            ).strip()
        except Exception as exc:
            raise VoiceConfigurationError(
                "فشل تحويل الكلام إلى نص. تحقق من نموذج Whisper وإعدادات الجهاز."
            ) from exc

    def _get_model(self) -> _WhisperModel:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VoiceDependencyError(
                "تحويل الكلام إلى نص غير متاح. ثبّت الحزمة الاختيارية "
                "'faster-whisper' ثم أعد التشغيل."
            ) from exc
        try:
            self._model = cast(
                "_WhisperModel",
                WhisperModel(
                    self.model_size_or_path,
                    device=self.device,
                    compute_type=self.compute_type,
                ),
            )
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تحميل نموذج Whisper. تحقق من اسمه أو مساره ومن المساحة "
                "المتاحة وإعدادات الجهاز."
            ) from exc
        return self._model
