from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

import pytest

from future_assistant.voice import (
    MicrophoneStream,
    VoiceDependencyError,
    VoiceDeviceError,
)


class FakeRawStream:
    def __init__(self, callback: Callable[..., None]) -> None:
        self.callback = callback
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakeSoundDevice:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}
        self.stream: FakeRawStream | None = None

    def RawInputStream(self, **kwargs: object) -> FakeRawStream:  # noqa: N802
        self.kwargs = kwargs
        callback = kwargs["callback"]
        assert callable(callback)
        self.stream = FakeRawStream(callback)
        return self.stream


def test_microphone_uses_raw_pcm_stream_without_hardware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sounddevice = FakeSoundDevice()
    microphone = MicrophoneStream(
        sample_rate=16_000,
        block_duration_seconds=0.1,
        queue_size=2,
    )
    monkeypatch.setattr(microphone, "_load_sounddevice", lambda: sounddevice)

    microphone.start()
    assert sounddevice.stream is not None
    assert sounddevice.stream.started
    assert sounddevice.kwargs["dtype"] == "int16"
    assert sounddevice.kwargs["channels"] == 1
    assert sounddevice.kwargs["blocksize"] == 1_600

    sounddevice.stream.callback(b"\x01\x00", 1, None, None)
    assert next(microphone) == b"\x01\x00"

    microphone.close()
    assert sounddevice.stream.stopped
    assert sounddevice.stream.closed
    with pytest.raises(StopIteration):
        next(microphone)


def test_microphone_reports_missing_optional_dependency_in_arabic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def import_without_sounddevice(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "sounddevice":
            raise ImportError("not installed")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_sounddevice)
    microphone = MicrophoneStream()

    with pytest.raises(VoiceDependencyError, match="sounddevice") as error:
        microphone.start()

    assert "الميكروفون" in str(error.value)


def test_microphone_closes_partially_opened_device_on_start_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenRawStream(FakeRawStream):
        def start(self) -> None:
            raise RuntimeError("PortAudio failure")

    class BrokenSoundDevice(FakeSoundDevice):
        def RawInputStream(self, **kwargs: object) -> BrokenRawStream:  # noqa: N802
            callback = kwargs["callback"]
            assert callable(callback)
            stream = BrokenRawStream(callback)
            self.stream = stream
            return stream

    sounddevice = BrokenSoundDevice()
    microphone = MicrophoneStream()
    monkeypatch.setattr(microphone, "_load_sounddevice", lambda: sounddevice)

    with pytest.raises(VoiceDeviceError, match="الميكروفون"):
        microphone.start()

    assert sounddevice.stream is not None
    assert sounddevice.stream.closed
