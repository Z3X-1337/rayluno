from __future__ import annotations

from datetime import datetime

import pytest

from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import RuntimeStatus, VolumeOperation
from future_assistant.runtime import build_runtime
from future_assistant.verified_runtime import VerifiedRuntimeBridge
from future_assistant.verified_skills import ReceiptJournal, UnknownConfirmationError


class FakeEffects:
    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []

    def open_url(self, url: str) -> None:
        self.operations.append(("open_url", url))

    def open_app(self, app_id: str) -> None:
        self.operations.append(("open_app", app_id))

    def current_time(self) -> datetime:
        self.operations.append(("current_time",))
        return datetime(2026, 7, 20, 16, 30)

    def control_volume(self, operation: VolumeOperation, steps: int) -> None:
        self.operations.append(("control_volume", operation.value, steps))


def _bridge() -> tuple[VerifiedRuntimeBridge, FakeEffects, ReceiptJournal]:
    effects = FakeEffects()
    config = AssistantConfig(require_wake_word=False, audit_path=None)
    runtime = build_runtime(config, effects=effects, audit=MemoryAuditLogger())
    journal = ReceiptJournal()
    return VerifiedRuntimeBridge(runtime, journal=journal), effects, journal


def test_app_launch_is_planned_but_not_executed_before_confirmation() -> None:
    bridge, effects, _ = _bridge()

    result = bridge.execute("افتح الحاسبة")

    assert result.status == "confirmation_required"
    assert result.verified
    assert result.pending_confirmation is not None
    assert result.pending_confirmation["skill_id"] == "app.launch"
    assert result.pending_confirmation["risk_level"] == "high"
    assert effects.operations == []


def test_app_launch_approval_executes_once_and_returns_receipt() -> None:
    bridge, effects, _ = _bridge()
    requested = bridge.execute("افتح الحاسبة")
    confirmation_id = requested.pending_confirmation["confirmation_id"]  # type: ignore[index]

    approved = bridge.approve(str(confirmation_id))

    assert approved.ok
    assert approved.status == RuntimeStatus.COMPLETED.value
    assert approved.receipt is not None
    assert approved.receipt["confirmation_state"] == "approved"
    assert effects.operations == [("open_app", "calculator")]
    with pytest.raises(UnknownConfirmationError):
        bridge.approve(str(confirmation_id))
    assert effects.operations == [("open_app", "calculator")]


def test_app_launch_rejection_never_executes_effect() -> None:
    bridge, effects, _ = _bridge()
    requested = bridge.execute("افتح الحاسبة")
    confirmation_id = requested.pending_confirmation["confirmation_id"]  # type: ignore[index]

    rejected = bridge.reject(str(confirmation_id))

    assert rejected.ok
    assert rejected.receipt is not None
    assert rejected.receipt["confirmation_state"] == "rejected"
    assert effects.operations == []


def test_search_executes_immediately_through_verified_skill_and_redacts_query() -> None:
    bridge, effects, _ = _bridge()
    private_query = "خطة العرض السرية"

    result = bridge.execute(f"ابحث عن {private_query}")

    assert result.ok
    assert result.verified
    assert result.pending_confirmation is None
    assert result.receipt is not None
    assert result.receipt["argument_keys"] == ["query"]
    assert private_query not in repr(result.receipt)
    assert effects.operations and effects.operations[0][0] == "open_url"


def test_unsupported_effect_uses_legacy_runtime_path_explicitly() -> None:
    bridge, effects, _ = _bridge()

    result = bridge.execute("ارفع الصوت")

    assert result.ok
    assert not result.verified
    assert result.action == "control_volume"
    assert effects.operations == [("control_volume", "up", 2)]


def test_reply_only_task_or_chat_plan_is_not_executed_twice() -> None:
    bridge, effects, _ = _bridge()

    result = bridge.execute("كم الساعة")

    assert result.ok
    assert not result.verified
    assert effects.operations == [("current_time",)]


def test_recent_receipts_are_newest_first_and_chain_verifies() -> None:
    bridge, _, journal = _bridge()

    bridge.execute("ابحث عن الأول")
    bridge.execute("ابحث عن الثاني")

    receipts = bridge.recent_receipts()
    assert len(receipts) == 2
    assert receipts[0]["previous_hash"] == receipts[1]["receipt_hash"]
    assert bridge.receipt_integrity_ok
