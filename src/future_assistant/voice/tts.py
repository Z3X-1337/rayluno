"""Bilingual Windows text-to-speech with OneCore and SAPI support."""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from ..localization import Language, detect_language
from .errors import VoiceConfigurationError, VoiceDependencyError


class _SapiVoiceToken(Protocol):
    def GetDescription(self) -> str: ...  # noqa: N802


class _SapiVoiceCollection(Protocol):
    Count: int

    def Item(self, index: int) -> _SapiVoiceToken: ...  # noqa: N802


class _SapiVoice(Protocol):
    Rate: int
    Volume: int
    Voice: _SapiVoiceToken

    def Speak(self, text: str) -> object: ...  # noqa: N802

    def GetVoices(self) -> _SapiVoiceCollection: ...  # noqa: N802


DispatchFactory = Callable[[str], object]
WavePlayer = Callable[[bytes], None]


def _text_language(text: str) -> str:
    """Return the dominant supported language for a response."""

    return detect_language(text, fallback=Language.EN).value


def _run_awaitable(awaitable: Awaitable[bytes]) -> bytes:
    """Run a WinRT awaitable from synchronous or already-async callers."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: list[bytes] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(awaitable))
        except BaseException as exc:  # pragma: no cover - defensive thread boundary
            error.append(exc)

    thread = threading.Thread(target=runner, name="onecore-tts", daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


@dataclass(frozen=True, slots=True)
class _OneCoreVoice:
    raw: object
    name: str
    language: str
    identifier: str


class _SpeechBackend(Protocol):
    def synthesize(self, text: str, *, language: str, voice_query: str | None) -> bytes: ...


class _WinRTSpeechBackend:
    """Lazy adapter around Windows.Media.SpeechSynthesis."""

    def synthesize(self, text: str, *, language: str, voice_query: str | None) -> bytes:
        return _run_awaitable(
            self._synthesize_async(text, language=language, voice_query=voice_query)
        )

    async def _synthesize_async(
        self,
        text: str,
        *,
        language: str,
        voice_query: str | None,
    ) -> bytes:
        try:
            from winrt.windows.media.speechsynthesis import SpeechSynthesizer
            from winrt.windows.storage.streams import DataReader
        except ImportError as exc:
            raise VoiceDependencyError(
                "النطق ثنائي اللغة غير متاح. ثبّت الحزمة الاختيارية 'voice' ثم أعد التشغيل."
            ) from exc

        voices = [
            _OneCoreVoice(
                raw=voice,
                name=str(voice.display_name),
                language=str(voice.language),
                identifier=str(voice.id),
            )
            for voice in SpeechSynthesizer.all_voices
        ]
        candidates = self._voice_candidates(voices, language=language, query=voice_query)
        if not candidates:
            requested = voice_query or ("العربية" if language == "ar" else "English")
            raise VoiceConfigurationError(f"لم يُعثر على صوت Windows مناسب للغة: {requested}")

        last_error: Exception | None = None
        for candidate in candidates:
            synthesizer = SpeechSynthesizer()
            stream = None
            reader = None
            try:
                synthesizer.voice = candidate.raw
                stream = await synthesizer.synthesize_text_to_stream_async(text)
                reader = DataReader(stream.get_input_stream_at(0))
                loaded = await reader.load_async(int(stream.size))
                wav = bytearray(loaded)
                reader.read_bytes(wav)
                if not wav.startswith(b"RIFF"):
                    raise VoiceConfigurationError("أعاد Windows بيانات صوت غير صالحة.")
                return bytes(wav)
            except (OSError, RuntimeError, VoiceConfigurationError) as exc:
                last_error = exc
                if voice_query:
                    break
            finally:
                if reader is not None:
                    reader.close()
                if stream is not None:
                    stream.close()
                close = getattr(synthesizer, "close", None)
                if close is not None:
                    close()

        raise VoiceConfigurationError(
            "تعذّر توليد الصوت المختار. قد يكون ظاهرًا في Windows لكن ملفاته غير مكتملة."
        ) from last_error

    @staticmethod
    def _voice_candidates(
        voices: list[_OneCoreVoice],
        *,
        language: str,
        query: str | None,
    ) -> list[_OneCoreVoice]:
        if query:
            normalized = query.casefold()
            return [
                voice
                for voice in voices
                if normalized in f"{voice.name} {voice.language} {voice.identifier}".casefold()
            ]

        matching = [
            voice for voice in voices if voice.language.casefold().startswith(f"{language}-")
        ]
        if language == "ar":
            # Naayf is commonly complete on Windows even when a stale Hoda token remains.
            matching.sort(key=lambda voice: ("naayf" not in voice.name.casefold(), voice.name))
        return matching


def _play_wave(wav: bytes) -> None:
    if sys.platform != "win32":
        raise VoiceConfigurationError("تشغيل صوت Windows متاح على نظام Windows فقط.")
    try:
        import winsound
    except ImportError as exc:  # pragma: no cover - part of CPython on Windows
        raise VoiceDependencyError("وحدة تشغيل الصوت في Windows غير متاحة.") from exc
    winsound.PlaySound(wav, winsound.SND_MEMORY | winsound.SND_SYNC)


class WindowsOneCoreSpeaker:
    """Speak Arabic and English with installed modern Windows voices."""

    def __init__(
        self,
        *,
        voice_name_contains: str | None = None,
        backend: _SpeechBackend | None = None,
        player: WavePlayer | None = None,
    ) -> None:
        self.voice_name_contains = voice_name_contains
        self._backend = backend
        self._player = player or _play_wave

    def speak(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        if sys.platform != "win32" and self._backend is None:
            raise VoiceConfigurationError("Windows OneCore متاح على نظام Windows فقط.")
        backend = self._backend or _WinRTSpeechBackend()
        try:
            wav = backend.synthesize(
                cleaned,
                language=_text_language(cleaned),
                voice_query=self.voice_name_contains,
            )
            self._player(wav)
        except (VoiceConfigurationError, VoiceDependencyError):
            raise
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تشغيل النطق عبر Windows. تحقق من جهاز الإخراج والأصوات المثبتة."
            ) from exc


def probe_onecore_languages() -> frozenset[str]:
    """Return languages that can actually synthesize a short local sample."""

    if sys.platform != "win32":
        return frozenset()
    backend = _WinRTSpeechBackend()
    working: set[str] = set()
    for language, sample in (("ar", "جاهز"), ("en", "Ready")):
        try:
            backend.synthesize(sample, language=language, voice_query=None)
        except (VoiceConfigurationError, VoiceDependencyError):
            continue
        working.add(language)
    return frozenset(working)


class WindowsSapiSpeaker:
    """Speak through the built-in Windows SAPI engine, initialized lazily."""

    def __init__(
        self,
        *,
        rate: int = 0,
        volume: int = 100,
        voice_name_contains: str | None = None,
        dispatch_factory: DispatchFactory | None = None,
    ) -> None:
        if not -10 <= rate <= 10:
            raise ValueError("سرعة صوت SAPI يجب أن تكون بين -10 و10.")
        if not 0 <= volume <= 100:
            raise ValueError("مستوى صوت SAPI يجب أن يكون بين 0 و100.")
        self.rate = rate
        self.volume = volume
        self.voice_name_contains = voice_name_contains
        self._dispatch_factory = dispatch_factory
        self._voice: _SapiVoice | None = None

    def speak(self, text: str) -> None:
        """Speak non-empty text synchronously."""

        cleaned = text.strip()
        if not cleaned:
            return
        voice = self._get_voice()
        try:
            voice.Speak(cleaned)
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تشغيل النطق عبر Windows SAPI. تحقق من جهاز الإخراج والصوت المثبت."
            ) from exc

    def _get_voice(self) -> _SapiVoice:
        if self._voice is not None:
            return self._voice
        if sys.platform != "win32" and self._dispatch_factory is None:
            raise VoiceConfigurationError("Windows SAPI متاح على نظام Windows فقط.")
        dispatch = self._dispatch_factory or self._load_dispatch()
        try:
            voice = cast("_SapiVoice", dispatch("SAPI.SpVoice"))
            voice.Rate = self.rate
            voice.Volume = self.volume
            if self.voice_name_contains:
                voice.Voice = self._select_voice(voice, self.voice_name_contains)
            else:
                preferred = self._preferred_arabic_voice(voice)
                if preferred is not None:
                    voice.Voice = preferred
        except VoiceConfigurationError:
            raise
        except Exception as exc:
            raise VoiceConfigurationError(
                "تعذّر تهيئة Windows SAPI. تحقق من تثبيت صوت صالح في النظام."
            ) from exc
        self._voice = voice
        return voice

    @staticmethod
    def _load_dispatch() -> DispatchFactory:
        try:
            from win32com.client import Dispatch
        except ImportError as exc:
            raise VoiceDependencyError(
                "النطق الصوتي غير متاح. ثبّت الحزمة الاختيارية 'pywin32' على Windows ثم أعد التشغيل."
            ) from exc
        return cast("DispatchFactory", Dispatch)

    @staticmethod
    def _select_voice(voice: _SapiVoice, query: str) -> _SapiVoiceToken:
        voices = voice.GetVoices()
        normalized_query = query.casefold()
        for index in range(voices.Count):
            candidate = voices.Item(index)
            if normalized_query in candidate.GetDescription().casefold():
                return candidate
        raise VoiceConfigurationError(f"لم يُعثر على صوت Windows يحتوي اسمه على: {query}")

    @staticmethod
    def _preferred_arabic_voice(voice: _SapiVoice) -> _SapiVoiceToken | None:
        markers = ("arabic", "hoda", "naayf", "هدى", "نايف", "عربي")
        voices = voice.GetVoices()
        for index in range(voices.Count):
            candidate = voices.Item(index)
            description = candidate.GetDescription().casefold()
            if any(marker in description for marker in markers):
                return candidate
        return None
