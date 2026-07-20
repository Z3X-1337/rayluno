from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType

from future_assistant.voice import VoiceLoop


class FakeStream(Iterator[bytes]):
    def __init__(self, frames: list[bytes]) -> None:
        self.frames = iter(frames)
        self.closed = False

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __iter__(self) -> FakeStream:
        return self

    def __next__(self) -> bytes:
        if self.closed:
            raise StopIteration
        return next(self.frames)

    def close(self) -> None:
        self.closed = True


class FakeDetector:
    def __init__(self) -> None:
        self.reset_count = 0

    def process(self, pcm: bytes) -> bool:
        return pcm == b"wake"

    def reset(self) -> None:
        self.reset_count += 1


class FakeRecorder:
    def record(self, frames: Iterator[bytes], *, stop_event: object) -> bytes:
        assert next(frames) == b"command-audio"
        return b"captured"


class FakeTranscriber:
    def transcribe(self, pcm: bytes, *, sample_rate: int = 16_000) -> str:
        assert pcm == b"captured"
        assert sample_rate == 16_000
        return "افتح المتصفح"


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


def test_voice_loop_callbacks_response_and_stop() -> None:
    stream = FakeStream([b"noise", b"wake", b"command-audio", b"ignored"])
    detector = FakeDetector()
    speaker = FakeSpeaker()
    wakes: list[bool] = []
    commands: list[str] = []
    loop: VoiceLoop

    def on_command(text: str) -> str:
        commands.append(text)
        loop.stop()
        return "تم"

    loop = VoiceLoop(
        stream_factory=lambda: stream,
        wake_detector=detector,
        recorder=FakeRecorder(),  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),
        on_command=on_command,
        speaker=speaker,
        on_wake=lambda: wakes.append(True),
    )

    assert loop.run() == 1
    assert commands == ["افتح المتصفح"]
    assert wakes == [True]
    assert speaker.spoken == ["تم"]
    assert detector.reset_count == 1
    assert stream.closed
    assert not loop.running


def test_voice_loop_reports_error_callback_and_exits() -> None:
    stream = FakeStream([b"frame"])
    errors: list[Exception] = []

    class BrokenDetector(FakeDetector):
        def process(self, pcm: bytes) -> bool:
            raise RuntimeError("boom")

    loop = VoiceLoop(
        stream_factory=lambda: stream,
        wake_detector=BrokenDetector(),
        recorder=FakeRecorder(),  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),
        on_command=lambda text: None,
        on_error=errors.append,
    )

    assert loop.run() == 0
    assert len(errors) == 1
    assert str(errors[0]) == "boom"
    assert stream.closed
