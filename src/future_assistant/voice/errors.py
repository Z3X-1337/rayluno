"""Exceptions raised by the local voice pipeline."""


class VoiceError(RuntimeError):
    """Base error for voice features."""


class VoiceDependencyError(VoiceError):
    """An optional voice dependency is not installed."""


class VoiceConfigurationError(VoiceError):
    """The voice pipeline has invalid or incomplete configuration."""


class VoiceDeviceError(VoiceError):
    """A microphone or speech device could not be used."""
