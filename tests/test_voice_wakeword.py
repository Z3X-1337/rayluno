from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from future_assistant.voice import (
    CompositeWakeWordDetector,
    VoiceConfigurationError,
    VoskWakeWordDetector,
)


class FakeRecognizer:
    def __init__(self) -> None:
        self.partial = ""
        self.completed = False
        self.reset_count = 0

    def AcceptWaveform(self, data: bytes) -> bool:  # noqa: N802
        assert data
        return self.completed

    def Result(self) -> str:  # noqa: N802
        return json.dumps({"text": self.partial}, ensure_ascii=False)

    def PartialResult(self) -> str:  # noqa: N802
        return json.dumps({"partial": self.partial}, ensure_ascii=False)

    def Reset(self) -> None:  # noqa: N802
        self.reset_count += 1


def test_vosk_detector_uses_custom_phrase_and_latches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recognizer = FakeRecognizer()
    captured: dict[str, object] = {}

    def model(path: str) -> object:
        captured["model_path"] = path
        return object()

    def kaldi_recognizer(
        model_object: object,
        sample_rate: float,
        grammar: str,
    ) -> FakeRecognizer:
        captured["model"] = model_object
        captured["sample_rate"] = sample_rate
        captured["grammar"] = json.loads(grammar)
        return recognizer

    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(Model=model, KaldiRecognizer=kaldi_recognizer),
    )
    detector = VoskWakeWordDetector(
        model_path=tmp_path,
        wake_phrase="  يا مُساعد  ",
    )
    assert captured == {}

    recognizer.partial = "من فضلك يا مساعد"
    assert detector.process(b"\x00\x00")
    assert not detector.process(b"\x00\x00")
    assert captured["model_path"] == str(tmp_path)
    assert captured["sample_rate"] == 16_000.0
    assert captured["grammar"] == ["يا مساعد", "[unk]"]

    detector.reset()
    assert recognizer.reset_count == 1
    assert detector.process(b"\x00\x00")


def test_vosk_detector_rejects_substring_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recognizer = FakeRecognizer()
    recognizer.partial = "assistantship"
    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(
            Model=lambda path: object(),
            KaldiRecognizer=lambda model, rate, grammar: recognizer,
        ),
    )
    detector = VoskWakeWordDetector(
        model_path=tmp_path,
        wake_phrase="assistant",
    )

    assert not detector.process(b"\x00\x00")


def test_vosk_detector_validates_model_path(tmp_path: Path) -> None:
    detector = VoskWakeWordDetector(
        model_path=tmp_path / "missing",
        wake_phrase="عبارتي الخاصة",
    )

    with pytest.raises(VoiceConfigurationError, match="Vosk") as error:
        detector.process(b"\x00\x00")

    assert "مسار" in str(error.value)


def test_vosk_detector_can_use_static_graph_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recognizer = FakeRecognizer()
    captured: dict[str, tuple[object, ...]] = {}

    def kaldi_recognizer(*args: object) -> FakeRecognizer:
        captured["args"] = args
        return recognizer

    monkeypatch.setitem(
        sys.modules,
        "vosk",
        SimpleNamespace(
            Model=lambda path: object(),
            KaldiRecognizer=kaldi_recognizer,
            SetLogLevel=lambda level: captured.setdefault("log", (level,)),
        ),
    )
    detector = VoskWakeWordDetector(
        model_path=tmp_path,
        wake_phrase="يا مساعد",
        constrained_grammar=False,
    )

    assert detector.process(b"\x00\x00") is False
    assert len(captured["args"]) == 2
    assert captured["log"] == (-1,)


class FakeWakeDetector:
    def __init__(self, trigger: bytes) -> None:
        self.trigger = trigger
        self.frames: list[bytes] = []
        self.reset_count = 0

    def process(self, pcm: bytes) -> bool:
        self.frames.append(pcm)
        return pcm == self.trigger

    def reset(self) -> None:
        self.reset_count += 1


def test_composite_detector_feeds_both_languages_latches_and_resets() -> None:
    arabic = FakeWakeDetector(b"arabic")
    english = FakeWakeDetector(b"english")
    detector = CompositeWakeWordDetector((arabic, english))

    assert detector.process(b"noise") is False
    assert detector.process(b"english") is True
    assert detector.process(b"arabic") is False
    assert arabic.frames == [b"noise", b"english"]
    assert english.frames == [b"noise", b"english"]

    detector.reset()
    assert arabic.reset_count == 1
    assert english.reset_count == 1
    assert detector.process(b"arabic") is True


def test_composite_detector_requires_at_least_one_language() -> None:
    with pytest.raises(ValueError, match="واحد"):
        CompositeWakeWordDetector(())
