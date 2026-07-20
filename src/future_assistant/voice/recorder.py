"""In-memory, energy-based command recording."""

from __future__ import annotations

import math
import sys
from array import array
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from threading import Event


@dataclass(frozen=True, slots=True)
class UtteranceRecorderConfig:
    """Timing and energy thresholds for local utterance capture."""

    sample_rate: int = 16_000
    channels: int = 1
    sample_width_bytes: int = 2
    rms_threshold: float = 500.0
    pre_roll_seconds: float = 0.25
    start_timeout_seconds: float = 3.0
    silence_seconds: float = 0.8
    min_speech_seconds: float = 0.15
    max_utterance_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("يجب أن يكون معدل أخذ العينات رقمًا موجبًا.")
        if self.channels != 1 or self.sample_width_bytes != 2:
            raise ValueError("مسجل الأوامر يدعم حاليًا PCM16 أحادي القناة فقط.")
        if self.rms_threshold < 0:
            raise ValueError("لا يمكن أن تكون عتبة RMS سالبة.")
        if self.pre_roll_seconds < 0:
            raise ValueError("لا يمكن أن تكون مدة التمهيد سالبة.")
        if self.start_timeout_seconds <= 0:
            raise ValueError("مهلة بدء الكلام يجب أن تكون أكبر من صفر.")
        if self.silence_seconds <= 0:
            raise ValueError("مدة الصمت يجب أن تكون أكبر من صفر.")
        if self.min_speech_seconds < 0:
            raise ValueError("لا يمكن أن تكون مدة الكلام الدنيا سالبة.")
        if self.max_utterance_seconds <= 0:
            raise ValueError("مدة الأمر القصوى يجب أن تكون أكبر من صفر.")
        if self.min_speech_seconds > self.max_utterance_seconds:
            raise ValueError("مدة الكلام الدنيا لا يمكن أن تتجاوز مدة الأمر القصوى.")


class UtteranceRecorder:
    """Capture one command from PCM chunks, keeping all audio in memory only."""

    def __init__(self, config: UtteranceRecorderConfig | None = None) -> None:
        self.config = config or UtteranceRecorderConfig()

    def record(
        self,
        frames: Iterable[bytes],
        *,
        stop_event: Event | None = None,
    ) -> bytes | None:
        """Return one bounded utterance, or ``None`` if speech never qualifies."""

        pre_roll: deque[tuple[bytes, float]] = deque()
        pre_roll_bytes = 0
        bytes_per_second = (
            self.config.sample_rate * self.config.channels * self.config.sample_width_bytes
        )
        pre_roll_limit = round(self.config.pre_roll_seconds * bytes_per_second)
        output: list[bytes] = []
        waiting_duration = 0.0
        active_duration = 0.0
        voiced_duration = 0.0
        trailing_silence = 0.0
        started = False

        for frame in frames:
            if stop_event is not None and stop_event.is_set():
                return None
            duration = self._duration(frame)
            if duration == 0:
                continue
            rms = pcm16_rms(frame)

            if not started:
                waiting_duration += duration
                if rms >= self.config.rms_threshold:
                    started = True
                    output.extend(chunk for chunk, _ in pre_roll)
                    output.append(frame)
                    active_duration = duration
                    voiced_duration = duration
                    pre_roll.clear()
                else:
                    pre_roll.append((frame, duration))
                    pre_roll_bytes += len(frame)
                    while pre_roll and pre_roll_bytes > pre_roll_limit:
                        removed_frame, _ = pre_roll.popleft()
                        pre_roll_bytes -= len(removed_frame)
                if not started and waiting_duration >= self.config.start_timeout_seconds:
                    return None
                if started and active_duration >= self.config.max_utterance_seconds:
                    break
                continue

            output.append(frame)
            active_duration += duration
            if rms >= self.config.rms_threshold:
                voiced_duration += duration
                trailing_silence = 0.0
            else:
                trailing_silence += duration

            if active_duration >= self.config.max_utterance_seconds:
                break
            if trailing_silence >= self.config.silence_seconds:
                break

        if not started or voiced_duration < self.config.min_speech_seconds:
            return None
        return b"".join(output)

    def _duration(self, frame: bytes) -> float:
        frame_width = self.config.sample_width_bytes * self.config.channels
        if len(frame) % frame_width:
            raise ValueError("كتلة الصوت ليست PCM16 أحادية القناة مكتملة.")
        return len(frame) / (self.config.sample_rate * frame_width)


def pcm16_rms(frame: bytes) -> float:
    """Calculate RMS for little-endian signed PCM16 without extra dependencies."""

    if len(frame) % 2:
        raise ValueError("بيانات PCM16 يجب أن تحتوي عددًا زوجيًا من البايتات.")
    if not frame:
        return 0.0
    samples = array("h")
    samples.frombytes(frame)
    if sys.byteorder == "big":
        samples.byteswap()
    mean_square = sum(sample * sample for sample in samples) / len(samples)
    return math.sqrt(mean_square)
