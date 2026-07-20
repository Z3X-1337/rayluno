"""Local reminder scheduling and daily-agenda domain services."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .identity import COMPATIBILITY_DATA_DIRECTORY
from .local_security import secure_directory, secure_file
from .tasks import Task, TaskPriority, TaskService

_MAX_TITLE_LENGTH = 240
_MAX_SNOOZE_MINUTES = 24 * 60


class ReminderStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class Reminder:
    id: int
    title: str
    due_at: datetime
    priority: TaskPriority
    status: ReminderStatus
    created_at: datetime
    delivered_at: datetime | None = None
    completed_at: datetime | None = None
    snooze_count: int = 0


@dataclass(frozen=True, slots=True)
class ReminderEvent:
    reminder: Reminder
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AgendaSnapshot:
    generated_at: datetime
    overdue_tasks: tuple[Task, ...]
    today_tasks: tuple[Task, ...]
    unscheduled_tasks: tuple[Task, ...]
    overdue_reminders: tuple[Reminder, ...]
    due_now_reminders: tuple[Reminder, ...]
    upcoming_reminders: tuple[Reminder, ...]


class ReminderStore(Protocol):
    def create(
        self,
        title: str,
        *,
        due_at: datetime,
        priority: TaskPriority,
        created_at: datetime,
    ) -> Reminder: ...

    def list(self, *, include_completed: bool = False, limit: int = 50) -> Sequence[Reminder]: ...

    def due(self, *, now: datetime, limit: int = 20) -> Sequence[Reminder]: ...

    def mark_delivered(self, reminder_id: int, *, delivered_at: datetime) -> Reminder | None: ...

    def complete(self, reminder_id: int, *, completed_at: datetime) -> Reminder | None: ...

    def snooze(self, reminder_id: int, *, due_at: datetime) -> Reminder | None: ...


def default_reminders_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / COMPATIBILITY_DATA_DIRECTORY / "reminders.sqlite3"


def _clean_title(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Reminder title must be text.")
    title = " ".join(value.strip().split())
    if not title or len(title) > _MAX_TITLE_LENGTH:
        raise ValueError(f"Reminder title must contain 1-{_MAX_TITLE_LENGTH} characters.")
    if any(ord(character) < 32 for character in title):
        raise ValueError("Reminder title cannot contain control characters.")
    return title


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _datetime_text(value: datetime) -> str:
    return _aware(value).astimezone(UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteReminderStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        secure_directory(self.path.parent)
        connection = sqlite3.connect(self.path, timeout=5.0)
        secure_file(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        if not self._initialized:
            self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 240),
                due_at TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('low', 'normal', 'high')),
                status TEXT NOT NULL CHECK(status IN ('pending', 'completed')),
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                completed_at TEXT,
                snooze_count INTEGER NOT NULL DEFAULT 0 CHECK(snooze_count >= 0)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_due "
            "ON reminders(status, due_at, delivered_at, id)"
        )
        connection.commit()
        self._initialized = True

    @staticmethod
    def _reminder(row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=int(row["id"]),
            title=str(row["title"]),
            due_at=datetime.fromisoformat(str(row["due_at"])),
            priority=TaskPriority(str(row["priority"])),
            status=ReminderStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            delivered_at=_parse_datetime(row["delivered_at"]),
            completed_at=_parse_datetime(row["completed_at"]),
            snooze_count=int(row["snooze_count"]),
        )

    def create(
        self,
        title: str,
        *,
        due_at: datetime,
        priority: TaskPriority,
        created_at: datetime,
    ) -> Reminder:
        clean_title = _clean_title(title)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reminders(
                    title, due_at, priority, status, created_at,
                    delivered_at, completed_at, snooze_count
                ) VALUES (?, ?, ?, 'pending', ?, NULL, NULL, 0)
                """,
                (
                    clean_title,
                    _datetime_text(due_at),
                    priority.value,
                    _datetime_text(created_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Created reminder could not be read back.")
        return self._reminder(row)

    def list(self, *, include_completed: bool = False, limit: int = 50) -> Sequence[Reminder]:
        bounded = max(1, min(int(limit), 200))
        clause = "" if include_completed else "WHERE status = 'pending'"
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM reminders
                {clause}
                ORDER BY due_at ASC, id ASC
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return tuple(self._reminder(row) for row in rows)

    def due(self, *, now: datetime, limit: int = 20) -> Sequence[Reminder]:
        bounded = max(1, min(int(limit), 100))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM reminders
                WHERE status = 'pending'
                  AND delivered_at IS NULL
                  AND due_at <= ?
                ORDER BY due_at ASC, id ASC
                LIMIT ?
                """,
                (_datetime_text(now), bounded),
            ).fetchall()
        return tuple(self._reminder(row) for row in rows)

    def mark_delivered(self, reminder_id: int, *, delivered_at: datetime) -> Reminder | None:
        if isinstance(reminder_id, bool) or not isinstance(reminder_id, int) or reminder_id < 1:
            return None
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET delivered_at = ?
                WHERE id = ? AND status = 'pending' AND delivered_at IS NULL
                """,
                (_datetime_text(delivered_at), reminder_id),
            )
            if cursor.rowcount != 1:
                connection.commit()
                return None
            row = connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
            connection.commit()
        return self._reminder(row) if row is not None else None

    def complete(self, reminder_id: int, *, completed_at: datetime) -> Reminder | None:
        if isinstance(reminder_id, bool) or not isinstance(reminder_id, int) or reminder_id < 1:
            return None
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET status = 'completed', completed_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (_datetime_text(completed_at), reminder_id),
            )
            if cursor.rowcount != 1:
                connection.commit()
                return None
            row = connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
            connection.commit()
        return self._reminder(row) if row is not None else None

    def snooze(self, reminder_id: int, *, due_at: datetime) -> Reminder | None:
        if isinstance(reminder_id, bool) or not isinstance(reminder_id, int) or reminder_id < 1:
            return None
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET due_at = ?, delivered_at = NULL, snooze_count = snooze_count + 1
                WHERE id = ? AND status = 'pending'
                """,
                (_datetime_text(due_at), reminder_id),
            )
            if cursor.rowcount != 1:
                connection.commit()
                return None
            row = connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
            connection.commit()
        return self._reminder(row) if row is not None else None


class InMemoryReminderStore:
    def __init__(self) -> None:
        self._items: dict[int, Reminder] = {}
        self._next_id = 1

    def create(
        self,
        title: str,
        *,
        due_at: datetime,
        priority: TaskPriority,
        created_at: datetime,
    ) -> Reminder:
        reminder = Reminder(
            self._next_id,
            _clean_title(title),
            _aware(due_at).astimezone(UTC),
            priority,
            ReminderStatus.PENDING,
            _aware(created_at).astimezone(UTC),
        )
        self._items[reminder.id] = reminder
        self._next_id += 1
        return reminder

    def list(self, *, include_completed: bool = False, limit: int = 50) -> Sequence[Reminder]:
        items = [
            item
            for item in self._items.values()
            if include_completed or item.status is ReminderStatus.PENDING
        ]
        items.sort(key=lambda item: (item.due_at, item.id))
        return tuple(items[: max(1, min(int(limit), 200))])

    def due(self, *, now: datetime, limit: int = 20) -> Sequence[Reminder]:
        current = _aware(now).astimezone(UTC)
        items = [
            item
            for item in self._items.values()
            if item.status is ReminderStatus.PENDING
            and item.delivered_at is None
            and item.due_at <= current
        ]
        items.sort(key=lambda item: (item.due_at, item.id))
        return tuple(items[: max(1, min(int(limit), 100))])

    def mark_delivered(self, reminder_id: int, *, delivered_at: datetime) -> Reminder | None:
        item = self._items.get(reminder_id)
        if item is None or item.status is ReminderStatus.COMPLETED or item.delivered_at is not None:
            return None
        updated = replace(item, delivered_at=_aware(delivered_at).astimezone(UTC))
        self._items[reminder_id] = updated
        return updated

    def complete(self, reminder_id: int, *, completed_at: datetime) -> Reminder | None:
        item = self._items.get(reminder_id)
        if item is None or item.status is ReminderStatus.COMPLETED:
            return None
        updated = replace(
            item,
            status=ReminderStatus.COMPLETED,
            completed_at=_aware(completed_at).astimezone(UTC),
        )
        self._items[reminder_id] = updated
        return updated

    def snooze(self, reminder_id: int, *, due_at: datetime) -> Reminder | None:
        item = self._items.get(reminder_id)
        if item is None or item.status is ReminderStatus.COMPLETED:
            return None
        updated = replace(
            item,
            due_at=_aware(due_at).astimezone(UTC),
            delivered_at=None,
            snooze_count=item.snooze_count + 1,
        )
        self._items[reminder_id] = updated
        return updated


class ReminderService:
    def __init__(
        self,
        store: ReminderStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now().astimezone())

    def create_after(
        self,
        title: str,
        *,
        minutes: int,
        priority: str = "normal",
    ) -> Reminder:
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or not 1 <= minutes <= _MAX_SNOOZE_MINUTES
        ):
            raise ValueError("Reminder delay must be between 1 minute and 24 hours.")
        now = _aware(self.clock())
        return self.store.create(
            title,
            due_at=now + timedelta(minutes=minutes),
            priority=TaskPriority(priority),
            created_at=now,
        )

    def create_at(
        self,
        title: str,
        *,
        hour: int,
        minute: int = 0,
        priority: str = "normal",
    ) -> Reminder:
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("Reminder hour must be between 0 and 23.")
        if isinstance(minute, bool) or not isinstance(minute, int) or not 0 <= minute <= 59:
            raise ValueError("Reminder minute must be between 0 and 59.")
        now = _aware(self.clock())
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
        return self.store.create(
            title,
            due_at=due,
            priority=TaskPriority(priority),
            created_at=now,
        )

    def list(self, *, include_completed: bool = False, limit: int = 20) -> Sequence[Reminder]:
        return self.store.list(include_completed=include_completed, limit=limit)

    def complete(self, reminder_id: int) -> Reminder | None:
        return self.store.complete(reminder_id, completed_at=_aware(self.clock()))

    def snooze(self, reminder_id: int, minutes: int) -> Reminder | None:
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or not 1 <= minutes <= _MAX_SNOOZE_MINUTES
        ):
            raise ValueError("Snooze duration must be between 1 minute and 24 hours.")
        return self.store.snooze(
            reminder_id, due_at=_aware(self.clock()) + timedelta(minutes=minutes)
        )

    def poll_due(self, *, limit: int = 20) -> tuple[ReminderEvent, ...]:
        now = _aware(self.clock())
        events: list[ReminderEvent] = []
        for reminder in self.store.due(now=now, limit=limit):
            delivered = self.store.mark_delivered(reminder.id, delivered_at=now)
            if delivered is not None:
                events.append(ReminderEvent(delivered, now))
        return tuple(events)


class AgendaService:
    def __init__(
        self,
        tasks: TaskService,
        reminders: ReminderService,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.tasks = tasks
        self.reminders = reminders
        self.clock = clock or reminders.clock

    def snapshot(self) -> AgendaSnapshot:
        now = _aware(self.clock())
        today = now.date()
        pending_tasks = tuple(self.tasks.list(limit=100))
        pending_reminders = tuple(self.reminders.list(limit=100))
        overdue_tasks = tuple(
            task for task in pending_tasks if task.due_date and task.due_date < today
        )
        today_tasks = tuple(task for task in pending_tasks if task.due_date == today)
        unscheduled_tasks = tuple(task for task in pending_tasks if task.due_date is None)
        overdue_reminders = tuple(item for item in pending_reminders if item.due_at < now)
        due_now_reminders = tuple(
            item for item in pending_reminders if now <= item.due_at <= now + timedelta(minutes=15)
        )
        upcoming_reminders = tuple(
            item
            for item in pending_reminders
            if now + timedelta(minutes=15) < item.due_at and item.due_at.date() == today
        )
        return AgendaSnapshot(
            generated_at=now,
            overdue_tasks=overdue_tasks,
            today_tasks=today_tasks,
            unscheduled_tasks=unscheduled_tasks,
            overdue_reminders=overdue_reminders,
            due_now_reminders=due_now_reminders,
            upcoming_reminders=upcoming_reminders,
        )
