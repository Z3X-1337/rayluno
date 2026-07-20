from datetime import datetime
from pathlib import Path

from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import VolumeOperation
from future_assistant.runtime import build_runtime
from future_assistant.ui.memory_window import MemoryDesktopApi


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


def _api(tmp_path: Path) -> tuple[MemoryDesktopApi, FakeEffects, MemoryAuditLogger]:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
        memory_path=tmp_path / "memory.sqlite3",
    )
    runtime = build_runtime(config, effects=effects, audit=audit)
    return MemoryDesktopApi(runtime), effects, audit


def test_memory_vault_starts_empty_and_declares_explicit_consent(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)

    snapshot = api.get_memory_snapshot()

    assert snapshot == {
        "available": True,
        "consent_mode": "explicit_only",
        "count": 0,
        "items": [],
        "error": None,
    }


def test_explicit_command_appears_in_desktop_memory_vault(tmp_path: Path) -> None:
    api, _, audit = _api(tmp_path)
    statement = "أفضل أن تكون الردود مباشرة"

    result = api.execute_command(f"تذكر أن {statement}")
    snapshot = api.get_memory_snapshot()

    assert result["ok"] is True
    assert result["verified"] is False
    assert snapshot["count"] == 1
    item = snapshot["items"][0]
    assert item["id"] == 1
    assert item["statement"] == statement
    assert item["category"] == "preference"
    assert item["source"] == "user_explicit"
    assert statement not in repr(audit.records)


def test_memory_can_be_deleted_from_desktop_by_visible_id(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)
    api.execute_command("تذكر أن اسمي زيد")

    deleted = api.forget_memory(1)
    snapshot = api.get_memory_snapshot()

    assert deleted["ok"] is True
    assert deleted["memory"]["statement"] == "اسمي زيد"
    assert snapshot["count"] == 0
    assert snapshot["items"] == []


def test_invalid_or_missing_memory_id_fails_without_deleting(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)
    api.execute_command("تذكر أنني أفضل الوضع الداكن")

    invalid = api.forget_memory(True)
    missing = api.forget_memory(99)

    assert invalid["ok"] is False
    assert missing["ok"] is False
    assert api.get_memory_snapshot()["count"] == 1


def test_sensitive_memory_refusal_never_reaches_vault(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path)

    result = api.execute_command("تذكر أن كلمة المرور هي 123456")

    assert result["ok"] is True
    assert "لن أحفظ كلمات المرور" in result["message"]
    assert api.get_memory_snapshot()["count"] == 0


def test_main_snapshot_contains_memory_and_verified_surfaces(tmp_path: Path) -> None:
    api, effects, _ = _api(tmp_path)
    api.execute_command("تذكر أنني أفضل العربية")
    search = api.execute_command("ابحث عن اختبار الذاكرة")

    snapshot = api.get_snapshot()

    assert snapshot["memory"]["count"] == 1
    assert snapshot["verified"]["available"] is True
    assert search["verified"] is True
    assert effects.operations and effects.operations[0][0] == "open_url"
