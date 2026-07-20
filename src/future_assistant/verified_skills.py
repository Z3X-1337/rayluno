"""Safe desktop-facing facade for verified automation skills.

The automation package owns policy and bounded execution. This module adds the
user-facing lifecycle around it: non-secret confirmation handles, privacy-safe
execution receipts, and an optional tamper-evident local receipt journal.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .automation import (
    AutomationEngine,
    AutomationResult,
    ExecutionStatus,
    ResultCode,
    SkillInvocation,
    SkillManifest,
)
from .automation.models import canonical_json

_RECEIPT_SCHEMA = "rayluno.execution-receipt/v1"
_CONFIRMATION_SCHEMA = "rayluno.pending-confirmation/v1"
_GENESIS_HASH = "0" * 64


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("The verified-skills clock must return an aware datetime.")
    return value.astimezone(UTC)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_payload(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    """Non-secret confirmation metadata that may safely cross the UI bridge."""

    schema: str
    confirmation_id: str
    request_id: str
    skill_id: str
    skill_version: str
    name: str
    description: str
    risk_level: str
    permissions: tuple[str, ...]
    argument_keys: tuple[str, ...]
    argument_digest: str
    expires_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "confirmation_id": self.confirmation_id,
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
            "permissions": list(self.permissions),
            "argument_keys": list(self.argument_keys),
            "argument_digest": self.argument_digest,
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    """Privacy-safe, hash-chained record of one execution lifecycle event."""

    schema: str
    receipt_id: str
    event: str
    request_id: str
    actor_id: str
    skill_id: str
    skill_version: str
    risk_level: str
    permissions: tuple[str, ...]
    status: str
    code: str
    confirmation_state: str
    started_at: datetime
    completed_at: datetime
    argument_keys: tuple[str, ...]
    argument_digest: str
    result_keys: tuple[str, ...]
    detail: str
    previous_hash: str
    receipt_hash: str

    def payload_dict(self) -> dict[str, object]:
        """Return the canonical payload covered by the receipt hash."""

        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "event": self.event,
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "risk_level": self.risk_level,
            "permissions": list(self.permissions),
            "status": self.status,
            "code": self.code,
            "confirmation_state": self.confirmation_state,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "argument_keys": list(self.argument_keys),
            "argument_digest": self.argument_digest,
            "result_keys": list(self.result_keys),
            "detail": self.detail,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.payload_dict()
        payload["previous_hash"] = self.previous_hash
        payload["receipt_hash"] = self.receipt_hash
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ExecutionReceipt:
        return cls(
            schema=str(value["schema"]),
            receipt_id=str(value["receipt_id"]),
            event=str(value["event"]),
            request_id=str(value["request_id"]),
            actor_id=str(value["actor_id"]),
            skill_id=str(value["skill_id"]),
            skill_version=str(value["skill_version"]),
            risk_level=str(value["risk_level"]),
            permissions=tuple(str(item) for item in value["permissions"]),  # type: ignore[union-attr]
            status=str(value["status"]),
            code=str(value["code"]),
            confirmation_state=str(value["confirmation_state"]),
            started_at=datetime.fromisoformat(str(value["started_at"])),
            completed_at=datetime.fromisoformat(str(value["completed_at"])),
            argument_keys=tuple(str(item) for item in value["argument_keys"]),  # type: ignore[union-attr]
            argument_digest=str(value["argument_digest"]),
            result_keys=tuple(str(item) for item in value["result_keys"]),  # type: ignore[union-attr]
            detail=str(value["detail"]),
            previous_hash=str(value["previous_hash"]),
            receipt_hash=str(value["receipt_hash"]),
        )


class ReceiptWriter(Protocol):
    def record(
        self,
        *,
        event: str,
        result: AutomationResult,
        manifest: SkillManifest | None,
        confirmation_state: str,
        started_at: datetime,
        completed_at: datetime,
    ) -> ExecutionReceipt: ...


class ReceiptJournal:
    """Append-only SHA-256 receipt chain with optional JSONL persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._lock = threading.RLock()
        self._receipts: list[ExecutionReceipt] = []
        if self.path is not None and self.path.exists():
            self._receipts = self._read_file(self.path)
            if not self.verify(self._receipts):
                raise ValueError("The execution receipt journal failed integrity verification.")

    @property
    def receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    @property
    def last_hash(self) -> str:
        with self._lock:
            return self._receipts[-1].receipt_hash if self._receipts else _GENESIS_HASH

    def record(
        self,
        *,
        event: str,
        result: AutomationResult,
        manifest: SkillManifest | None,
        confirmation_state: str,
        started_at: datetime,
        completed_at: datetime,
    ) -> ExecutionReceipt:
        invocation = result.invocation
        permissions = (
            tuple(sorted(permission.value for permission in manifest.permissions))
            if manifest is not None
            else ()
        )
        payload: dict[str, object] = {
            "schema": _RECEIPT_SCHEMA,
            "receipt_id": secrets.token_hex(16),
            "event": event,
            "request_id": invocation.request_id,
            "actor_id": invocation.actor_id,
            "skill_id": invocation.skill_id,
            "skill_version": manifest.version if manifest is not None else "unknown",
            "risk_level": manifest.risk_level.value if manifest is not None else "unknown",
            "permissions": list(permissions),
            "status": result.status.value,
            "code": result.code.value,
            "confirmation_state": confirmation_state,
            "started_at": _aware_utc(started_at).isoformat(),
            "completed_at": _aware_utc(completed_at).isoformat(),
            "argument_keys": sorted(invocation.arguments),
            "argument_digest": _sha256_text(canonical_json(invocation.arguments)),
            "result_keys": sorted(result.data),
            "detail": result.detail,
        }
        with self._lock:
            previous_hash = self._receipts[-1].receipt_hash if self._receipts else _GENESIS_HASH
            receipt_hash = self._seal(previous_hash, payload)
            receipt = ExecutionReceipt.from_dict(
                {**payload, "previous_hash": previous_hash, "receipt_hash": receipt_hash}
            )
            self._receipts.append(receipt)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(_json_payload(receipt.to_dict()))
                    stream.write("\n")
            return receipt

    @classmethod
    def verify(cls, receipts: Sequence[ExecutionReceipt]) -> bool:
        previous_hash = _GENESIS_HASH
        for receipt in receipts:
            if receipt.schema != _RECEIPT_SCHEMA or receipt.previous_hash != previous_hash:
                return False
            if not secrets.compare_digest(
                receipt.receipt_hash,
                cls._seal(previous_hash, receipt.payload_dict()),
            ):
                return False
            previous_hash = receipt.receipt_hash
        return True

    @staticmethod
    def _seal(previous_hash: str, payload: Mapping[str, object]) -> str:
        return _sha256_text(f"{previous_hash}:{_json_payload(payload)}")

    @staticmethod
    def _read_file(path: Path) -> list[ExecutionReceipt]:
        receipts: list[ExecutionReceipt] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError("Receipt journal entries must be JSON objects.")
            receipts.append(ExecutionReceipt.from_dict(value))
        return receipts


@dataclass(frozen=True, slots=True)
class VerifiedSkillOutcome:
    receipt: ExecutionReceipt
    pending_confirmation: PendingConfirmation | None = None
    data: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt": self.receipt.to_dict(),
            "pending_confirmation": (
                self.pending_confirmation.to_dict()
                if self.pending_confirmation is not None
                else None
            ),
            "data": dict(self.data or {}),
        }


@dataclass(frozen=True, slots=True)
class _PendingExecution:
    invocation: SkillInvocation
    token: str
    view: PendingConfirmation


class UnknownConfirmationError(LookupError):
    """Raised when a UI confirmation handle is invalid or was already consumed."""


class VerifiedSkillSession:
    """Keep confirmation secrets server-side and expose receipts to the desktop UI."""

    def __init__(
        self,
        engine: AutomationEngine,
        *,
        receipts: ReceiptWriter | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._receipts = receipts or ReceiptJournal()
        self._clock = clock
        self._manifests = {manifest.skill_id: manifest for manifest in engine.manifests}
        self._pending: dict[str, _PendingExecution] = {}
        self._lock = threading.RLock()
        self._now()

    @property
    def manifests(self) -> tuple[SkillManifest, ...]:
        return self._engine.manifests

    def pending_confirmations(self) -> tuple[PendingConfirmation, ...]:
        now = self._now()
        with self._lock:
            expired = [
                confirmation_id
                for confirmation_id, pending in self._pending.items()
                if pending.view.expires_at <= now
            ]
            for confirmation_id in expired:
                del self._pending[confirmation_id]
            return tuple(
                pending.view
                for _, pending in sorted(
                    self._pending.items(),
                    key=lambda item: item[1].view.expires_at,
                )
            )

    async def submit(self, invocation: SkillInvocation) -> VerifiedSkillOutcome:
        started_at = self._now()
        result = await self._engine.execute(invocation)
        manifest = self._manifests.get(invocation.skill_id)
        if result.status is ExecutionStatus.CONFIRMATION_REQUIRED and manifest is not None:
            grant = self._engine.request_confirmation(invocation)
            confirmation_id = self._new_confirmation_id()
            view = PendingConfirmation(
                schema=_CONFIRMATION_SCHEMA,
                confirmation_id=confirmation_id,
                request_id=invocation.request_id,
                skill_id=manifest.skill_id,
                skill_version=manifest.version,
                name=manifest.name,
                description=manifest.description,
                risk_level=manifest.risk_level.value,
                permissions=tuple(sorted(item.value for item in manifest.permissions)),
                argument_keys=tuple(sorted(invocation.arguments)),
                argument_digest=_sha256_text(canonical_json(invocation.arguments)),
                expires_at=grant.expires_at,
            )
            with self._lock:
                self._pending[confirmation_id] = _PendingExecution(
                    invocation,
                    grant.token,
                    view,
                )
            receipt = self._record(
                event="confirmation_requested",
                result=result,
                manifest=manifest,
                confirmation_state="pending",
                started_at=started_at,
            )
            return VerifiedSkillOutcome(receipt, pending_confirmation=view)

        receipt = self._record(
            event="execution",
            result=result,
            manifest=manifest,
            confirmation_state="not_required",
            started_at=started_at,
        )
        return VerifiedSkillOutcome(receipt, data=result.data)

    async def approve(self, confirmation_id: str) -> VerifiedSkillOutcome:
        pending = self._pop_pending(confirmation_id)
        started_at = self._now()
        result = await self._engine.execute(
            pending.invocation,
            confirmation_token=pending.token,
        )
        manifest = self._manifests.get(pending.invocation.skill_id)
        receipt = self._record(
            event="execution",
            result=result,
            manifest=manifest,
            confirmation_state="approved",
            started_at=started_at,
        )
        return VerifiedSkillOutcome(receipt, data=result.data)

    def reject(self, confirmation_id: str) -> VerifiedSkillOutcome:
        pending = self._pop_pending(confirmation_id)
        started_at = self._now()
        result = AutomationResult(
            pending.invocation,
            ExecutionStatus.CANCELLED,
            ResultCode.CANCELLED,
            "The user rejected this skill execution.",
        )
        manifest = self._manifests.get(pending.invocation.skill_id)
        receipt = self._record(
            event="confirmation_rejected",
            result=result,
            manifest=manifest,
            confirmation_state="rejected",
            started_at=started_at,
        )
        return VerifiedSkillOutcome(receipt)

    def _record(
        self,
        *,
        event: str,
        result: AutomationResult,
        manifest: SkillManifest | None,
        confirmation_state: str,
        started_at: datetime,
    ) -> ExecutionReceipt:
        return self._receipts.record(
            event=event,
            result=result,
            manifest=manifest,
            confirmation_state=confirmation_state,
            started_at=started_at,
            completed_at=self._now(),
        )

    def _pop_pending(self, confirmation_id: str) -> _PendingExecution:
        if not isinstance(confirmation_id, str) or not confirmation_id:
            raise UnknownConfirmationError("Confirmation handle is invalid.")
        with self._lock:
            pending = self._pending.pop(confirmation_id, None)
        if pending is None:
            raise UnknownConfirmationError(
                "Confirmation handle is invalid, expired, or already consumed."
            )
        return pending

    def _new_confirmation_id(self) -> str:
        with self._lock:
            while True:
                confirmation_id = secrets.token_urlsafe(18)
                if confirmation_id not in self._pending:
                    return confirmation_id

    def _now(self) -> datetime:
        return _aware_utc(self._clock())


__all__ = [
    "ExecutionReceipt",
    "PendingConfirmation",
    "ReceiptJournal",
    "ReceiptWriter",
    "UnknownConfirmationError",
    "VerifiedSkillOutcome",
    "VerifiedSkillSession",
]
