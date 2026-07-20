"""Desktop user interface for the assistant."""

from .today_window import DesktopVoiceController, TodayDesktopApi, start_desktop

DesktopApi = TodayDesktopApi

__all__ = ["DesktopApi", "DesktopVoiceController", "start_desktop"]
