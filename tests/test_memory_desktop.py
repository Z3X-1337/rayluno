from __future__ import annotations

from future_assistant.config import AssistantConfig
from future_assistant.runtime import DryRunEffects
from future_assistant.ui.memory_window import MemoryDesktopApi
from future_assistant.verified_runtime import build_verified_runtime
from future_assistant.verified_skills import HashChainedReceiptLedger


def _api(tmp_path) -> tuple[MemoryDesktopApi, DryRunEffects]:  # noqa: ANN001
    effects = DryRunEffects()
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
        memory_path=tmp_path / "memory.sqlite3",
    )
    runtime = build_verified_runtime(
        config,
        effects=effects,
        receipt_ledger=HashChainedReceiptLedger(),
    )
    return MemoryDesktopApi(runtime), effects


def test_memory_vault_reflects_only_explicit_runtime_writes(tmp_path) -> None:  # noqa: ANN001
    api, _ = _api(tmp_path)

    unrelated = api.execute_command("أنا أفضل الردود المختصرة")
    before = api.get_memory_snapshot()
    saved = api.execute_command("تذكر أنني أفضل الردود المختصرة")
    after = api.get_memory_snapshot()

    assert unrelated["ok"] is False
    assert before["count"] == 0
    assert saved["ok"] is True
    assert after["consent_mode"] == "explicit_only"
    assert after["storage"] == "local_sqlite"
    assert after["count"] == 1
    assert after["items"][0]["statement"] == "أنني أفضل الردود المختصرة"
    assert after["items"][0]["source"] == "user_explicit"


def test_memory_vault_can_delete_one_fact_without_exposing_internal_metadata(tmp_path) -> None:  # noqa: ANN001
    api, _ = _api(tmp_path)
    api.execute_command("تذكر أن اسمي زيد")
    snapshot = api.get_memory_snapshot()
    memory_id = snapshot["items"][0]["id"]

    deleted = api.forget_memory(memory_id)

    assert deleted["ok"] is True
    assert deleted["deleted_id"] == memory_id
    assert deleted["memory"]["count"] == 0
    assert "fingerprint" not in repr(snapshot)
    assert "fingerprint" not in repr(deleted)


def test_memory_clear_uses_expiring_single_use_python_handle(tmp_path) -> None:  # noqa: ANN001
    api, _ = _api(tmp_path)
    api.execute_command("تذكر أن اسمي زيد")
    api.execute_command("تذكر أنني أفضل الوضع الداكن")

    requested = api.request_memory_clear()

    assert requested["ok"] is True
    assert requested["count"] == 2
    assert requested["confirmation_id"]
    assert requested["expires_at"]

    invalid = api.confirm_memory_clear("forged-handle")
    assert invalid == {"ok": False, "error": "invalid_clear_confirmation"}
    assert api.get_memory_snapshot()["count"] == 2

    confirmed = api.confirm_memory_clear(requested["confirmation_id"])

    assert confirmed["ok"] is True
    assert confirmed["deleted_count"] == 2
    assert confirmed["memory"]["count"] == 0

    replay = api.confirm_memory_clear(requested["confirmation_id"])
    assert replay == {"ok": False, "error": "invalid_clear_confirmation"}


def test_memory_clear_can_be_cancelled_without_deleting(tmp_path) -> None:  # noqa: ANN001
    api, _ = _api(tmp_path)
    api.execute_command("تذكر أن اسمي زيد")
    requested = api.request_memory_clear()

    cancelled = api.cancel_memory_clear(requested["confirmation_id"])

    assert cancelled["ok"] is True
    assert cancelled["cancelled"] is True
    assert cancelled["memory"]["count"] == 1
    assert api.get_memory_snapshot()["clear_pending"] is None
