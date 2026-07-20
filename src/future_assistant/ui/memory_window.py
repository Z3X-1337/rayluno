"""Desktop composition root for explicit-consent personal memory."""

from __future__ import annotations

from typing import Any

from future_assistant.memory import MemoryService, SQLiteMemoryStore

from .verified_window import (
    DesktopVoiceController,
    VerifiedDesktopApi,
)
from .verified_window import (
    start_desktop as start_verified_desktop,
)


class MemoryDesktopApi(VerifiedDesktopApi):
    """Verified desktop bridge with a reviewable local memory vault."""

    def __init__(
        self,
        runtime: Any,
        *args: Any,
        memory_service: MemoryService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(runtime, *args, **kwargs)
        self._memory_error: str | None = None
        try:
            self._memory = memory_service or MemoryService(
                SQLiteMemoryStore(runtime.config.memory_path)
            )
        except Exception as exc:
            self._memory = None
            self._memory_error = type(exc).__name__

    def get_memory_snapshot(self, limit: object = 50) -> dict[str, object]:
        """Return only explicit user-approved facts and safe display metadata."""

        service = self._memory
        if service is None:
            return self._unavailable_snapshot()
        try:
            parsed_limit = int(limit)
        except (TypeError, ValueError):
            parsed_limit = 50
        try:
            facts = service.list(limit=max(1, min(parsed_limit, 100)))
        except Exception as exc:
            self._memory_error = type(exc).__name__
            return self._unavailable_snapshot()
        return {
            "available": True,
            "consent_mode": "explicit_only",
            "count": len(facts),
            "items": [
                {
                    "id": fact.id,
                    "statement": fact.statement,
                    "category": fact.category.value,
                    "source": fact.source,
                    "updated_at": fact.updated_at.isoformat(),
                }
                for fact in facts
            ],
            "error": None,
        }

    def forget_memory(self, memory_id: object) -> dict[str, object]:
        """Delete one user-selected memory by its visible local identifier."""

        service = self._memory
        if service is None:
            return {
                "ok": False,
                "message": "ذاكرة رايلونو غير متاحة حاليًا.",
                "memory": None,
            }
        try:
            parsed_id = int(memory_id)
        except (TypeError, ValueError):
            parsed_id = 0
        if isinstance(memory_id, bool) or parsed_id < 1:
            return {
                "ok": False,
                "message": "معرّف الذاكرة غير صالح.",
                "memory": None,
            }
        try:
            fact = service.forget(parsed_id)
        except Exception as exc:
            self._memory_error = type(exc).__name__
            return {
                "ok": False,
                "message": "تعذّر حذف الذاكرة بأمان.",
                "memory": None,
            }
        if fact is None:
            return {
                "ok": False,
                "message": "لم أجد ذاكرة بهذا الرقم.",
                "memory": None,
            }
        payload = {
            "ok": True,
            "message": f"حذفت الذاكرة رقم {fact.id}.",
            "memory": {
                "id": fact.id,
                "statement": fact.statement,
                "category": fact.category.value,
            },
        }
        self.emit({"memory_snapshot": self.get_memory_snapshot(), "memory_deleted": payload})
        return payload

    def get_snapshot(self) -> dict[str, object]:
        snapshot = super().get_snapshot()
        snapshot["memory"] = self.get_memory_snapshot()
        return snapshot

    def _unavailable_snapshot(self) -> dict[str, object]:
        return {
            "available": False,
            "consent_mode": "explicit_only",
            "count": 0,
            "items": [],
            "error": self._memory_error or "unavailable",
        }


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Use the memory-aware API while preserving the verified desktop launcher."""

    from . import verified_window

    original_api = verified_window.VerifiedDesktopApi
    verified_window.VerifiedDesktopApi = MemoryDesktopApi
    try:
        start_verified_desktop(*args, **kwargs)
    finally:
        verified_window.VerifiedDesktopApi = original_api


__all__ = [
    "DesktopVoiceController",
    "MemoryDesktopApi",
    "start_desktop",
]
