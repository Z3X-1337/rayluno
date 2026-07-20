"""Permission manifests and tamper-evident execution receipts for bounded skills."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .audit import summarize_action
from .domain import Action, ActionKind, ExecutionResult, PlanSource


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
    receipt_id: str
    timestamp: str
    skill_id: str
    permission: str
    risk: str
    status: str
    policy_reason: str
    action: Mapping[str, object]
    previous_hash: str
    receipt_hash: str


class ReceiptSink(Protocol):
    def record(
        self,
        assessment: SkillAssessment,
        result: ExecutionResult,
    ) -> ExecutionReceipt: ...


class HashChainedReceiptLedger:
    """Append-only local JSONL ledger with a hash link between adjacent receipts."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self.receipts: list[ExecutionReceipt] = []
        self._previous_hash = self._load_previous_hash()

    def record(
        self,
        assessment: SkillAssessment,
        result: ExecutionResult,
    ) -> ExecutionReceipt:
        with self._lock:
            timestamp = self.clock().astimezone(UTC).isoformat()
            status = "completed" if result.ok else "blocked" if result.blocked else "failed"
            payload: dict[str, object] = {
                "timestamp": timestamp,
                "skill_id": assessment.manifest.skill_id,
                "permission": assessment.manifest.permission,
                "risk": assessment.manifest.risk.value,
                "status": status,
                "policy_reason": assessment.reason,
                "action": summarize_action(result.action),
                "previous_hash": self._previous_hash,
            }
            canonical = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            receipt_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            receipt = ExecutionReceipt(
                receipt_id=f"ryl-{receipt_hash[:12]}",
                receipt_hash=receipt_hash,
                **payload,
            )
            self.receipts.append(receipt)
            self._previous_hash = receipt_hash
            self._append(receipt)
            return receipt

    def _load_previous_hash(self) -> str:
        if self.path is None or not self.path.exists():
            return ""
        try:
            lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line]
            if not lines:
                return ""
            value = json.loads(lines[-1]).get("receipt_hash", "")
            return value if isinstance(value, str) and len(value) == 64 else ""
        except (OSError, json.JSONDecodeError):
            return ""

    def _append(self, receipt: ExecutionReceipt) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(receipt), ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"{line}\n")
