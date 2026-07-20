"""In-memory speech transcription through optional whisper.cpp bindings."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Protocol, cast

from .errors import VoiceConfigurationError, VoiceDependencyError


class _Segment(Protocol):
    text: str


class _WhisperCppModel(Protocol):
    def transcribe(self, audio: object, **kwargs: object) -> Iterable[_Segment]: ...


class WhisperCppTranscriber:
    """Transcribe PCM directly from memory with a legacy-CPU-compatible wheel."""

    def __init__(
        self,
        *,
        model_size_or_path: str = "base",
        language: str | None = None,
        threads: int | None = None,
    ) -> None:
        if not model_size_or_path.strip():
            raise ValueError("يجب تحديد اسم نموذج Whisper أو مساره.")
        if threads is not None and threads < 1:
            raise ValueError("عدد مسارات المعالجة يجب أن يكون واحدًا على الأقل.")
        self.model_size_or_path = model_size_or_path
        self.language = language
        self.threads = threads or min(4, os.cpu_count() or 1)
        self._model: _WhisperCppModel | None = None

    def transcribe(self, pcm: bytes, *, sample_rate: int = 16_000) -> str:
        if sample_rate != 16_000:
            raise VoiceConfigurationError("يتطلب whisper.cpp صوتًا بمعدل 16000 هرتز في هذه الطبقة.")
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
        try:
            segments = self._get_model().transcribe(
                audio,
                language=self.language or "auto",
                no_context=True,
                print_progress=False,
                print_realtime=False,
                print_timestamps=False,
            )
            return " ".join(
                segment.text.strip() for segment in segments if segment.text.strip()
            ).strip()
        except Exception as exc:
            raise VoiceConfigurationError(
                "فشل تحويل الكلام إلى نص عبر whisper.cpp. تحقق من النموذج وإعدادات الجهاز."
            ) from exc

    def _get_model(self) -> _WhisperCppModel:
        if self._model is not None:
            return self._model
        try:
            from pywhispercpp.model import Model
        except ImportError as exc:
            raise VoiceDependencyError(
                "محرك whisper.cpp غير متاح. ثبّت الحزمة الاختيارية "
                "'pywhispercpp==1.3.1' ثم أعد التشغيل."
            ) from exc
        try:
            self._model = cast(
                "_WhisperCppModel",
                Model(
                    self.model_size_or_path,
                    language=self.language or "auto",
                    n_threads=self.threads,
                    print_progress=False,
                    print_realtime=False,
                    print_timestamps=False,
                    no_context=True,
                    redirect_whispercpp_logs_to=None,
                ),
            )
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تحميل نموذج whisper.cpp. تحقق من اسمه أو مساره ومن المساحة المتاحة."
            ) from exc
        return self._model
