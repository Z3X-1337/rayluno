from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from future_assistant.actions import ActionFactory
from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.memory import (
    InMemoryMemoryStore,
    MemoryCategory,
    MemoryService,
    SQLiteMemoryStore,
    SensitiveMemoryError,
)
from future_assistant.memory_commands import MemoryCommandPlanner
from future_assistant.router import DeterministicRouter
from future_assistant.runtime import DryRunEffects, build_runtime


FIXED_NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _clock() -> datetime:
    return FIXED_NOW


def test_memory_service_requires_explicit_non_sensitive_statement() -> None:
    service = MemoryService(InMemoryMemoryStore(), clock=_clock)

    saved = service.remember("أفضل الوضع الداكن", category="preference")

    assert saved.created
    assert saved.fact.category is MemoryCategory.PREFERENCE
    assert saved.fact.source == "user_explicit"
    assert service.context() == ("أفضل الوضع الداكن",)

    with pytest.raises(SensitiveMemoryError):
        service.remember("كلمة السر هي 123456", category="context")
    with pytest.raises(SensitiveMemoryError):
        service.remember("my API key is secret", category="context")


def test_duplicate_memory_refreshes_existing_fact_without_duplication() -> None:
    service = MemoryService(InMemoryMemoryStore(), clock=_clock)

    first = service.remember("I prefer concise answers", category="preference")
    second = service.remember("i prefer concise answers", category="preference")

    assert first.created
    assert not second.created
    assert second.fact.id == first.fact.id
    assert len(service.list()) == 1


def test_sqlite_memory_persists_and_can_be_forgotten(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    first = MemoryService(SQLiteMemoryStore(path), clock=_clock)
    saved = first.remember("اسمي زيد", category="identity")

    reopened = MemoryService(SQLiteMemoryStore(path), clock=_clock)
    facts = reopened.list()

    assert len(facts) == 1
    assert facts[0].statement == "اسمي زيد"
    assert facts[0].category is MemoryCategory.IDENTITY
    assert reopened.forget(saved.fact.id) == facts[0]
    assert reopened.list() == ()


def test_arabic_memory_commands_cover_remember_list_and_forget() -> None:
    service = MemoryService(InMemoryMemoryStore(), clock=_clock)
    planner = MemoryCommandPlanner(service)

    remembered = planner.plan("تذكر ان اسمي زيد", "تذكر أن اسمي زيد")
    listed = planner.plan("ماذا تتذكر عني", "ماذا تتذكر عني")
    forgotten = planner.plan("احذف الذاكرة رقم 1", "احذف الذاكرة رقم 1")

    assert remembered is not None and "الذاكرة رقم 1" in remembered.reply
    assert listed is not None and "اسمي زيد" in listed.reply
    assert "[هوية]" in listed.reply
    assert forgotten is not None and "حذفت الذاكرة رقم 1" in forgotten.reply
    assert service.list() == ()


def test_english_memory_commands_and_duplicate_message() -> None:
    service = MemoryService(InMemoryMemoryStore(), clock=_clock)
    planner = MemoryCommandPlanner(service)

    first = planner.plan("remember that i prefer dark mode", "Remember that I prefer dark mode")
    duplicate = planner.plan("remember that i prefer dark mode", "Remember that I prefer dark mode")
    listed = planner.plan("what do you remember about me", "What do you remember about me")

    assert first is not None and "I saved memory 1" in first.reply
    assert duplicate is not None and "already saved" in duplicate.reply
    assert listed is not None and "[preference]" in listed.reply


def test_memory_planner_refuses_secret_material_without_persisting() -> None:
    service = MemoryService(InMemoryMemoryStore(), clock=_clock)
    planner = MemoryCommandPlanner(service)

    result = planner.plan(
        "تذكر ان كلمة المرور هي hunter2",
        "تذكر أن كلمة المرور هي hunter2",
    )

    assert result is not None
    assert "لن أحفظ كلمات المرور" in result.reply
    assert service.list() == ()


def test_router_does_not_confuse_timed_reminder_with_personal_memory(tmp_path: Path) -> None:
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
        memory_path=tmp_path / "memory.sqlite3",
    )
    router = DeterministicRouter(ActionFactory(config), clock=_clock)

    reminder = router.route("ذكرني بعد عشر دقائق أراجع العرض")
    memory = router.route("تذكر أنني أفضل الردود المختصرة")

    assert reminder is not None and "التذكير رقم" in reminder.reply
    assert memory is not None and "الذاكرة رقم" in memory.reply


def test_runtime_memory_lifecycle_keeps_raw_statement_out_of_audit(tmp_path: Path) -> None:
    audit = MemoryAuditLogger()
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
        memory_path=tmp_path / "memory.sqlite3",
    )
    runtime = build_runtime(config, effects=DryRunEffects(), audit=audit)
    statement = "أفضل أن تكون الردود مباشرة"

    saved = runtime.handle(f"تذكر أن {statement}")
    listed = runtime.handle("ماذا تتذكر عني")
    deleted = runtime.handle("احذف الذاكرة رقم 1")

    assert saved.ok and "الذاكرة رقم 1" in saved.message
    assert listed.ok and statement in listed.message
    assert deleted.ok and "حذفت الذاكرة رقم 1" in deleted.message
    assert statement not in repr(audit.records)
