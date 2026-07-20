"""Composable and stoppable wake-listen-transcribe loop."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager, suppress
from threading import Event, Lock
from typing import Protocol

from .recorder import UtteranceRecorder


class WakeWordDetector(Protocol):
    def process(self, pcm: bytes) -> bool: ...

    def reset(self) -> None: ...


class Transcriber(Protocol):
    def transcribe(self, pcm: bytes, *, sample_rate: int = 16_000) -> str: ...


class Speaker(Protocol):
    def speak(self, text: str) -> None: ...


class AudioStream(AbstractContextManager["AudioStream"], Iterable[bytes], Protocol):
    def close(self) -> None: ...


CommandCallback = Callable[[str], str | None]
WakeCallback = Callable[[], None]
ErrorCallback = Callable[[Exception], None]
StreamFactory = Callable[[], AudioStream]


class VoiceLoop:
    """Run the local voice pipeline until :meth:`stop` is requested."""

    def __init__(
        self,
        *,
        stream_factory: StreamFactory,
        wake_detector: WakeWordDetector,
        recorder: UtteranceRecorder,
        transcriber: Transcriber,
        on_command: CommandCallback,
        speaker: Speaker | None = None,
        on_wake: WakeCallback | None = None,
        on_error: ErrorCallback | None = None,
        sample_rate: int = 16_000,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("يجب أن يكون معدل أخذ العينات رقمًا موجبًا.")
        self.stream_factory = stream_factory
        self.wake_detector = wake_detector
        self.recorder = recorder
        self.transcriber = transcriber
        self.on_command = on_command
        self.speaker = speaker
        self.on_wake = on_wake
        self.on_error = on_error
        self.sample_rate = sample_rate
        self._stop_event = Event()
        self._state_lock = Lock()
        self._active_stream: AudioStream | None = None
        self._running = False

    @property
    def running(self) -> bool:
        with self._state_lock:
            return self._running

    def run(self) -> int:
        """Block until stopped or input ends; return dispatched command count."""

        with self._state_lock:
            if self._running:
                raise RuntimeError("حلقة الصوت تعمل بالفعل.")
            self._running = True
            self._stop_event.clear()

        command_count = 0
        try:
            with self.stream_factory() as stream:
                with self._state_lock:
                    self._active_stream = stream
                iterator = iter(stream)
                while not self._stop_event.is_set():
                    try:
                        frame = next(iterator)
                    except StopIteration:
                        break
                    if not self.wake_detector.process(frame):
                        continue
                    if self.on_wake is not None:
                        self.on_wake()
                    try:
                        utterance = self.recorder.record(
                            iterator,
                            stop_event=self._stop_event,
                        )
                    finally:
                        self.wake_detector.reset()
                    if not utterance or self._stop_event.is_set():
                        continue
                    text = self.transcriber.transcribe(
                        utterance,
                        sample_rate=self.sample_rate,
                    ).strip()
                    if not text:
                        continue
                    response = self.on_command(text)
                    command_count += 1
                    if self.speaker is not None and response and response.strip():
                        self.speaker.speak(response)
        except Exception as exc:
            if self.on_error is None:
                raise
            self.on_error(exc)
        finally:
            with self._state_lock:
                self._active_stream = None
                self._running = False
        return command_count

    def stop(self) -> None:
        """Signal the loop and close active input so a blocked iterator wakes."""

        self._stop_event.set()
        with self._state_lock:
            stream = self._active_stream
        if stream is not None:
            with suppress(Exception):
                stream.close()
