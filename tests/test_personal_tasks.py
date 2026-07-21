from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from future_assistant.actions import ActionFactory
from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import ActionKind, RuntimeStatus
from future_assistant.router import DeterministicRouter
from future_assistant.runtime import DryRunEffects, build_runtime
from future_assistant.tasks import (
    InMemoryTaskStore,
    SQLiteTaskStore,
    TaskPriority,
    TaskService,
    TaskStatus,
)


@pytest.fixture
def config(tmp_path) -> AssistantConfig:  # noqa: ANN001
    return AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
    )


@pytest.fixture
def task_service() -> TaskService:
    return TaskService(
        InMemoryTaskStore(),
        clock=lambda: datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
    )


@pytest.fixture
def router(config: AssistantConfig, task_service: TaskService) -> DeterministicRouter:
    return DeterministicRouter(ActionFactory(config), task_service=task_service)


@pytest.mark.parametrize(
    ("phrase", "title", "priority", "due_date"),
    [
        ("اضف مهمة شراء الحليب", "شراء الحليب", TaskPriority.NORMAL, None),
        ("ذكرني ان ارسل التقرير غدا", "ارسل التقرير", TaskPriority.NORMAL, date(2026, 7, 21)),
        (
            "ضيف مهمة مراجعة العرض اليوم باولوية عالية",
            "مراجعة العرض",
            TaskPriority.HIGH,
            date(2026, 7, 20),
        ),
        ("add a task to review the demo", "review the demo", TaskPriority.NORMAL, None),
        (
            "remind me to call the team tomorrow high priority",
            "call the team",
            TaskPriority.HIGH,
            date(2026, 7, 21),
        ),
    ],
)
def test_routes_and_persists_bilingual_task_creation(
    router: DeterministicRouter,
    task_service: TaskService,
    phrase: str,
    title: str,
    priority: TaskPriority,
    due_date: date | None,
) -> None:
    plan = router.route(phrase)

    assert plan is not None
    assert plan.actions == ()
    task = task_service.list(include_completed=True)[0]
    assert task.title == title
    assert task.priority is priority
    assert task.due_date == due_date


def test_routes_task_mutations_and_lists(
    router: DeterministicRouter,
    task_service: TaskService,
) -> None:
    router.route("اضف مهمة تجهيز العرض")
    listed = router.route("اعرض مهامي")
    completed = router.route("انجز المهمة رقم 1")
    empty = router.route("اعرض مهامي")
    history = router.route("show all tasks")
    deleted = router.route("delete task 1")

    assert listed is not None and "○ 1) تجهيز العرض" in str(listed.reply)
    assert completed is not None and "أنجزت المهمة رقم 1" in str(completed.reply)
    assert empty is not None and empty.reply == "لا توجد مهام في هذه القائمة."
    assert history is not None and "✓ 1) تجهيز العرض" in str(history.reply)
    assert deleted is not None and "I deleted task 1" in str(deleted.reply)
    assert task_service.list(include_completed=True) == ()


def test_task_service_resolves_due_dates_and_sorts_by_priority() -> None:
    now = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    service = TaskService(InMemoryTaskStore(), clock=lambda: now)

    normal = service.create("normal", due="today")
    high = service.create("high", priority="high", due="tomorrow")
    low = service.create("low", priority="low")

    assert normal.due_date == date(2026, 7, 20)
    assert high.due_date == date(2026, 7, 21)
    assert [task.id for task in service.list()] == [high.id, normal.id, low.id]


def test_sqlite_task_store_persists_and_enforces_single_completion(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "private" / "tasks.sqlite3"
    created_at = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    store = SQLiteTaskStore(path)
    task = store.create(
        "Prepare judge demo",
        priority=TaskPriority.HIGH,
        due_date=date(2026, 7, 21),
        created_at=created_at,
    )

    reopened = SQLiteTaskStore(path)
    listed = reopened.list()
    completed = reopened.complete(
        task.id,
        completed_at=datetime(2026, 7, 20, 9, 0, tzinfo=UTC),
    )

    assert listed == (task,)
    assert completed is not None
    assert completed.status is TaskStatus.COMPLETED
    assert reopened.complete(task.id, completed_at=created_at) is None
    assert reopened.list() == ()
    assert reopened.list(include_completed=True)[0].completed_at is not None


def test_runtime_supports_full_private_task_lifecycle(config: AssistantConfig) -> None:
    expected_before = datetime.now(UTC).date() + timedelta(days=1)
    audit = MemoryAuditLogger()
    runtime = build_runtime(
        config,
        effects=DryRunEffects(),
        audit=audit,
    )

    created = runtime.handle("اضف مهمة تجهيز فيديو الحكام غدا باولوية عالية")
    listed = runtime.handle("اعرض مهامي")
    completed = runtime.handle("انجز المهمة رقم 1")
    empty = runtime.handle("اعرض مهامي")
    history = runtime.handle("اعرض كل المهام")
    expected_after = datetime.now(UTC).date() + timedelta(days=1)

    assert created.status is RuntimeStatus.COMPLETED
    assert created.message == "أضفت المهمة رقم 1: تجهيز فيديو الحكام."
    assert listed.status is RuntimeStatus.COMPLETED
    assert "○ 1) تجهيز فيديو الحكام" in listed.message
    assert any(
        expected.isoformat() in listed.message for expected in {expected_before, expected_after}
    )
    assert completed.message == "أنجزت المهمة رقم 1: تجهيز فيديو الحكام."
    assert empty.message == "لا توجد مهام في هذه القائمة."
    assert "✓ 1) تجهيز فيديو الحكام" in history.message

    assert "تجهيز فيديو الحكام" not in repr(audit.records)


def test_runtime_replies_in_english_for_task_commands(config: AssistantConfig) -> None:
    runtime = build_runtime(config, effects=DryRunEffects())

    created = runtime.handle("add a task to submit the report today")
    listed = runtime.handle("show my tasks")

    assert created.message == "I added task 1: submit the report."
    assert listed.message.startswith("You have 1 task:")
    assert "submit the report" in listed.message


def test_existing_search_routing_is_not_shadowed_by_task_parser(
    router: DeterministicRouter,
) -> None:
    plan = router.route("ابحث عن ادارة المهام")

    assert plan is not None
    assert plan.actions[0].kind is ActionKind.OPEN_URL
    parsed = urlsplit(plan.actions[0].parameters["url"])
    assert parse_qs(parsed.query)["q"] == ["ادارة المهام"]
