"""Desktop user interface for the assistant."""

from .verified_window import DesktopVoiceController, VerifiedDesktopApi, start_desktop

DesktopApi = VerifiedDesktopApi

__all__ = ["DesktopApi", "DesktopVoiceController", "VerifiedDesktopApi", "start_desktop"]
