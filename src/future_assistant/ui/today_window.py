"""Today command-center extension for the existing desktop bridge.

The extension keeps personal task/reminder state out of the legacy desktop module while
preserving its public API. The composition wrapper temporarily substitutes the enhanced
API only while the desktop window is running.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

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
    """Desktop API extended with structured local Today data and reminder events."""

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

    def poll_due_reminders(self) -> dict[str, object]:
        try:
            return {"ok": True, "events": build_due_reminder_events(self._personal_reminders)}
        except Exception:
            return {"ok": False, "events": []}


def start_desktop(*args: Any, **kwargs: Any) -> None:
    """Run the existing window with TodayDesktopApi as its composition-root bridge."""

    original_api = legacy.DesktopApi
    legacy.DesktopApi = TodayDesktopApi
    try:
        legacy.start_desktop(*args, **kwargs)
    finally:
        legacy.DesktopApi = original_api
