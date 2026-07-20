"""Desktop composition root for the explicit-consent Personal Memory Vault."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from future_assistant.memory import MemoryFact, MemoryService, SQLiteMemoryStore

from . import window as legacy
from .verified_window import DesktopVoiceController, VerifiedDesktopApi

_CLEAR_TTL_SECONDS = 60


def _fact_public(fact: MemoryFact) -> dict[str, object]:
    return {
        "id": fact.id,
        "statement": fact.statement,
        "category": fact.category.value,
        "source": fact.source,
        "created_at": fact.created_at.astimezone(UTC).isoformat(),
        "updated_at": fact.updated_at.astimezone(UTC).isoformat(),
    }


class MemoryDesktopApi(VerifiedDesktopApi):
    """Verified desktop API extended with transparent, explicit memory controls."""

    def __init__(self, runtime: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(runtime, *args, **kwargs)
        self._memory = MemoryService(SQLiteMemoryStore(runtime.config.memory_path))
        self._clear_handle: str | None = None
        self._clear_expires_at: datetime | None = None

    def bind_window(self, window: Any) -> None:
        super().bind_window(window)

        def inject_memory_assets(*_: object) -> None:
            window.evaluate_js(
                """
                (() => {
                  if (!document.querySelector('link[data-rayluno-memory-v2]')) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = 'memory_v2.css';
                    link.dataset.raylunoMemoryV2 = 'true';
                    document.head.append(link);
                  }
                  if (!document.querySelector('script[data-rayluno-memory-v2]')) {
                    const script = document.createElement('script');
                    script.src = 'memory_v2.js';
                    script.dataset.raylunoMemoryV2 = 'true';
                    document.body.append(script);
                  }
                })();
                """
            )

        window.events.loaded += inject_memory_assets

    def get_snapshot(self) -> dict[str, object]:
        snapshot = super().get_snapshot()
        snapshot["memory"] = self.get_memory_snapshot()
        return snapshot

    def get_memory_snapshot(self) -> dict[str, object]:
        try:
            facts = tuple(self._memory.list(limit=100))
            return {
                "available": True,
                "consent_mode": "explicit_only",
                "storage": "local_sqlite",
                "count": len(facts),
                "items": [_fact_public(fact) for fact in facts],
                "clear_pending": self._clear_public(),
            }
        except Exception as exc:
            return {
                "available": False,
                "consent_mode": "explicit_only",
                "storage": "local_sqlite",
                "count": 0,
                "items": [],
                "clear_pending": None,
                "error": type(exc).__name__,
            }

    def forget_memory(self, memory_id: object) -> dict[str, object]:
        if isinstance(memory_id, bool):
            return self._memory_error("invalid_memory_id")
        try:
            parsed_id = int(memory_id)
        except (TypeError, ValueError):
            return self._memory_error("invalid_memory_id")
        with self._execution_lock:
            fact = self._memory.forget(parsed_id)
        if fact is None:
            return self._memory_error("memory_not_found")
        snapshot = self.get_memory_snapshot()
        self.emit({"memory": snapshot})
        return {"ok": True, "deleted_id": fact.id, "memory": snapshot}

    def request_memory_clear(self) -> dict[str, object]:
        now = datetime.now(UTC)
        self._clear_handle = secrets.token_urlsafe(18)
        self._clear_expires_at = now + timedelta(seconds=_CLEAR_TTL_SECONDS)
        return {
            "ok": True,
            "confirmation_id": self._clear_handle,
            "expires_at": self._clear_expires_at.isoformat(),
            "count": len(self._memory.list(limit=200)),
        }

    def confirm_memory_clear(self, confirmation_id: object) -> dict[str, object]:
        handle = self._clear_handle
        expires_at = self._clear_expires_at
        if not isinstance(confirmation_id, str) or handle is None or expires_at is None:
            return self._memory_error("invalid_clear_confirmation")
        if datetime.now(UTC) >= expires_at:
            self._consume_clear_handle()
            return self._memory_error("clear_confirmation_expired")
        if not secrets.compare_digest(handle, confirmation_id.strip()):
            return self._memory_error("invalid_clear_confirmation")
        self._consume_clear_handle()
        with self._execution_lock:
            deleted = self._memory.clear()
        snapshot = self.get_memory_snapshot()
        self.emit({"memory": snapshot})
        return {"ok": True, "deleted_count": deleted, "memory": snapshot}

    def cancel_memory_clear(self, confirmation_id: object) -> dict[str, object]:
        handle = self._clear_handle
        if not isinstance(confirmation_id, str) or handle is None:
            return self._memory_error("invalid_clear_confirmation")
        if not secrets.compare_digest(handle, confirmation_id.strip()):
            return self._memory_error("invalid_clear_confirmation")
        self._consume_clear_handle()
        return {"ok": True, "cancelled": True, "memory": self.get_memory_snapshot()}

    def _clear_public(self) -> dict[str, object] | None:
        handle = self._clear_handle
        expires_at = self._clear_expires_at
        if handle is None or expires_at is None:
            return None
        if datetime.now(UTC) >= expires_at:
            self._consume_clear_handle()
            return None
        return {
            "confirmation_id": handle,
            "expires_at": expires_at.isoformat(),
        }

    def _consume_clear_handle(self) -> None:
        self._clear_handle = None
        self._clear_expires_at = None

    @staticmethod
    def _memory_error(code: str) -> dict[str, object]:
        return {"ok": False, "error": code}


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the legacy window with MemoryDesktopApi as the final composition root."""

    original_api = legacy.DesktopApi
    legacy.DesktopApi = MemoryDesktopApi
    try:
        legacy.start_desktop(*args, **kwargs)
    finally:
        legacy.DesktopApi = original_api


__all__ = [
    "DesktopVoiceController",
    "MemoryDesktopApi",
    "start_desktop",
]
