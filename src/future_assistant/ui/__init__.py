"""Desktop user interface for the assistant."""

from .memory_window import MemoryDesktopApi, start_desktop
from .verified_window import DesktopVoiceController, VerifiedDesktopApi

DesktopApi = MemoryDesktopApi

__all__ = [
    "DesktopApi",
    "DesktopVoiceController",
    "MemoryDesktopApi",
    "VerifiedDesktopApi",
    "start_desktop",
]
