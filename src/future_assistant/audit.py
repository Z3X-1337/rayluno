"""Privacy-aware audit sinks. Raw user commands and query values are never stored."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlsplit

from .domain import Action, ActionKind


@dataclass(frozen=True, slots=True)
class AuditRecord:
    timestamp: str
    event: str
    command_hash: str | None = None
    action: dict[str, object] | None = None
    detail: str | None = None


class AuditLogger(Protocol):
    def record(
        self,
        event: str,
        *,
        command: str | None = None,
        action: Action | None = None,
        detail: str | None = None,
    ) -> None: ...


def summarize_action(action: Action) -> dict[str, object]:
    summary: dict[str, object] = {"kind": action.kind.value}
    if action.kind is ActionKind.OPEN_URL:
        value = action.parameters.get("url")
        if isinstance(value, str):
            parts = urlsplit(value)
            summary.update(
                {
                    "host": parts.hostname or "",
                    "path": parts.path,
                    "query_keys": sorted({key for key, _ in parse_qsl(parts.query)}),
                }
            )
    elif action.kind is ActionKind.OPEN_APP:
        summary["app_id"] = str(action.parameters.get("app_id", ""))
    elif action.kind is ActionKind.CONTROL_VOLUME:
        summary["operation"] = str(action.parameters.get("operation", ""))
        summary["steps"] = action.parameters.get("steps", 0)
    return summary


class _BaseAuditLogger:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))

    def make_record(
        self,
        event: str,
        command: str | None,
        action: Action | None,
        detail: str | None,
    ) -> AuditRecord:
        command_hash = None
        if command is not None:
            command_hash = hashlib.sha256(command.encode("utf-8")).hexdigest()
        return AuditRecord(
            timestamp=self.clock().astimezone(UTC).isoformat(),
            event=event,
            command_hash=command_hash,
            action=summarize_action(action) if action else None,
            detail=detail[:300] if detail else None,
        )


class NullAuditLogger:
    def record(
        self,
        event: str,
        *,
        command: str | None = None,
        action: Action | None = None,
        detail: str | None = None,
    ) -> None:
        return None


class MemoryAuditLogger(_BaseAuditLogger):
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        super().__init__(clock)
        self.records: list[AuditRecord] = []

    def record(
        self,
        event: str,
        *,
        command: str | None = None,
        action: Action | None = None,
        detail: str | None = None,
    ) -> None:
        self.records.append(self.make_record(event, command, action, detail))


class JsonlAuditLogger(_BaseAuditLogger):
    def __init__(self, path: Path, clock: Callable[[], datetime] | None = None) -> None:
        super().__init__(clock)
        self.path = path
        self._lock = threading.Lock()

    def record(
        self,
        event: str,
        *,
        command: str | None = None,
        action: Action | None = None,
        detail: str | None = None,
    ) -> None:
        record = self.make_record(event, command, action, detail)
        line = json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(f"{line}\n")
