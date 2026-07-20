"""Local-first voice input, wake phrase, transcription, and speech output."""

from .errors import (
    VoiceConfigurationError,
    VoiceDependencyError,
    VoiceDeviceError,
    VoiceError,
)
from .loop import VoiceLoop
from .microphone import MicrophoneStream
from .recorder import UtteranceRecorder, UtteranceRecorderConfig, pcm16_rms
from .settings import VoiceSettings, build_voice_loop
from .transcription import FasterWhisperTranscriber
from .tts import WindowsOneCoreSpeaker, WindowsSapiSpeaker, probe_onecore_languages
from .wakeword import CompositeWakeWordDetector, VoskWakeWordDetector
from .whispercpp import WhisperCppTranscriber

__all__ = [
    "FasterWhisperTranscriber",
    "CompositeWakeWordDetector",
    "MicrophoneStream",
    "UtteranceRecorder",
    "UtteranceRecorderConfig",
    "VoiceConfigurationError",
    "VoiceDependencyError",
    "VoiceDeviceError",
    "VoiceError",
    "VoiceLoop",
    "VoiceSettings",
    "VoskWakeWordDetector",
    "WhisperCppTranscriber",
    "WindowsOneCoreSpeaker",
    "WindowsSapiSpeaker",
    "build_voice_loop",
    "pcm16_rms",
    "probe_onecore_languages",
]
