"""Desktop composition root for the Verified Execution v2 interface."""

from __future__ import annotations

from typing import Any

from . import window as legacy
from .today_window import DesktopVoiceController, TodayDesktopApi


class VerifiedDesktopApi(TodayDesktopApi):
    """Today bridge that injects the confirmation gate and receipt inspector assets."""

    def bind_window(self, window: Any) -> None:
        super().bind_window(window)

        def inject_verified_assets(*_: object) -> None:
            window.evaluate_js(
                """
                (() => {
                  if (!document.querySelector('link[data-rayluno-verified-v2]')) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = 'verified_v2.css';
                    link.dataset.raylunoVerifiedV2 = 'true';
                    document.head.append(link);
                  }
                  if (!document.querySelector('script[data-rayluno-verified-v2]')) {
                    const script = document.createElement('script');
                    script.src = 'verified_v2.js';
                    script.dataset.raylunoVerifiedV2 = 'true';
                    document.body.append(script);
                  }
                })();
                """
            )

        window.events.loaded += inject_verified_assets


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the legacy window with VerifiedDesktopApi as its composition root."""

    original_api = legacy.DesktopApi
    legacy.DesktopApi = VerifiedDesktopApi
    try:
        legacy.start_desktop(*args, **kwargs)
    finally:
        legacy.DesktopApi = original_api


__all__ = [
    "DesktopVoiceController",
    "VerifiedDesktopApi",
    "start_desktop",
]
