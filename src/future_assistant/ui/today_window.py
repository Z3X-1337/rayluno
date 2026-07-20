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
        "receipt_id": str(receipt.receipt_id),
        "timestamp": str(receipt.timestamp),
        "skill_id": str(receipt.skill_id),
        "permission": str(receipt.permission),
        "risk": str(receipt.risk),
        "status": str(receipt.status),
        "policy_reason": str(receipt.policy_reason),
        "action": dict(receipt.action),
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
            pending = self.runtime.pending
            ledger = self.runtime.receipt_ledger
            receipts = tuple(getattr(ledger, "receipts", ()))
            pending_manifest = None
            if pending is not None:
                assessment = next(
                    (item for item in pending.assessments if item.requires_confirmation),
                    pending.assessments[0],
                )
                pending_manifest = _manifest_public(assessment.manifest)
            return {
                "available": True,
                "skills": [_manifest_public(manifest) for manifest in manifests],
                "pending": pending_manifest,
                "receipts": [_receipt_public(receipt) for receipt in reversed(receipts[-5:])],
                "chain_head": receipts[-1].receipt_hash if receipts else None,
                "privacy": "local",
            }
        except Exception:
            return {
                "available": False,
                "skills": [],
                "pending": None,
                "receipts": [],
                "chain_head": None,
                "privacy": "local",
            }

    def poll_due_reminders(self) -> dict[str, object]:
        try:
            return {"ok": True, "events": build_due_reminder_events(self._personal_reminders)}
        except Exception:
            return {"ok": False, "events": []}

    def _result_payload(self, result: RuntimeResult, command: str) -> dict[str, object]:
        payload = super()._result_payload(result, command)
        if result.status is RuntimeStatus.CONFIRMATION_REQUIRED:
            payload["ok"] = True
            pending = getattr(self.runtime, "pending", None)
            if pending is not None:
                assessment = next(
                    (item for item in pending.assessments if item.requires_confirmation),
                    pending.assessments[0],
                )
                payload["confirmation"] = _manifest_public(assessment.manifest)
        if result.executions:
            receipts = getattr(self.runtime, "last_receipts", ())
            if receipts:
                payload["receipt"] = _receipt_public(receipts[-1])
        return payload


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the existing window with TodayDesktopApi as its composition-root bridge."""

    original_api = legacy.DesktopApi
    legacy.DesktopApi = TodayDesktopApi
    try:
        legacy.start_desktop(*args, **kwargs)
    finally:
        legacy.DesktopApi = original_api
