from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from future_assistant.actions import ActionFactory
from future_assistant.agenda_commands import AgendaCommandPlanner
from future_assistant.config import AssistantConfig
from future_assistant.reminders import (
    AgendaService,
    InMemoryReminderStore,
    ReminderService,
    SQLiteReminderStore,
)
from future_assistant.router import DeterministicRouter
from future_assistant.tasks import InMemoryTaskStore, TaskService

JO = timezone(timedelta(hours=3))


def _services(now: datetime):  # noqa: ANN001
    def clock() -> datetime:
        return now

    tasks = TaskService(InMemoryTaskStore(), clock=clock)
    reminders = ReminderService(InMemoryReminderStore(), clock=clock)
    agenda = AgendaService(tasks, reminders, clock=clock)
    return tasks, reminders, agenda


def test_relative_and_absolute_reminders_are_bilingual() -> None:
    now = datetime(2026, 7, 20, 15, 0, tzinfo=JO)
    _, reminders, agenda = _services(now)
    planner = AgendaCommandPlanner(reminders, agenda)

    arabic = planner.plan("ذكرني بعد عشر دقائق ارسل التقرير", "ذكرني بعد عشر دقائق ارسل التقرير")
    english = planner.plan(
        "remind me at 6 pm to call the team high priority",
        "remind me at 6 pm to call the team high priority",
    )

    assert arabic is not None and "رقم 1" in str(arabic.reply)
    assert english is not None and "reminder 2" in str(english.reply)
    items = reminders.list()
    assert items[0].due_at == datetime(2026, 7, 20, 12, 10, tzinfo=UTC)
    assert items[1].due_at == datetime(2026, 7, 20, 15, 0, tzinfo=UTC)
    assert items[1].priority.value == "high"


def test_scheduler_delivers_once_then_snooze_rearms() -> None:
    current = [datetime(2026, 7, 20, 12, 0, tzinfo=UTC)]
    service = ReminderService(InMemoryReminderStore(), clock=lambda: current[0])
    reminder = service.create_after("send report", minutes=10)

    current[0] += timedelta(minutes=10)
    first = service.poll_due()
    second = service.poll_due()
    snoozed = service.snooze(reminder.id, 5)
    current[0] += timedelta(minutes=5)
    third = service.poll_due()

    assert [event.reminder.id for event in first] == [reminder.id]
    assert second == ()
    assert snoozed is not None and snoozed.snooze_count == 1
    assert [event.reminder.id for event in third] == [reminder.id]


def test_daily_agenda_prioritizes_overdue_and_due_soon() -> None:
    now = datetime(2026, 7, 20, 9, 0, tzinfo=JO)
    tasks, reminders, agenda = _services(now)
    tasks.create("review demo", priority="high", due="today")
    reminders.create_after("send build", minutes=10, priority="normal")
    planner = AgendaCommandPlanner(reminders, agenda)

    result = planner.plan("ما خطتي اليوم", "ما خطتي اليوم")

    assert result is not None
    assert "1 مهام اليوم" in str(result.reply)
    assert "1 تذكيرات قريبة" in str(result.reply)
    assert "ابدأ بـ: review demo" in str(result.reply)


def test_snooze_and_complete_commands() -> None:
    now = datetime(2026, 7, 20, 9, 0, tzinfo=JO)
    _, reminders, agenda = _services(now)
    reminder = reminders.create_after("call team", minutes=5)
    planner = AgendaCommandPlanner(reminders, agenda)

    snoozed = planner.plan("اجل التذكير رقم 1 عشر دقائق", "اجل التذكير رقم 1 عشر دقائق")
    completed = planner.plan("complete reminder 1", "complete reminder 1")

    assert snoozed is not None and "10 دقيقة" in str(snoozed.reply)
    assert completed is not None and "completed reminder 1" in str(completed.reply)
    assert reminders.list() == ()
    assert reminder.id == 1


def test_sqlite_reminder_store_persists_delivery_and_snooze(tmp_path) -> None:  # noqa: ANN001
    now = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    service = ReminderService(
        SQLiteReminderStore(tmp_path / "reminders.sqlite3"), clock=lambda: now
    )
    reminder = service.create_after("test", minutes=1)

    later = ReminderService(
        SQLiteReminderStore(tmp_path / "reminders.sqlite3"),
        clock=lambda: now + timedelta(minutes=1),
    )
    events = later.poll_due()
    snoozed = later.snooze(reminder.id, 5)

    assert len(events) == 1
    assert later.poll_due() == ()
    assert snoozed is not None and snoozed.delivered_at is None


def test_router_checks_reminders_before_generic_task_remind_me(tmp_path) -> None:  # noqa: ANN001
    now = datetime(2026, 7, 20, 9, 0, tzinfo=JO)
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
    )
    router = DeterministicRouter(ActionFactory(config), clock=lambda: now)

    timed = router.route("ذكرني بعد عشر دقائق ارسل التقرير")
    untimed = router.route("ذكرني ان اراجع التقرير")

    assert timed is not None and "التذكير رقم" in str(timed.reply)
    assert untimed is not None and "المهمة رقم" in str(untimed.reply)
