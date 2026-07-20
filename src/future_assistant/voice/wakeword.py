"""Offline wake-phrase detection using the Apache-licensed Vosk engine."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Protocol, cast

from .errors import VoiceConfigurationError, VoiceDependencyError


class _Recognizer(Protocol):
    def AcceptWaveform(self, data: bytes) -> bool: ...  # noqa: N802

    def Result(self) -> str: ...  # noqa: N802

    def PartialResult(self) -> str: ...  # noqa: N802

    def Reset(self) -> object: ...  # noqa: N802


class _VoskModule(Protocol):
    def Model(self, model_path: str) -> object: ...  # noqa: N802

    def KaldiRecognizer(  # noqa: N802
        self,
        model: object,
        sample_rate: float,
        *args: object,
    ) -> _Recognizer: ...


class WakeDetector(Protocol):
    def process(self, pcm: bytes) -> bool: ...

    def reset(self) -> None: ...


class CompositeWakeWordDetector:
    """Feed the same microphone stream to Arabic and English wake detectors."""

    def __init__(self, detectors: tuple[WakeDetector, ...]) -> None:
        if not detectors:
            raise ValueError("يجب توفير كاشف عبارة تنبيه واحد على الأقل.")
        self.detectors = detectors
        self._latched = False

    def process(self, pcm: bytes) -> bool:
        if self._latched or not pcm:
            return False
        detected = False
        for detector in self.detectors:
            if detector.process(pcm):
                detected = True
        self._latched = detected
        return detected

    def reset(self) -> None:
        self._latched = False
        for detector in self.detectors:
            detector.reset()


class VoskWakeWordDetector:
    """Detect a required, user-selected phrase entirely on the local machine.

    The Vosk Python package uses a permissive engine license. Deployments must
    still choose a downloaded language model whose own license fits their use.
    No bundled personal-use wake-word model is used by this class.
    """

    def __init__(
        self,
        *,
        model_path: str | Path,
        wake_phrase: str,
        sample_rate: int = 16_000,
        constrained_grammar: bool = True,
    ) -> None:
        phrase = _normalize(wake_phrase)
        if not phrase:
            raise ValueError("يجب اختيار عبارة تنبيه غير فارغة.")
        if sample_rate <= 0:
            raise ValueError("يجب أن يكون معدل أخذ العينات رقمًا موجبًا.")

        self.model_path = Path(model_path).expanduser()
        self.wake_phrase = phrase
        self.sample_rate = sample_rate
        self.constrained_grammar = constrained_grammar
        self._recognizer: _Recognizer | None = None
        self._latched = False

    def process(self, pcm: bytes) -> bool:
        """Consume PCM16 audio and return ``True`` once per detected phrase."""

        if self._latched or not pcm:
            return False
        recognizer = self._get_recognizer()
        completed = recognizer.AcceptWaveform(pcm)
        payload = recognizer.Result() if completed else recognizer.PartialResult()
        text = self._text_from_result(payload, partial=not completed)
        if not _contains_phrase(text, self.wake_phrase):
            return False
        self._latched = True
        return True

    def reset(self) -> None:
        """Re-arm detection and discard the recognizer's previous utterance."""

        self._latched = False
        if self._recognizer is not None:
            self._recognizer.Reset()

    def _get_recognizer(self) -> _Recognizer:
        if self._recognizer is not None:
            return self._recognizer
        if not self.model_path.is_dir():
            raise VoiceConfigurationError(
                f"مسار نموذج Vosk غير صالح أو غير موجود: {self.model_path}"
            )
        try:
            import vosk
        except ImportError as exc:
            raise VoiceDependencyError(
                "كشف عبارة التنبيه غير متاح. ثبّت الحزمة الاختيارية 'vosk' "
                "واختر نموذجًا محليًا بترخيص يناسب استخدامك."
            ) from exc

        vosk_module = cast("_VoskModule", vosk)
        try:
            set_log_level = getattr(vosk_module, "SetLogLevel", None)
            if callable(set_log_level):
                set_log_level(-1)
            model = vosk_module.Model(str(self.model_path))
            if self.constrained_grammar:
                grammar = json.dumps(
                    [self.wake_phrase, "[unk]"],
                    ensure_ascii=False,
                )
                self._recognizer = vosk_module.KaldiRecognizer(
                    model,
                    float(self.sample_rate),
                    grammar,
                )
            else:
                self._recognizer = vosk_module.KaldiRecognizer(
                    model,
                    float(self.sample_rate),
                )
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تحميل نموذج Vosk. تحقق من اكتمال ملفات النموذج ومن دعمه للغة عبارة التنبيه."
            ) from exc
        return self._recognizer

    @staticmethod
    def _text_from_result(payload: str, *, partial: bool) -> str:
        try:
            result = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return ""
        key = "partial" if partial else "text"
        value = result.get(key, "")
        return value if isinstance(value, str) else ""


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize(text)
    return f" {phrase} " in f" {normalized_text} "


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(
        character for character in normalized if not unicodedata.category(character).startswith("M")
    )
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())
