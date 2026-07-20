"""Desktop composition root for verified skills, confirmations, and receipts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from future_assistant.verified_runtime import VerifiedCommandResult, VerifiedRuntimeBridge
from future_assistant.verified_skills import UnknownConfirmationError

from . import window as legacy
from .today_window import TodayDesktopApi

DesktopVoiceController = legacy.DesktopVoiceController


class VerifiedDesktopApi(TodayDesktopApi):
    """Today desktop bridge with fail-closed verified execution support."""

    def __init__(
        self,
        runtime: Any,
        *args: Any,
        verified_bridge: VerifiedRuntimeBridge | None = None,
        verified_bridge_factory: Callable[[Any], VerifiedRuntimeBridge] = VerifiedRuntimeBridge,
        **kwargs: Any,
    ) -> None:
        super().__init__(runtime, *args, **kwargs)
        self._verified_error: str | None = None
        try:
            self._verified = verified_bridge or verified_bridge_factory(runtime)
        except Exception as exc:
            self._verified = None
            self._verified_error = type(exc).__name__

    def execute_command(self, command: str) -> dict[str, object]:
        """Execute through the verified bridge and expose JSON-safe lifecycle data."""

        cleaned = command.strip() if isinstance(command, str) else ""
        if not cleaned:
            return {"ok": False, "message": "اكتب أمرًا أولًا.", "action": "none"}
        if len(cleaned) > 2_000:
            return {
                "ok": False,
                "message": "الأمر أطول من الحد المسموح.",
                "action": "blocked",
                "status": "blocked",
                "verified": True,
            }
        if self._verified is None:
            payload = self._unavailable_payload(cleaned)
            self._remember(payload)
            self.emit({"verified_status": self.get_verified_status()})
            return payload

        try:
            with self._execution_lock:
                outcome = self._verified.execute(cleaned)
        except Exception as exc:
            self._verified_error = type(exc).__name__
            payload = self._unavailable_payload(cleaned)
            self._remember(payload)
            self.emit({"verified_status": self.get_verified_status()})
            return payload

        payload = self._payload(outcome)
        self._remember(payload)
        self._emit_verified_lifecycle(payload)
        return payload

    def approve_skill(self, confirmation_id: object) -> dict[str, object]:
        return self._resolve_confirmation(confirmation_id, approve=True)

    def reject_skill(self, confirmation_id: object) -> dict[str, object]:
        return self._resolve_confirmation(confirmation_id, approve=False)

    def get_verified_status(self) -> dict[str, object]:
        bridge = self._verified
        if bridge is None:
            return {
                "available": False,
                "integrity_ok": False,
                "supported_skills": ["browser.search", "app.launch"],
                "receipt_count": 0,
                "latest_hash": None,
                "error": self._verified_error or "unavailable",
            }
        try:
            receipts = bridge.recent_receipts(limit=100)
            integrity_ok = bridge.receipt_integrity_ok
        except Exception as exc:
            self._verified_error = type(exc).__name__
            return {
                "available": False,
                "integrity_ok": False,
                "supported_skills": ["browser.search", "app.launch"],
                "receipt_count": 0,
                "latest_hash": None,
                "error": self._verified_error,
            }
        return {
            "available": True,
            "integrity_ok": integrity_ok,
            "supported_skills": ["browser.search", "app.launch"],
            "receipt_count": len(receipts),
            "latest_hash": receipts[0].get("receipt_hash") if receipts else None,
            "error": None,
        }

    def get_verified_receipts(self, limit: object = 20) -> dict[str, object]:
        bridge = self._verified
        if bridge is None:
            return {
                "ok": False,
                "integrity_ok": False,
                "receipts": [],
                "message": "طبقة التنفيذ الموثق غير متاحة.",
            }
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            parsed_limit = 20
        try:
            receipts = bridge.recent_receipts(limit=max(1, min(parsed_limit, 100)))
            integrity_ok = bridge.receipt_integrity_ok
        except Exception as exc:
            self._verified_error = type(exc).__name__
            return {
                "ok": False,
                "integrity_ok": False,
                "receipts": [],
                "message": "تعذّر التحقق من سجل التنفيذ.",
            }
        return {
            "ok": integrity_ok,
            "integrity_ok": integrity_ok,
            "receipts": receipts,
            "message": (
                "سلسلة الإيصالات سليمة." if integrity_ok else "فشل التحقق من سلسلة الإيصالات."
            ),
        }

    def get_snapshot(self) -> dict[str, object]:
        snapshot = super().get_snapshot()
        snapshot["verified"] = self.get_verified_status()
        return snapshot

    def _resolve_confirmation(
        self,
        confirmation_id: object,
        *,
        approve: bool,
    ) -> dict[str, object]:
        bridge = self._verified
        if bridge is None:
            return self._unavailable_payload("")
        if not isinstance(confirmation_id, str) or not confirmation_id.strip():
            return self._invalid_confirmation_payload()
        try:
            with self._execution_lock:
                outcome = (
                    bridge.approve(confirmation_id.strip())
                    if approve
                    else bridge.reject(confirmation_id.strip())
                )
        except UnknownConfirmationError:
            return self._invalid_confirmation_payload()
        except Exception as exc:
            self._verified_error = type(exc).__name__
            return self._unavailable_payload("")
        payload = self._payload(outcome)
        self._remember(payload)
        self.emit({"result": payload, "verified_resolution": payload})
        if payload.get("receipt"):
            self.emit({"verified_receipt": payload["receipt"]})
        return payload

    def _emit_verified_lifecycle(self, payload: dict[str, object]) -> None:
        pending = payload.get("pending_confirmation")
        if isinstance(pending, dict):
            self.emit(
                {
                    "verified_confirmation": pending,
                    "verified_receipt": payload.get("receipt"),
                }
            )
        elif payload.get("receipt"):
            self.emit({"verified_receipt": payload["receipt"]})

    def _remember(self, payload: dict[str, object]) -> None:
        with self._history_lock:
            self._history.insert(0, dict(payload))
            del self._history[20:]

    @staticmethod
    def _payload(outcome: VerifiedCommandResult) -> dict[str, object]:
        payload = outcome.to_dict()
        payload["ai_generated"] = False
        return payload

    @staticmethod
    def _invalid_confirmation_payload() -> dict[str, object]:
        return {
            "ok": False,
            "status": "blocked",
            "message": "انتهت صلاحية التأكيد أو تم استخدامه مسبقًا.",
            "action": "blocked",
            "command": "",
            "pending_confirmation": None,
            "receipt": None,
            "verified": True,
            "ai_generated": False,
        }

    def _unavailable_payload(self, command: str) -> dict[str, object]:
        return {
            "ok": False,
            "status": "blocked",
            "message": "تعذّر التحقق من مسار التنفيذ؛ تم منع الإجراء بأمان.",
            "action": "blocked",
            "command": command,
            "pending_confirmation": None,
            "receipt": None,
            "verified": True,
            "ai_generated": False,
        }


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the legacy window with VerifiedDesktopApi as the composition root."""

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
