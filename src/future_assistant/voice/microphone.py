"""Live microphone input implemented with an optional sounddevice dependency."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import suppress
from queue import Empty, Full, Queue
from threading import Event, Lock
from types import TracebackType
from typing import Protocol, Self, cast

from .errors import VoiceDependencyError, VoiceDeviceError


class _RawInputStream(Protocol):
    def start(self) -> object: ...

    def stop(self) -> object: ...

    def close(self) -> object: ...


class _SoundDeviceModule(Protocol):
    def RawInputStream(self, **kwargs: object) -> _RawInputStream: ...  # noqa: N802


_END = object()


class MicrophoneStream(Iterator[bytes]):
    """Yield low-latency PCM16 mono chunks without persisting microphone audio.

    ``sounddevice`` is imported only when :meth:`start` is called. If the
    callback queue fills, the oldest chunk is discarded so command latency
    does not grow without bound.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        block_duration_seconds: float = 0.05,
        device: int | str | None = None,
        queue_size: int = 32,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("يجب أن يكون معدل أخذ العينات رقمًا موجبًا.")
        if block_duration_seconds <= 0:
            raise ValueError("يجب أن تكون مدة كتلة الصوت أكبر من صفر.")
        if queue_size < 1:
            raise ValueError("يجب أن يستوعب طابور الصوت كتلة واحدة على الأقل.")

        self.sample_rate = sample_rate
        self.block_duration_seconds = block_duration_seconds
        self.device = device
        self._queue: Queue[bytes | object] = Queue(maxsize=queue_size)
        self._closed = Event()
        self._state_lock = Lock()
        self._stream: _RawInputStream | None = None

    @property
    def block_size(self) -> int:
        """Number of mono samples requested from PortAudio per callback."""

        return max(1, round(self.sample_rate * self.block_duration_seconds))

    @property
    def is_open(self) -> bool:
        return self._stream is not None and not self._closed.is_set()

    def _load_sounddevice(self) -> _SoundDeviceModule:
        try:
            import sounddevice
        except ImportError as exc:
            raise VoiceDependencyError(
                "ميزة الميكروفون غير متاحة. ثبّت الحزمة الاختيارية 'sounddevice' ثم أعد التشغيل."
            ) from exc
        return cast("_SoundDeviceModule", sounddevice)

    def start(self) -> None:
        """Open and start the configured input device."""

        with self._state_lock:
            if self._stream is not None:
                return
            self._clear_queue()
            self._closed.clear()
            sounddevice = self._load_sounddevice()
            stream: _RawInputStream | None = None
            try:
                stream = sounddevice.RawInputStream(
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    device=self.device,
                    channels=1,
                    dtype="int16",
                    callback=self._audio_callback,
                )
                stream.start()
            except Exception as exc:
                self._closed.set()
                if stream is not None:
                    with suppress(Exception):
                        stream.close()
                raise VoiceDeviceError(
                    "تعذّر فتح الميكروفون. تحقق من صلاحية الوصول ومن جهاز "
                    "الإدخال المحدد وإعدادات PortAudio."
                ) from exc
            self._stream = stream

    def close(self) -> None:
        """Stop input promptly and release the device; safe to call repeatedly."""

        with self._state_lock:
            stream, self._stream = self._stream, None
            self._closed.set()
            self._offer_end_marker()
            if stream is None:
                return
            with suppress(Exception):
                stream.stop()
            with suppress(Exception):
                stream.close()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> bytes:
        while True:
            if self._closed.is_set() and self._queue.empty():
                raise StopIteration
            try:
                item = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if item is _END:
                raise StopIteration
            return cast("bytes", item)

    def _audio_callback(
        self,
        indata: object,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        del frames, time_info, status
        if self._closed.is_set():
            return
        chunk = bytes(indata)
        try:
            self._queue.put_nowait(chunk)
        except Full:
            with suppress(Empty):
                self._queue.get_nowait()
            with suppress(Full):
                self._queue.put_nowait(chunk)

    def _offer_end_marker(self) -> None:
        try:
            self._queue.put_nowait(_END)
        except Full:
            with suppress(Empty):
                self._queue.get_nowait()
            with suppress(Full):
                self._queue.put_nowait(_END)

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return
