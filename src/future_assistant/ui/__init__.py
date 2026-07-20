"""Desktop user interface for the assistant."""

from .memory_window import DesktopVoiceController, MemoryDesktopApi, start_desktop

DesktopApi = MemoryDesktopApi

__all__ = ["DesktopApi", "DesktopVoiceController", "start_desktop"]
