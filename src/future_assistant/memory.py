"""Explicit-consent personal memory stored locally on the user's device."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .identity import COMPATIBILITY_DATA_DIRECTORY

_MAX_STATEMENT_LENGTH = 280
_SOURCE_USER_EXPLICIT = "user_explicit"
_SENSITIVE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bpassword\b",
        r"\bpasscode\b",
        r"\bpin(?:\s+code)?\b",
        r"\bcvv\b",
        r"\bcredit\s+card\b",
        r"\bcard\s+number\b",
        r"\bapi[ _-]?key\b",
        r"\bsecret[ _-]?key\b",
        r"\baccess[ _-]?token\b",
        r"\brefresh[ _-]?token\b",
        r"\bprivate[ _-]?key\b",
        r"\bseed\s+phrase\b",
        r"\brecovery\s+phrase\b",
        r"كلمة\s+(?:السر|المرور)",
        r"الرقم\s+السري",
        r"رمز\s+(?:الدخول|التحقق|السري)",
        r"رقم\s+البطاقة",
        r"بطاقة\s+الائتمان",
        r"مفتاح\s+(?:api|خاص|سري)",
        r"رمز\s+الوصول",
        r"عبارة\s+(?:الاسترداد|الاستعادة)",
    )
)


class MemoryCategory(StrEnum):
    IDENTITY = "identity"
    PREFERENCE = "preference"
    CONTEXT = "context"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class MemoryFact:
    id: int
    statement: str
    category: MemoryCategory
    source: str
    fingerprint: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryWrite:
    fact: MemoryFact
    created: bool


class SensitiveMemoryError(ValueError):
    """Raised when a user asks the assistant to retain likely secret material."""


class MemoryStore(Protocol):
    def remember(
        self,
        statement: str,
        *,
        category: MemoryCategory,
        source: str,
        fingerprint: str,
        now: datetime,
    ) -> MemoryWrite: ...

    def list(self, *, limit: int = 50) -> Sequence[MemoryFact]: ...

    def forget(self, memory_id: int) -> MemoryFact | None: ...

    def clear(self) -> int: ...


def default_memory_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / COMPATIBILITY_DATA_DIRECTORY / "memory.sqlite3"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _datetime_text(value: datetime) -> str:
    return _aware_utc(value).isoformat()


def _clean_statement(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Memory statement must be text.")
    statement = " ".join(value.strip().split())
    if not statement or len(statement) > _MAX_STATEMENT_LENGTH:
        raise ValueError(
            f"Memory statement must contain 1-{_MAX_STATEMENT_LENGTH} characters."
        )
    if any(ord(character) < 32 for character in statement):
        raise ValueError("Memory statement cannot contain control characters.")
    return statement


def memory_fingerprint(statement: str) -> str:
    normalized = " ".join(statement.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def contains_sensitive_material(statement: str) -> bool:
    return any(pattern.search(statement) for pattern in _SENSITIVE_PATTERNS)


class SQLiteMemoryStore:
    """Transactional local memory store with fingerprint-based deduplication."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        if not self._initialized:
            self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                statement TEXT NOT NULL CHECK(length(statement) BETWEEN 1 AND 280),
                category TEXT NOT NULL
                    CHECK(category IN ('identity', 'preference', 'context', 'other')),
                source TEXT NOT NULL CHECK(source = 'user_explicit'),
                fingerprint TEXT NOT NULL UNIQUE CHECK(length(fingerprint) = 64),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_updated ON memory_facts(updated_at DESC, id DESC)"
        )
        connection.commit()
        self._initialized = True

    @staticmethod
    def _fact(row: sqlite3.Row) -> MemoryFact:
        return MemoryFact(
            id=int(row["id"]),
            statement=str(row["statement"]),
            category=MemoryCategory(str(row["category"])),
            source=str(row["source"]),
            fingerprint=str(row["fingerprint"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def remember(
        self,
        statement: str,
        *,
        category: MemoryCategory,
        source: str,
        fingerprint: str,
        now: datetime,
    ) -> MemoryWrite:
        clean = _clean_statement(statement)
        if source != _SOURCE_USER_EXPLICIT:
            raise ValueError("Only explicit user memories may be persisted.")
        timestamp = _datetime_text(now)
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM memory_facts WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO memory_facts(
                        statement, category, source, fingerprint, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (clean, category.value, source, fingerprint, timestamp, timestamp),
                )
                row = connection.execute(
                    "SELECT * FROM memory_facts WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                created = True
            else:
                connection.execute(
                    """
                    UPDATE memory_facts
                    SET statement = ?, category = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean, category.value, timestamp, int(existing["id"])),
                )
                row = connection.execute(
                    "SELECT * FROM memory_facts WHERE id = ?",
                    (int(existing["id"]),),
                ).fetchone()
                created = False
            connection.commit()
        if row is None:
            raise RuntimeError("Memory fact could not be read back.")
        return MemoryWrite(self._fact(row), created)

    def list(self, *, limit: int = 50) -> Sequence[MemoryFact]:
        bounded = max(1, min(int(limit), 200))
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memory_facts
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return tuple(self._fact(row) for row in rows)

    def forget(self, memory_id: int) -> MemoryFact | None:
        if isinstance(memory_id, bool) or not isinstance(memory_id, int) or memory_id < 1:
            return None
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_facts WHERE id = ?",
                (memory_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM memory_facts WHERE id = ?", (memory_id,))
            connection.commit()
        return self._fact(row)

    def clear(self) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM memory_facts")
            connection.commit()
        return max(0, int(cursor.rowcount))


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: dict[int, MemoryFact] = {}
        self._fingerprints: dict[str, int] = {}
        self._next_id = 1

    def remember(
        self,
        statement: str,
        *,
        category: MemoryCategory,
        source: str,
        fingerprint: str,
        now: datetime,
    ) -> MemoryWrite:
        clean = _clean_statement(statement)
        if source != _SOURCE_USER_EXPLICIT:
            raise ValueError("Only explicit user memories may be persisted.")
        current = _aware_utc(now)
        existing_id = self._fingerprints.get(fingerprint)
        if existing_id is not None:
            existing = self._items[existing_id]
            updated = replace(
                existing,
                statement=clean,
                category=category,
                updated_at=current,
            )
            self._items[existing_id] = updated
            return MemoryWrite(updated, False)
        fact = MemoryFact(
            self._next_id,
            clean,
            category,
            source,
            fingerprint,
            current,
            current,
        )
        self._items[fact.id] = fact
        self._fingerprints[fingerprint] = fact.id
        self._next_id += 1
        return MemoryWrite(fact, True)

    def list(self, *, limit: int = 50) -> Sequence[MemoryFact]:
        items = sorted(
            self._items.values(),
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )
        return tuple(items[: max(1, min(int(limit), 200))])

    def forget(self, memory_id: int) -> MemoryFact | None:
        item = self._items.pop(memory_id, None)
        if item is not None:
            self._fingerprints.pop(item.fingerprint, None)
        return item

    def clear(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._fingerprints.clear()
        return count


class MemoryService:
    def __init__(
        self,
        store: MemoryStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))

    def remember(
        self,
        statement: str,
        *,
        category: str = "context",
    ) -> MemoryWrite:
        clean = _clean_statement(statement)
        if contains_sensitive_material(clean):
            raise SensitiveMemoryError(
                "Rayluno does not store passwords, access tokens, payment details, or keys."
            )
        parsed_category = MemoryCategory(category)
        return self.store.remember(
            clean,
            category=parsed_category,
            source=_SOURCE_USER_EXPLICIT,
            fingerprint=memory_fingerprint(clean),
            now=_aware_utc(self.clock()),
        )

    def list(self, *, limit: int = 20) -> Sequence[MemoryFact]:
        return self.store.list(limit=limit)

    def forget(self, memory_id: int) -> MemoryFact | None:
        return self.store.forget(memory_id)

    def clear(self) -> int:
        return self.store.clear()

    def context(self, *, limit: int = 12) -> tuple[str, ...]:
        """Return explicit statements for a future bounded personalization layer."""

        return tuple(fact.statement for fact in self.list(limit=limit))


__all__ = [
    "InMemoryMemoryStore",
    "MemoryCategory",
    "MemoryFact",
    "MemoryService",
    "MemoryWrite",
    "SQLiteMemoryStore",
    "SensitiveMemoryError",
    "contains_sensitive_material",
    "default_memory_path",
    "memory_fingerprint",
]
