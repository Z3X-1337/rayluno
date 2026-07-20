"""Privacy-aware audit sinks. Raw user commands and query values are never stored."""

from __future__ import annotations

import json
import os
import secrets
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlsplit

from .domain import Action, ActionKind
from .local_security import keyed_digest, load_or_create_key, secure_directory, secure_file
from .local_security import keyed_digest, load_or_create_key, secure_directory, secure_file


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
    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        *,
        fingerprint_key: bytes | None = None,
    ) -> None:
        self.clock = clock or (lambda: datetime.now(UTC))
        self._fingerprint_key = fingerprint_key or secrets.token_bytes(32)

    def make_record(
        self,
        event: str,
        command: str | None,
        action: Action | None,
        detail: str | None,
    ) -> AuditRecord:
        command_hash = None
        if command is not None:
            command_hash = keyed_digest(
                self._fingerprint_key,
                {"domain": "rayluno.audit.command/v1", "command": command},
            )
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
        self.path = Path(path)
        secure_directory(self.path.parent)
        key_path = self.path.with_name(f"{self.path.name}.key")
        try:
            fingerprint_key = load_or_create_key(key_path)
        except (OSError, ValueError):
            fingerprint_key = secrets.token_bytes(32)
        super().__init__(clock, fingerprint_key=fingerprint_key)
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
            secure_directory(self.path.parent)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(f"{line}\n")
                stream.flush()
                os.fsync(stream.fileno())
            secure_file(self.path)
