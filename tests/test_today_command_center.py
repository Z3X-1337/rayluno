from __future__ import annotations

from datetime import datetime, timedelta, timezone

from future_assistant.config import AssistantConfig
from future_assistant.runtime import DryRunEffects, build_runtime
from future_assistant.ui.today_window import TodayDesktopApi

JO = timezone(timedelta(hours=3))


def _api(tmp_path, now: datetime) -> TodayDesktopApi:  # noqa: ANN001
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
    )
    runtime = build_runtime(config, effects=DryRunEffects(clock=lambda: now))
    return TodayDesktopApi(runtime, personal_clock=lambda: now)


def test_today_snapshot_exposes_real_local_task_and_reminder_data(tmp_path) -> None:  # noqa: ANN001
    now = datetime(2026, 7, 20, 17, 0, tzinfo=JO)
    api = _api(tmp_path, now)
    api._personal_tasks.create("مراجعة فيديو الحكام", priority="high", due="today")
    api._personal_reminders.create_after("إرسال العرض", minutes=10, priority="normal")

    snapshot = api.get_snapshot()["personal"]

    assert snapshot["available"] is True
    assert snapshot["counts"]["today"] == 1
    assert snapshot["counts"]["due_soon"] == 1
    assert snapshot["focus"]["title"] == "مراجعة فيديو الحكام"
    assert snapshot["next_reminder"]["title"] == "إرسال العرض"
    assert snapshot["items"][0]["title"] == "مراجعة فيديو الحكام"
    assert snapshot["privacy"] == "local"


def test_due_reminder_bridge_delivers_once_and_fails_closed(tmp_path) -> None:  # noqa: ANN001
    current = [datetime(2026, 7, 20, 17, 0, tzinfo=JO)]
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
    )
    runtime = build_runtime(config, effects=DryRunEffects(clock=lambda: current[0]))
    api = TodayDesktopApi(runtime, personal_clock=lambda: current[0])
    reminder = api._personal_reminders.create_after("إرسال العرض", minutes=1)

    current[0] += timedelta(minutes=1)
    first = api.poll_due_reminders()
    second = api.poll_due_reminders()

    assert first["ok"] is True
    assert first["events"][0]["id"] == reminder.id
    assert second == {"ok": True, "events": []}

    api._personal_reminders.store.due = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError())
    assert api.poll_due_reminders() == {"ok": False, "events": []}
