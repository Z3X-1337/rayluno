"""Permission manifests and tamper-evident execution receipts for bounded skills."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .audit import summarize_action
from .domain import Action, ActionKind, ExecutionResult, PlanSource

_RECEIPT_SCHEMA = "rayluno.execution-receipt/v2"
_GENESIS_HASH = "0" * 64


class SkillRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfirmationPolicy(StrEnum):
    NEVER = "never"
    MODEL_PROPOSED = "model_proposed"
    ALWAYS = "always"


@dataclass(frozen=True, slots=True)
class SkillManifest:
    skill_id: str
    action_kind: ActionKind
    permission: str
    risk: SkillRisk
    confirmation: ConfirmationPolicy
    purposes: frozenset[str] = frozenset()

    def matches(self, action: Action) -> bool:
        if action.kind is not self.action_kind:
            return False
        if not self.purposes:
            return True
        purpose = action.parameters.get("purpose")
        return isinstance(purpose, str) and purpose in self.purposes


@dataclass(frozen=True, slots=True)
class SkillAssessment:
    manifest: SkillManifest
    requires_confirmation: bool
    reason: str


class VerifiedSkillRegistry:
    def __init__(self, manifests: tuple[SkillManifest, ...] | None = None) -> None:
        self._manifests = manifests or default_skill_manifests()

    @property
    def manifests(self) -> tuple[SkillManifest, ...]:
        return self._manifests

    def resolve(self, action: Action) -> SkillManifest | None:
        for manifest in self._manifests:
            if manifest.matches(action):
                return manifest
        return None


class VerifiedSkillEngine:
    def __init__(self, registry: VerifiedSkillRegistry | None = None) -> None:
        self.registry = registry or VerifiedSkillRegistry()

    def assess(self, action: Action, source: PlanSource) -> SkillAssessment | None:
        manifest = self.registry.resolve(action)
        if manifest is None:
            return None
        proposal_sources = {PlanSource.OLLAMA, PlanSource.DEMO}
        requires_confirmation = manifest.confirmation is ConfirmationPolicy.ALWAYS or (
            manifest.confirmation is ConfirmationPolicy.MODEL_PROPOSED
            and source in proposal_sources
        )
        if requires_confirmation:
            reason = (
                "demo_proposed_consequential_skill"
                if source is PlanSource.DEMO
                else "model_proposed_consequential_skill"
            )
        else:
            reason = "registered_skill_policy_satisfied"
        return SkillAssessment(manifest, requires_confirmation, reason)


def default_skill_manifests() -> tuple[SkillManifest, ...]:
    return (
        SkillManifest(
            "web.search",
            ActionKind.OPEN_URL,
            "network.browser.search",
            SkillRisk.MEDIUM,
            ConfirmationPolicy.MODEL_PROPOSED,
            frozenset({"search", "youtube_search", "youtube_media"}),
        ),
        SkillManifest(
            "web.navigate",
            ActionKind.OPEN_URL,
            "network.browser.navigate",
            SkillRisk.MEDIUM,
            ConfirmationPolicy.MODEL_PROPOSED,
            frozenset({"site"}),
        ),
        SkillManifest(
            "application.launch",
            ActionKind.OPEN_APP,
            "applications.launch",
            SkillRisk.MEDIUM,
            ConfirmationPolicy.MODEL_PROPOSED,
        ),
        SkillManifest(
            "system.time.read",
            ActionKind.REPORT_TIME,
            "system.time.read",
            SkillRisk.LOW,
            ConfirmationPolicy.NEVER,
        ),
        SkillManifest(
            "system.audio.control",
            ActionKind.CONTROL_VOLUME,
            "system.audio.control",
            SkillRisk.LOW,
            ConfirmationPolicy.MODEL_PROPOSED,
        ),
    )


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    schema: str
    receipt_id: str
    timestamp: str
    event: str
    skill_id: str
    permission: str
    risk: str
    status: str
    confirmation_state: str
    policy_reason: str
    action: Mapping[str, object]
    argument_keys: tuple[str, ...]
    argument_digest: str
    previous_hash: str
    receipt_hash: str

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "event": self.event,
            "skill_id": self.skill_id,
            "permission": self.permission,
            "risk": self.risk,
            "status": self.status,
            "confirmation_state": self.confirmation_state,
            "policy_reason": self.policy_reason,
            "action": dict(self.action),
            "argument_keys": list(self.argument_keys),
            "argument_digest": self.argument_digest,
            "previous_hash": self.previous_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ExecutionReceipt:
        action = value.get("action")
        argument_keys = value.get("argument_keys")
        if not isinstance(action, Mapping) or not isinstance(argument_keys, list):
            raise ValueError("Receipt action and argument_keys must be structured values.")
        return cls(
            schema=str(value["schema"]),
            receipt_id=str(value["receipt_id"]),
            timestamp=str(value["timestamp"]),
            event=str(value["event"]),
            skill_id=str(value["skill_id"]),
            permission=str(value["permission"]),
            risk=str(value["risk"]),
            status=str(value["status"]),
            confirmation_state=str(value["confirmation_state"]),
            policy_reason=str(value["policy_reason"]),
            action={str(key): item for key, item in action.items()},
            argument_keys=tuple(str(item) for item in argument_keys),
            argument_digest=str(value["argument_digest"]),
            previous_hash=str(value["previous_hash"]),
            receipt_hash=str(value["receipt_hash"]),
        )


class ReceiptIntegrityError(RuntimeError):
    """Raised when a receipt journal cannot be trusted or safely extended."""


class ReceiptSink(Protocol):
    @property
    def receipts(self) -> tuple[ExecutionReceipt, ...]: ...

    @property
    def integrity_ok(self) -> bool: ...

    def verify_integrity(self, *, reload: bool = True) -> bool: ...

    def record(
        self,
        assessment: SkillAssessment,
        result: ExecutionResult,
        *,
        event: str = "execution",
        confirmation_state: str = "not_required",
        status_override: str | None = None,
    ) -> ExecutionReceipt: ...


class HashChainedReceiptLedger:
    """Append-only JSONL receipt journal verified before every new execution."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._receipts: list[ExecutionReceipt] = []
        self._integrity_ok = True
        self._integrity_error: str | None = None
        self._load_initial_state()

    @property
    def receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    @property
    def integrity_ok(self) -> bool:
        with self._lock:
            return self._integrity_ok

    @property
    def integrity_error(self) -> str | None:
        with self._lock:
            return self._integrity_error

    @property
    def chain_head(self) -> str:
        with self._lock:
            return self._receipts[-1].receipt_hash if self._receipts else _GENESIS_HASH

    def verify_integrity(self, *, reload: bool = True) -> bool:
        with self._lock:
            try:
                candidate = (
                    self._read_file()
                    if reload and self.path is not None
                    else self._receipts
                )
            except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
                self._mark_invalid(type(exc).__name__)
                return False
            if not self.verify(candidate):
                self._mark_invalid("hash_chain_mismatch")
                return False
            self._receipts = list(candidate)
            self._integrity_ok = True
            self._integrity_error = None
            return True

    def record(
        self,
        assessment: SkillAssessment,
        result: ExecutionResult,
        *,
        event: str = "execution",
        confirmation_state: str = "not_required",
        status_override: str | None = None,
    ) -> ExecutionReceipt:
        with self._lock:
            if not self.verify_integrity(reload=True):
                raise ReceiptIntegrityError("The receipt journal failed integrity verification.")
            previous_hash = self.chain_head
            timestamp = self._aware_utc(self.clock()).isoformat()
            status = status_override or (
                "completed" if result.ok else "blocked" if result.blocked else "failed"
            )
            arguments = dict(result.action.parameters)
            payload: dict[str, object] = {
                "schema": _RECEIPT_SCHEMA,
                "receipt_id": f"ryl-{secrets.token_hex(8)}",
                "timestamp": timestamp,
                "event": event,
                "skill_id": assessment.manifest.skill_id,
                "permission": assessment.manifest.permission,
                "risk": assessment.manifest.risk.value,
                "status": status,
                "confirmation_state": confirmation_state,
                "policy_reason": assessment.reason,
                "action": summarize_action(result.action),
                "argument_keys": sorted(str(key) for key in arguments),
                "argument_digest": self._digest(arguments),
                "previous_hash": previous_hash,
            }
            receipt_hash = self._seal(payload)
            receipt = ExecutionReceipt.from_dict({**payload, "receipt_hash": receipt_hash})
            self._receipts.append(receipt)
            self._append(receipt)
            return receipt

    @classmethod
    def verify(cls, receipts: Sequence[ExecutionReceipt]) -> bool:
        previous_hash = _GENESIS_HASH
        for receipt in receipts:
            if receipt.schema != _RECEIPT_SCHEMA or receipt.previous_hash != previous_hash:
                return False
            expected_hash = cls._seal(receipt.unsigned_payload())
            if not secrets.compare_digest(receipt.receipt_hash, expected_hash):
                return False
            previous_hash = receipt.receipt_hash
        return True

    def _load_initial_state(self) -> None:
        if self.path is None or not self.path.exists():
            return
        self.verify_integrity(reload=True)

    def _read_file(self) -> list[ExecutionReceipt]:
        if self.path is None or not self.path.exists():
            return []
        receipts: list[ExecutionReceipt] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError("Receipt journal entries must be JSON objects.")
            receipts.append(ExecutionReceipt.from_dict(value))
        return receipts

    def _append(self, receipt: ExecutionReceipt) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(receipt), ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{line}\n")

    def _mark_invalid(self, error: str) -> None:
        self._integrity_ok = False
        self._integrity_error = error

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _canonical(value: Mapping[str, object]) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _digest(cls, value: Mapping[str, object]) -> str:
        return hashlib.sha256(cls._canonical(value).encode("utf-8")).hexdigest()

    @classmethod
    def _seal(cls, payload: Mapping[str, object]) -> str:
        return hashlib.sha256(cls._canonical(payload).encode("utf-8")).hexdigest()


__all__ = [
    "ConfirmationPolicy",
    "ExecutionReceipt",
    "HashChainedReceiptLedger",
    "ReceiptIntegrityError",
    "ReceiptSink",
    "SkillAssessment",
    "SkillManifest",
    "SkillRisk",
    "VerifiedSkillEngine",
    "VerifiedSkillRegistry",
    "default_skill_manifests",
]
