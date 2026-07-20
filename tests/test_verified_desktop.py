from __future__ import annotations

from future_assistant.config import AssistantConfig
from future_assistant.domain import Action, ActionKind, Plan, PlanSource, RuntimeStatus
from future_assistant.runtime import DryRunEffects
from future_assistant.ui.today_window import TodayDesktopApi
from future_assistant.verified_runtime import build_verified_runtime
from future_assistant.verified_skills import HashChainedReceiptLedger


class FixedPlanner:
    def __init__(self, plan: Plan) -> None:
        self.plan_value = plan

    def plan(self, command: str) -> Plan:
        return self.plan_value


def test_desktop_exposes_one_time_confirmation_and_receipts_without_raw_command(
    tmp_path,  # noqa: ANN001
) -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    effects = DryRunEffects()
    ledger = HashChainedReceiptLedger()
    runtime = build_verified_runtime(
        AssistantConfig(
            require_wake_word=False,
            audit_path=None,
            tasks_path=tmp_path / "tasks.sqlite3",
            reminders_path=tmp_path / "reminders.sqlite3",
        ),
        effects=effects,
        planner=FixedPlanner(plan),
        receipt_ledger=ledger,
    )
    api = TodayDesktopApi(runtime)

    proposed = api.execute_command("شغّل الأداة السرية المناسبة للحساب")
    pending = api.get_verified_snapshot()

    assert proposed["status"] == RuntimeStatus.CONFIRMATION_REQUIRED.value
    assert proposed["confirmation"]["skill_id"] == "application.launch"
    assert proposed["confirmation"]["confirmation_id"]
    assert proposed["confirmation"]["argument_digest"]
    assert pending["pending"]["permission"] == "applications.launch"
    assert pending["integrity_ok"] is True
    assert pending["receipt_count"] == 1
    assert pending["receipts"][0]["event"] == "confirmation_requested"
    assert effects.operations == []
    assert "السرية" not in repr(pending)

    confirmation_id = proposed["confirmation"]["confirmation_id"]
    confirmed = api.approve_skill(confirmation_id)
    verified = api.get_verified_snapshot()

    assert confirmed["ok"] is True
    assert confirmed["receipt"]["receipt_id"].startswith("ryl-")
    assert confirmed["receipt"]["confirmation_state"] == "approved"
    assert verified["pending"] is None
    assert verified["integrity_ok"] is True
    assert verified["receipt_count"] == 3
    assert verified["receipts"][0]["skill_id"] == "application.launch"
    assert verified["receipts"][0]["event"] == "execution"
    assert verified["chain_head"] == verified["receipts"][0]["receipt_hash"]
    assert effects.operations == [("open_app", "calculator")]

    replay = api.approve_skill(confirmation_id)

    assert replay["ok"] is False
    assert effects.operations == [("open_app", "calculator")]
