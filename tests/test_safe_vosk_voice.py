from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from future_assistant.localization import Language
from future_assistant.safe_voice_cli import _build_safe_voice_loop
from future_assistant.voice.errors import VoiceConfigurationError
from future_assistant.voice.settings import VoiceSettings
from future_assistant.voice.vosk_transcription import VoskTranscriber
from future_assistant.voice.wakeword import VoskWakeWordDetector


class FakeRecognizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.accepted = b""

    def AcceptWaveform(self, data: bytes) -> bool:  # noqa: N802
        self.accepted = data
        return True

    def Result(self) -> str:  # noqa: N802
        return json.dumps({"text": self.text}, ensure_ascii=False)

    def FinalResult(self) -> str:  # noqa: N802
        return json.dumps({"text": self.text}, ensure_ascii=False)


def test_vosk_transcriber_is_lazy_local_and_reuses_model(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    model_path = tmp_path / "vosk-ar"
    model_path.mkdir()
    loads: list[str] = []

    def model(path: str) -> object:
        loads.append(path)
        return object()

    fake_vosk = SimpleNamespace(
        SetLogLevel=lambda _level: None,
        Model=model,
        KaldiRecognizer=lambda _model, _rate: FakeRecognizer("افتح يوتيوب"),
    )
    monkeypatch.setitem(sys.modules, "vosk", fake_vosk)
    transcriber = VoskTranscriber(model_path=model_path)

    assert transcriber.transcribe(b"\x00\x00" * 20) == "افتح يوتيوب"
    assert transcriber.transcribe(b"\x01\x00" * 20) == "افتح يوتيوب"
    assert loads == [str(model_path)]


def test_vosk_transcriber_rejects_missing_model(tmp_path) -> None:  # noqa: ANN001
    transcriber = VoskTranscriber(model_path=tmp_path / "missing")

    with pytest.raises(VoiceConfigurationError, match="مسار نموذج Vosk"):
        transcriber.transcribe(b"\x00\x00")


def test_safe_voice_entry_uses_vosk_for_arabic_commands(tmp_path) -> None:  # noqa: ANN001
    arabic_model = tmp_path / "vosk-ar"
    arabic_model.mkdir()
    settings = VoiceSettings(
        vosk_model_path=arabic_model,
        language=Language.AR,
        stt_backend="vosk",
        tts_enabled=False,
    )

    loop = _build_safe_voice_loop(settings, on_command=lambda command: command)

    assert isinstance(loop.transcriber, VoskTranscriber)
    assert loop.transcriber.model_path == arabic_model
    assert isinstance(loop.wake_detector, VoskWakeWordDetector)


def test_safe_voice_entry_selects_english_model_when_requested(tmp_path) -> None:  # noqa: ANN001
    arabic_model = tmp_path / "vosk-ar"
    english_model = tmp_path / "vosk-en"
    arabic_model.mkdir()
    english_model.mkdir()
    settings = VoiceSettings(
        vosk_model_path=arabic_model,
        vosk_english_model_path=english_model,
        language=Language.AUTO,
        whisper_language="en",
        stt_backend="vosk",
        tts_enabled=False,
    )

    loop = _build_safe_voice_loop(settings, on_command=lambda command: command)

    assert isinstance(loop.transcriber, VoskTranscriber)
    assert loop.transcriber.model_path == english_model
