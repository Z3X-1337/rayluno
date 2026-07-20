from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from future_assistant.voice import (
    FasterWhisperTranscriber,
    VoiceConfigurationError,
    WindowsOneCoreSpeaker,
    WindowsSapiSpeaker,
)


class FakeAudio:
    def astype(self, dtype: object) -> FakeAudio:
        return self

    def __imul__(self, value: float) -> FakeAudio:
        return self


class FakeWhisperModel:
    created: list[tuple[str, str, str]] = []

    def __init__(self, name: str, *, device: str, compute_type: str) -> None:
        self.created.append((name, device, compute_type))
        self.calls: list[dict[str, object]] = []

    def transcribe(
        self,
        audio: object,
        **kwargs: object,
    ) -> tuple[list[SimpleNamespace], object]:
        assert isinstance(audio, FakeAudio)
        self.calls.append(kwargs)
        return [SimpleNamespace(text=" مرحبًا "), SimpleNamespace(text="بك")], object()


def test_faster_whisper_loads_lazily_and_uses_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeWhisperModel.created.clear()
    fake_numpy = SimpleNamespace(
        int16=object(),
        float32=object(),
        frombuffer=lambda pcm, dtype: FakeAudio(),
    )
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    transcriber = FasterWhisperTranscriber(
        model_size_or_path="local-model",
        language="ar",
    )
    assert FakeWhisperModel.created == []

    assert transcriber.transcribe(b"\x00\x00") == "مرحبًا بك"
    assert FakeWhisperModel.created == [("local-model", "cpu", "int8")]
    assert transcriber.transcribe(b"\x00\x00") == "مرحبًا بك"
    assert len(FakeWhisperModel.created) == 1


def test_faster_whisper_rejects_wrong_sample_rate() -> None:
    transcriber = FasterWhisperTranscriber()
    with pytest.raises(VoiceConfigurationError, match="16000"):
        transcriber.transcribe(b"\x00\x00", sample_rate=8_000)


class FakeToken:
    def __init__(self, description: str) -> None:
        self.description = description

    def GetDescription(self) -> str:  # noqa: N802
        return self.description


class FakeTokens:
    def __init__(self, tokens: list[FakeToken]) -> None:
        self.tokens = tokens
        self.Count = len(tokens)

    def Item(self, index: int) -> FakeToken:  # noqa: N802
        return self.tokens[index]


class FakeSapiVoice:
    def __init__(self) -> None:
        self.Rate = 0
        self.Volume = 0
        self.Voice: FakeToken | None = None
        self.spoken: list[str] = []
        self.tokens = FakeTokens([FakeToken("English"), FakeToken("Arabic Voice")])

    def GetVoices(self) -> FakeTokens:  # noqa: N802
        return self.tokens

    def Speak(self, text: str) -> None:  # noqa: N802
        self.spoken.append(text)


def test_windows_sapi_is_lazy_and_selects_requested_voice() -> None:
    voice = FakeSapiVoice()
    dispatch_calls: list[str] = []

    def dispatch(name: str) -> object:
        dispatch_calls.append(name)
        return voice

    speaker = WindowsSapiSpeaker(
        rate=2,
        volume=80,
        voice_name_contains="arabic",
        dispatch_factory=dispatch,
    )
    assert dispatch_calls == []

    speaker.speak("  أهلًا  ")

    assert dispatch_calls == ["SAPI.SpVoice"]
    assert voice.Rate == 2
    assert voice.Volume == 80
    assert voice.Voice is voice.tokens.tokens[1]
    assert voice.spoken == ["أهلًا"]


def test_windows_sapi_prefers_arabic_voice_automatically() -> None:
    voice = FakeSapiVoice()
    speaker = WindowsSapiSpeaker(dispatch_factory=lambda name: voice)

    speaker.speak("مرحبًا")

    assert voice.Voice is voice.tokens.tokens[1]


class FakeSpeechBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def synthesize(self, text: str, *, language: str, voice_query: str | None) -> bytes:
        self.calls.append((text, language, voice_query))
        return b"RIFF-fake-wave"


@pytest.mark.parametrize(
    ("text", "expected_language"),
    [("مرحبًا، النظام جاهز", "ar"), ("Hello, the system is ready", "en")],
)
def test_onecore_speaker_selects_language_and_plays_wave(
    text: str,
    expected_language: str,
) -> None:
    backend = FakeSpeechBackend()
    played: list[bytes] = []
    speaker = WindowsOneCoreSpeaker(backend=backend, player=played.append)

    speaker.speak(f"  {text}  ")

    assert backend.calls == [(text, expected_language, None)]
    assert played == [b"RIFF-fake-wave"]


def test_onecore_speaker_honors_explicit_voice_and_ignores_empty_text() -> None:
    backend = FakeSpeechBackend()
    played: list[bytes] = []
    speaker = WindowsOneCoreSpeaker(
        voice_name_contains="Naayf",
        backend=backend,
        player=played.append,
    )

    speaker.speak("  ")
    speaker.speak("جاهز")

    assert backend.calls == [("جاهز", "ar", "Naayf")]
    assert played == [b"RIFF-fake-wave"]
