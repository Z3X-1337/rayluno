"""Today and verified-execution extensions for the existing desktop bridge.

The composition wrapper keeps personal state and security receipts out of the legacy desktop
module while preserving its public API.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from future_assistant.domain import RuntimeResult, RuntimeStatus
from future_assistant.reminders import (
    AgendaService,
    AgendaSnapshot,
    Reminder,
    ReminderService,
    SQLiteReminderStore,
)
from future_assistant.tasks import SQLiteTaskStore, Task, TaskPriority, TaskService

from . import window as legacy

DesktopVoiceController = legacy.DesktopVoiceController


def _task_public(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority.value,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "completed": task.completed_at is not None,
    }


def _reminder_public(reminder: Reminder) -> dict[str, object]:
    return {
        "id": reminder.id,
        "title": reminder.title,
        "priority": reminder.priority.value,
        "due_at": reminder.due_at.astimezone().isoformat(),
        "delivered": reminder.delivered_at is not None,
        "snooze_count": reminder.snooze_count,
    }


def _manifest_public(manifest: Any) -> dict[str, object]:
    return {
        "skill_id": str(manifest.skill_id),
        "permission": str(manifest.permission),
        "risk": str(manifest.risk.value),
        "confirmation": str(manifest.confirmation.value),
    }


def _receipt_public(receipt: Any) -> dict[str, object]:
    return {
        "schema": str(receipt.schema),
        "receipt_id": str(receipt.receipt_id),
        "timestamp": str(receipt.timestamp),
        "event": str(receipt.event),
        "skill_id": str(receipt.skill_id),
        "permission": str(receipt.permission),
        "risk": str(receipt.risk),
        "status": str(receipt.status),
        "confirmation_state": str(receipt.confirmation_state),
        "policy_reason": str(receipt.policy_reason),
        "action": dict(receipt.action),
        "argument_keys": list(receipt.argument_keys),
        "argument_digest": str(receipt.argument_digest),
        "previous_hash": str(receipt.previous_hash),
        "receipt_hash": str(receipt.receipt_hash),
    }


def _personal_focus(snapshot: AgendaSnapshot) -> dict[str, object] | None:
    candidates: list[tuple[str, Task | Reminder]] = [
        *(
            ("reminder", reminder)
            for reminder in (*snapshot.overdue_reminders, *snapshot.due_now_reminders)
        ),
        *(("task", task) for task in (*snapshot.overdue_tasks, *snapshot.today_tasks)),
    ]
    if not candidates:
        return None
    priority_order = {TaskPriority.HIGH: 0, TaskPriority.NORMAL: 1, TaskPriority.LOW: 2}
    candidates.sort(key=lambda item: (priority_order[item[1].priority], item[1].id))
    kind, item = candidates[0]
    payload = _reminder_public(item) if isinstance(item, Reminder) else _task_public(item)
    payload["kind"] = kind
    return payload


def build_personal_snapshot(
    agenda: AgendaService,
    reminders: ReminderService,
) -> dict[str, object]:
    snapshot = agenda.snapshot()
    pending_reminders = tuple(reminders.list(limit=20))
    agenda_items: list[dict[str, object]] = []
    for task in (*snapshot.overdue_tasks, *snapshot.today_tasks, *snapshot.unscheduled_tasks):
        item = _task_public(task)
        item["kind"] = "task"
        agenda_items.append(item)
        if len(agenda_items) == 5:
            break
    return {
        "available": True,
        "generated_at": snapshot.generated_at.astimezone().isoformat(),
        "counts": {
            "overdue": len(snapshot.overdue_tasks) + len(snapshot.overdue_reminders),
            "today": len(snapshot.today_tasks),
            "due_soon": len(snapshot.due_now_reminders),
            "later": len(snapshot.upcoming_reminders),
            "unscheduled": len(snapshot.unscheduled_tasks),
        },
        "focus": _personal_focus(snapshot),
        "next_reminder": _reminder_public(pending_reminders[0]) if pending_reminders else None,
        "items": agenda_items,
        "privacy": "local",
    }


def build_due_reminder_events(reminders: ReminderService) -> list[dict[str, object]]:
    return [
        {
            "id": event.reminder.id,
            "title": event.reminder.title,
            "priority": event.reminder.priority.value,
            "due_at": event.reminder.due_at.astimezone().isoformat(),
            "occurred_at": event.occurred_at.astimezone().isoformat(),
        }
        for event in reminders.poll_due(limit=10)
    ]


class TodayDesktopApi(legacy.DesktopApi):
    """Desktop API extended with Today data and verifiable execution state."""

    def __init__(
        self,
        runtime: Any,
        *args: Any,
        personal_clock: Callable[[], datetime] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(runtime, *args, **kwargs)
        config = runtime.config
        self._personal_tasks = TaskService(
            SQLiteTaskStore(config.tasks_path),
            clock=personal_clock,
        )
        self._personal_reminders = ReminderService(
            SQLiteReminderStore(config.reminders_path),
            clock=personal_clock,
        )
        self._personal_agenda = AgendaService(
            self._personal_tasks,
            self._personal_reminders,
            clock=personal_clock,
        )

    def get_snapshot(self) -> dict[str, object]:
        snapshot = super().get_snapshot()
        snapshot["personal"] = self.get_personal_snapshot()
        snapshot["verified"] = self.get_verified_snapshot()
        return snapshot

    def get_personal_snapshot(self) -> dict[str, object]:
        try:
            return build_personal_snapshot(self._personal_agenda, self._personal_reminders)
        except Exception:
            return {
                "available": False,
                "counts": {
                    "overdue": 0,
                    "today": 0,
                    "due_soon": 0,
                    "later": 0,
                    "unscheduled": 0,
                },
                "focus": None,
                "next_reminder": None,
                "items": [],
                "privacy": "local",
            }

    def get_verified_snapshot(self) -> dict[str, object]:
        try:
            engine = self.runtime.skill_engine
            manifests = engine.registry.manifests
            pending = self.runtime.pending_public()
            ledger = self.runtime.receipt_ledger
            receipts = tuple(getattr(ledger, "receipts", ()))
            integrity_ok = bool(self.runtime.receipt_integrity_ok)
            return {
                "available": integrity_ok,
                "integrity_ok": integrity_ok,
                "integrity_error": getattr(ledger, "integrity_error", None),
                "skills": [_manifest_public(manifest) for manifest in manifests],
                "pending": pending,
                "receipts": [_receipt_public(receipt) for receipt in reversed(receipts[-5:])],
                "receipt_count": len(receipts),
                "chain_head": receipts[-1].receipt_hash if receipts else None,
                "privacy": "local",
            }
        except Exception as exc:
            return {
                "available": False,
                "integrity_ok": False,
                "integrity_error": type(exc).__name__,
                "skills": [],
                "pending": None,
                "receipts": [],
                "receipt_count": 0,
                "chain_head": None,
                "privacy": "local",
            }

    def get_verified_receipts(self, limit: object = 20) -> dict[str, object]:
        try:
            parsed_limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            parsed_limit = 20
        snapshot = self.get_verified_snapshot()
        try:
            receipts = tuple(getattr(self.runtime.receipt_ledger, "receipts", ()))
            public_receipts = [
                _receipt_public(receipt) for receipt in reversed(receipts[-parsed_limit:])
            ]
        except Exception:
            public_receipts = []
        return {
            "ok": bool(snapshot["integrity_ok"]),
            "integrity_ok": bool(snapshot["integrity_ok"]),
            "integrity_error": snapshot.get("integrity_error"),
            "receipts": public_receipts,
            "receipt_count": snapshot.get("receipt_count", 0),
            "chain_head": snapshot.get("chain_head"),
        }

    def approve_skill(self, confirmation_id: object) -> dict[str, object]:
        return self._resolve_confirmation(confirmation_id, approve=True)

    def reject_skill(self, confirmation_id: object) -> dict[str, object]:
        return self._resolve_confirmation(confirmation_id, approve=False)

    def poll_due_reminders(self) -> dict[str, object]:
        try:
            return {"ok": True, "events": build_due_reminder_events(self._personal_reminders)}
        except Exception:
            return {"ok": False, "events": []}

    def _resolve_confirmation(
        self,
        confirmation_id: object,
        *,
        approve: bool,
    ) -> dict[str, object]:
        if not isinstance(confirmation_id, str) or not confirmation_id.strip():
            return {
                "ok": False,
                "status": RuntimeStatus.BLOCKED.value,
                "message": "معرّف التأكيد غير صالح.",
                "action": "blocked",
                "verified": True,
            }
        with self._execution_lock:
            result = (
                self.runtime.approve(confirmation_id.strip())
                if approve
                else self.runtime.reject(confirmation_id.strip())
            )
        payload = self._result_payload(result, "")
        with self._history_lock:
            self._history.insert(0, payload)
            del self._history[20:]
        self.emit(
            {
                "verified_resolution": payload,
                "verified_status": self.get_verified_snapshot(),
            }
        )
        return dict(payload)

    def _result_payload(self, result: RuntimeResult, command: str) -> dict[str, object]:
        payload = super()._result_payload(result, command)
        payload["verified"] = True
        payload["integrity_ok"] = bool(self.runtime.receipt_integrity_ok)
        if result.status is RuntimeStatus.CONFIRMATION_REQUIRED:
            payload["ok"] = True
            pending = self.runtime.pending_public()
            if pending is not None:
                payload["confirmation"] = pending
        receipts = tuple(getattr(self.runtime, "last_receipts", ()))
        if receipts:
            payload["receipt"] = _receipt_public(receipts[-1])
            payload["receipts"] = [_receipt_public(receipt) for receipt in receipts]
        return payload


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the existing window with TodayDesktopApi as its composition-root bridge."""

    original_api = legacy.DesktopApi
    legacy.DesktopApi = TodayDesktopApi
    try:
        legacy.start_desktop(*args, **kwargs)
    finally:
        legacy.DesktopApi = original_api
