"""Private local task management for the personal assistant.

The task subsystem is deliberately independent from voice, UI, and model providers.
It persists only user-authored task data in a local SQLite database and exposes a
small service API that can be replaced with an in-memory store in tests.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .identity import COMPATIBILITY_DATA_DIRECTORY

_MAX_TITLE_LENGTH = 240


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class Task:
    id: int
    title: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    due_date: date | None = None
    completed_at: datetime | None = None


class TaskStore(Protocol):
    def create(
        self,
        title: str,
        *,
        priority: TaskPriority,
        due_date: date | None,
        created_at: datetime,
    ) -> Task: ...

    def list(self, *, include_completed: bool = False, limit: int = 20) -> Sequence[Task]: ...

    def complete(self, task_id: int, *, completed_at: datetime) -> Task | None: ...

    def delete(self, task_id: int) -> Task | None: ...


def default_tasks_path() -> Path:
    """Return the private per-user task database path."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / COMPATIBILITY_DATA_DIRECTORY / "tasks.sqlite3"


def _clean_title(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Task title must be text.")
    title = " ".join(value.strip().split())
    if not title or len(title) > _MAX_TITLE_LENGTH:
        raise ValueError(f"Task title must contain 1-{_MAX_TITLE_LENGTH} characters.")
    if any(ord(character) < 32 for character in title):
        raise ValueError("Task title cannot contain control characters.")
    return title


def _datetime_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteTaskStore:
    """Small transactional task store; the database is opened only on first use."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if not self._initialized:
            self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 240),
                priority TEXT NOT NULL CHECK(priority IN ('low', 'normal', 'high')),
                status TEXT NOT NULL CHECK(status IN ('pending', 'completed')),
                created_at TEXT NOT NULL,
                due_date TEXT,
                completed_at TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_date, id)"
        )
        connection.commit()
        self._initialized = True

    @staticmethod
    def _task(row: sqlite3.Row) -> Task:
        return Task(
            id=int(row["id"]),
            title=str(row["title"]),
            priority=TaskPriority(str(row["priority"])),
            status=TaskStatus(str(row["status"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            due_date=date.fromisoformat(str(row["due_date"])) if row["due_date"] else None,
            completed_at=_parse_datetime(row["completed_at"]),
        )

    def create(
        self,
        title: str,
        *,
        priority: TaskPriority,
        due_date: date | None,
        created_at: datetime,
    ) -> Task:
        clean_title = _clean_title(title)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks(title, priority, status, created_at, due_date, completed_at)
                VALUES (?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    clean_title,
                    priority.value,
                    _datetime_text(created_at),
                    due_date.isoformat() if due_date else None,
                ),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Created task could not be read back.")
        return self._task(row)

    def list(self, *, include_completed: bool = False, limit: int = 20) -> Sequence[Task]:
        bounded_limit = max(1, min(int(limit), 100))
        clause = "" if include_completed else "WHERE status = 'pending'"
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM tasks
                {clause}
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC,
                    id ASC
                LIMIT ?
                """,  # noqa: S608 - clause is selected from two fixed literals above
                (bounded_limit,),
            ).fetchall()
        return tuple(self._task(row) for row in rows)

    def complete(self, task_id: int, *, completed_at: datetime) -> Task | None:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
            return None
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks
                SET status = 'completed', completed_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (_datetime_text(completed_at), task_id),
            )
            if cursor.rowcount != 1:
                connection.commit()
                return None
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("Completed task could not be read back.")
        return self._task(row)

    def delete(self, task_id: int) -> Task | None:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
            return None
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            connection.commit()
        return self._task(row)


class InMemoryTaskStore:
    """Deterministic test store with the same semantics as SQLiteTaskStore."""

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id = 1

    def create(
        self,
        title: str,
        *,
        priority: TaskPriority,
        due_date: date | None,
        created_at: datetime,
    ) -> Task:
        task = Task(
            self._next_id,
            _clean_title(title),
            priority,
            TaskStatus.PENDING,
            created_at,
            due_date,
        )
        self._tasks[task.id] = task
        self._next_id += 1
        return task

    def list(self, *, include_completed: bool = False, limit: int = 20) -> Sequence[Task]:
        tasks = [
            task
            for task in self._tasks.values()
            if include_completed or task.status is TaskStatus.PENDING
        ]
        priority_order = {TaskPriority.HIGH: 0, TaskPriority.NORMAL: 1, TaskPriority.LOW: 2}
        tasks.sort(
            key=lambda task: (
                priority_order[task.priority],
                task.due_date is None,
                task.due_date or date.max,
                task.id,
            )
        )
        return tuple(tasks[: max(1, min(int(limit), 100))])

    def complete(self, task_id: int, *, completed_at: datetime) -> Task | None:
        task = self._tasks.get(task_id)
        if task is None or task.status is TaskStatus.COMPLETED:
            return None
        completed = Task(
            task.id,
            task.title,
            task.priority,
            TaskStatus.COMPLETED,
            task.created_at,
            task.due_date,
            completed_at,
        )
        self._tasks[task_id] = completed
        return completed

    def delete(self, task_id: int) -> Task | None:
        return self._tasks.pop(task_id, None)


class TaskService:
    def __init__(
        self,
        store: TaskStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))

    def create(self, title: str, *, priority: str = "normal", due: str | None = None) -> Task:
        parsed_priority = TaskPriority(priority)
        now = self.clock()
        due_date = self._resolve_due_date(due, now.date())
        return self.store.create(
            title,
            priority=parsed_priority,
            due_date=due_date,
            created_at=now,
        )

    def list(self, *, include_completed: bool = False, limit: int = 10) -> Sequence[Task]:
        return self.store.list(include_completed=include_completed, limit=limit)

    def complete(self, task_id: int) -> Task | None:
        return self.store.complete(task_id, completed_at=self.clock())

    def delete(self, task_id: int) -> Task | None:
        return self.store.delete(task_id)

    @staticmethod
    def _resolve_due_date(value: str | None, today: date) -> date | None:
        if value is None or value == "none":
            return None
        if value == "today":
            return today
        if value == "tomorrow":
            return today + timedelta(days=1)
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported task due date.") from error
        if parsed < today:
            raise ValueError("Task due date cannot be in the past.")
        return parsed
