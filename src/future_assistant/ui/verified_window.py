"""Desktop composition root for the Verified Execution and Trust Center interfaces."""

from __future__ import annotations

from typing import Any

from . import window as legacy
from .today_window import DesktopVoiceController, TodayDesktopApi


class VerifiedDesktopApi(TodayDesktopApi):
    """Today bridge extended with verified execution and a runtime-backed trust report."""

    def get_trust_snapshot(self) -> dict[str, object]:
        """Return the implemented trust contract without exposing local secrets."""

        try:
            ledger = self.runtime.receipt_ledger
            integrity_ok = bool(self.runtime.receipt_integrity_ok)
            settings = self._settings_store.load()
            manifests = self.runtime.skill_engine.registry.manifests
            guarantees = {
                "write_ahead_authorization": True,
                "authenticated_checkpoint": bool(
                    integrity_ok and getattr(ledger, "authenticated_checkpoint", False)
                ),
                "keyed_fingerprints": callable(
                    getattr(ledger, "fingerprint_arguments", None)
                ),
                "explicit_memory": callable(getattr(self, "get_memory_snapshot", None)),
                "no_shell": True,
                "telemetry_off": not bool(settings.telemetry_opt_in),
            }
            return {
                "available": True,
                "integrity_ok": integrity_ok,
                "guarantees": guarantees,
                "active_count": sum(guarantees.values()),
                "total_count": len(guarantees),
                "registered_skill_count": len(manifests),
                "judge_mode": self._judge_mode,
                "checkpoint_kind": "local_hmac_sha256",
                "authorization_order": "authorize_then_effect_then_outcome",
                "limitations": [
                    "same_user_key_access_can_forge_local_state",
                    "complete_trust_state_deletion_looks_like_clean_install",
                    "not_hardware_or_remotely_witnessed",
                ],
            }
        except Exception as exc:
            return {
                "available": False,
                "integrity_ok": False,
                "guarantees": {},
                "active_count": 0,
                "total_count": 6,
                "registered_skill_count": 0,
                "judge_mode": self._judge_mode,
                "checkpoint_kind": "unavailable",
                "authorization_order": "unavailable",
                "limitations": [],
                "error": type(exc).__name__,
            }

    def get_verified_snapshot(self) -> dict[str, object]:
        snapshot = super().get_verified_snapshot()
        snapshot["trust"] = self.get_trust_snapshot()
        return snapshot

    def get_verified_receipts(self, limit: object = 20) -> dict[str, object]:
        result = super().get_verified_receipts(limit)
        result["trust"] = self.get_trust_snapshot()
        return result

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
                  if (!document.querySelector('link[data-rayluno-trust-center]')) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = 'trust_center.css';
                    link.dataset.raylunoTrustCenter = 'true';
                    document.head.append(link);
                  }
                  if (!document.querySelector('script[data-rayluno-trust-center]')) {
                    const script = document.createElement('script');
                    script.src = 'trust_center.js';
                    script.dataset.raylunoTrustCenter = 'true';
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
