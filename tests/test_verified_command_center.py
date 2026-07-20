from __future__ import annotations

from datetime import datetime
from pathlib import Path

from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import VolumeOperation
from future_assistant.runtime import build_runtime
from future_assistant.ui.verified_window import VerifiedDesktopApi


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


def _api(tmp_path: Path) -> tuple[VerifiedDesktopApi, FakeEffects]:
    effects = FakeEffects()
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
    )
    runtime = build_runtime(config, effects=effects, audit=MemoryAuditLogger())
    return VerifiedDesktopApi(runtime), effects


def test_desktop_app_launch_requires_confirmation_before_effect(tmp_path: Path) -> None:
    api, effects = _api(tmp_path)

    result = api.execute_command("افتح الحاسبة")

    assert result["ok"] is True
    assert result["status"] == "confirmation_required"
    assert result["verified"] is True
    pending = result["pending_confirmation"]
    assert isinstance(pending, dict)
    assert pending["skill_id"] == "app.launch"
    assert pending["risk_level"] == "high"
    assert pending["permissions"] == ["app.launch"]
    assert effects.operations == []


def test_desktop_approval_executes_once_and_replay_fails_closed(tmp_path: Path) -> None:
    api, effects = _api(tmp_path)
    requested = api.execute_command("افتح الحاسبة")
    pending = requested["pending_confirmation"]
    assert isinstance(pending, dict)
    confirmation_id = str(pending["confirmation_id"])

    approved = api.approve_skill(confirmation_id)
    replayed = api.approve_skill(confirmation_id)

    assert approved["ok"] is True
    assert approved["verified"] is True
    assert isinstance(approved["receipt"], dict)
    assert approved["receipt"]["confirmation_state"] == "approved"
    assert replayed["ok"] is False
    assert replayed["status"] == "blocked"
    assert effects.operations == [("open_app", "calculator")]


def test_desktop_rejection_never_executes_effect(tmp_path: Path) -> None:
    api, effects = _api(tmp_path)
    requested = api.execute_command("افتح الحاسبة")
    pending = requested["pending_confirmation"]
    assert isinstance(pending, dict)

    rejected = api.reject_skill(str(pending["confirmation_id"]))

    assert rejected["ok"] is True
    assert rejected["status"] == "blocked"
    assert isinstance(rejected["receipt"], dict)
    assert rejected["receipt"]["confirmation_state"] == "rejected"
    assert effects.operations == []


def test_desktop_search_executes_with_redacted_verified_receipt(tmp_path: Path) -> None:
    api, effects = _api(tmp_path)
    private_query = "خطة الحكام الخاصة"

    result = api.execute_command(f"ابحث عن {private_query}")

    assert result["ok"] is True
    assert result["verified"] is True
    receipt = result["receipt"]
    assert isinstance(receipt, dict)
    assert receipt["argument_keys"] == ["query"]
    assert private_query not in repr(receipt)
    assert effects.operations and effects.operations[0][0] == "open_url"


def test_snapshot_and_receipt_api_report_verified_chain(tmp_path: Path) -> None:
    api, _ = _api(tmp_path)
    api.execute_command("ابحث عن اختبار السلسلة")

    snapshot = api.get_snapshot()
    receipts = api.get_verified_receipts()

    assert snapshot["verified"]["available"] is True
    assert snapshot["verified"]["integrity_ok"] is True
    assert snapshot["verified"]["receipt_count"] == 1
    assert receipts["ok"] is True
    assert receipts["integrity_ok"] is True
    assert len(receipts["receipts"]) == 1


def test_tampered_receipt_journal_disables_execution_fail_closed(tmp_path: Path) -> None:
    receipt_path = tmp_path / "execution-receipts.jsonl"
    receipt_path.write_text('{"status":"edited"}\n', encoding="utf-8")
    api, effects = _api(tmp_path)

    result = api.execute_command("افتح الحاسبة")
    status = api.get_verified_status()

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["verified"] is True
    assert status["available"] is False
    assert status["integrity_ok"] is False
    assert effects.operations == []


def test_invalid_confirmation_input_is_rejected_without_exception(tmp_path: Path) -> None:
    api, effects = _api(tmp_path)

    result = api.approve_skill(None)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert effects.operations == []
