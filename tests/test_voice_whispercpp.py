from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from future_assistant.voice import WhisperCppTranscriber


def test_whispercpp_transcribes_pcm_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeModel:
        def __init__(self, model: str, **kwargs: object) -> None:
            captured["model"] = model
            captured["init"] = kwargs

        def transcribe(self, audio: object, **kwargs: object):  # noqa: ANN201
            captured["audio"] = audio
            captured["transcribe"] = kwargs
            return [SimpleNamespace(text="  افتح يوتيوب  ")]

    package = ModuleType("pywhispercpp")
    model_module = ModuleType("pywhispercpp.model")
    model_module.Model = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pywhispercpp", package)
    monkeypatch.setitem(sys.modules, "pywhispercpp.model", model_module)
    transcriber = WhisperCppTranscriber(model_size_or_path="base", language="ar", threads=2)

    result = transcriber.transcribe(b"\x00\x00\xff\x7f")

    assert result == "افتح يوتيوب"
    assert captured["model"] == "base"
    assert isinstance(captured["audio"], np.ndarray)
    assert captured["transcribe"]["language"] == "ar"


def test_whispercpp_validates_pcm_shape_and_sample_rate() -> None:
    transcriber = WhisperCppTranscriber()

    with pytest.raises(ValueError, match="زوجي"):
        transcriber.transcribe(b"\x00")
    with pytest.raises(Exception, match="16000"):
        transcriber.transcribe(b"\x00\x00", sample_rate=8_000)
