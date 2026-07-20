from __future__ import annotations

from array import array
from threading import Event

import pytest

from future_assistant.voice import (
    UtteranceRecorder,
    UtteranceRecorderConfig,
    pcm16_rms,
)


def pcm_frame(value: int, *, samples: int = 10) -> bytes:
    return array("h", [value] * samples).tobytes()


def test_recorder_keeps_pre_roll_and_stops_after_silence() -> None:
    config = UtteranceRecorderConfig(
        sample_rate=100,
        rms_threshold=500,
        pre_roll_seconds=0.2,
        start_timeout_seconds=1.0,
        silence_seconds=0.2,
        min_speech_seconds=0.2,
        max_utterance_seconds=2.0,
    )
    recorder = UtteranceRecorder(config)
    quiet = pcm_frame(0)
    speech = pcm_frame(1_000)

    result = recorder.record([quiet, quiet, quiet, speech, speech, speech, quiet, quiet, speech])

    assert result == b"".join([quiet, quiet, speech, speech, speech, quiet, quiet])


def test_recorder_times_out_and_rejects_short_noise() -> None:
    timeout_recorder = UtteranceRecorder(
        UtteranceRecorderConfig(
            sample_rate=100,
            start_timeout_seconds=0.3,
            silence_seconds=0.2,
            min_speech_seconds=0.2,
        )
    )
    quiet = pcm_frame(0)
    assert timeout_recorder.record([quiet] * 10) is None

    short_noise = pcm_frame(1_000)
    assert timeout_recorder.record([short_noise, quiet, quiet]) is None


def test_recorder_respects_stop_event_and_max_duration() -> None:
    event = Event()
    event.set()
    recorder = UtteranceRecorder(
        UtteranceRecorderConfig(
            sample_rate=100,
            max_utterance_seconds=0.3,
            min_speech_seconds=0.1,
        )
    )
    speech = pcm_frame(1_000)

    assert recorder.record([speech] * 10, stop_event=event) is None

    event.clear()
    result = recorder.record([speech] * 10, stop_event=event)
    assert result == speech * 3

    one_frame_recorder = UtteranceRecorder(
        UtteranceRecorderConfig(
            sample_rate=100,
            max_utterance_seconds=0.1,
            min_speech_seconds=0.1,
        )
    )
    assert one_frame_recorder.record([speech] * 3) == speech


def test_pcm16_rms_and_incomplete_frame_validation() -> None:
    assert pcm16_rms(pcm_frame(1_000)) == pytest.approx(1_000)
    assert pcm16_rms(b"") == 0
    with pytest.raises(ValueError, match="PCM16"):
        pcm16_rms(b"\x00")
