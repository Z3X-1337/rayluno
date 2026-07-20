from datetime import UTC, datetime

from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import (
    Action,
    ActionKind,
    Plan,
    PlanSource,
    RuntimeStatus,
    VolumeOperation,
)
from future_assistant.runtime import AssistantRuntime
from future_assistant.verified_runtime import VerifiedAssistantRuntime
from future_assistant.verified_skills import HashChainedReceiptLedger


class FakeEffects:
    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []
        self.now = datetime(2026, 7, 20, 12, 0)

    def open_url(self, url: str) -> None:
        self.operations.append(("open_url", url))

    def open_app(self, app_id: str) -> None:
        self.operations.append(("open_app", app_id))

    def current_time(self) -> datetime:
        self.operations.append(("current_time",))
        return self.now

    def control_volume(self, operation: VolumeOperation, steps: int) -> None:
        self.operations.append(("control_volume", operation.value, steps))


class FixedPlanner:
    def __init__(self, plan: Plan | None) -> None:
        self.result = plan

    def plan(self, command: str) -> Plan | None:
        return self.result


class QueuePlanner:
    def __init__(self, plans: list[Plan]) -> None:
        self.plans = plans

    def plan(self, command: str) -> Plan | None:
        return self.plans.pop(0)


def _runtime(
    planner,
) -> tuple[VerifiedAssistantRuntime, FakeEffects, MemoryAuditLogger, HashChainedReceiptLedger]:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    base = AssistantRuntime(
        AssistantConfig(audit_path=None),
        planner,
        effects,
        audit,
    )
    ledger = HashChainedReceiptLedger(clock=lambda: datetime(2026, 7, 20, 9, 0, tzinfo=UTC))
    runtime = VerifiedAssistantRuntime(base, receipt_ledger=ledger)
    return runtime, effects, audit, ledger


def test_model_proposed_app_launch_requires_one_time_confirmation() -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    runtime, effects, audit, ledger = _runtime(FixedPlanner(plan))

    proposed = runtime.handle("يا رايلونو شغل الأداة المناسبة للحساب")

    assert proposed.status is RuntimeStatus.CONFIRMATION_REQUIRED
    assert "application.launch" in proposed.message
    assert "applications.launch" in proposed.message
    assert effects.operations == []
    assert ledger.receipts == []

    confirmed = runtime.handle("يا رايلونو تأكيد")

    assert confirmed.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("open_app", "calculator")]
    assert "ryl-" in confirmed.message
    assert len(ledger.receipts) == 1
    assert ledger.receipts[0].skill_id == "application.launch"
    assert [record.event for record in audit.records] == [
        "command_received",
        "confirmation_requested",
        "confirmation_accepted",
        "action_executed",
    ]


def test_pending_model_action_can_be_cancelled_without_side_effect() -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_URL, {"url": "https://github.com/", "purpose": "site"}),),
        source=PlanSource.OLLAMA,
    )
    runtime, effects, audit, ledger = _runtime(FixedPlanner(plan))

    runtime.handle("يا رايلونو افتح المنصة المناسبة للمستودعات")
    cancelled = runtime.handle("يا رايلونو إلغاء")

    assert cancelled.status is RuntimeStatus.COMPLETED
    assert effects.operations == []
    assert ledger.receipts == []
    assert audit.records[-1].event == "confirmation_cancelled"


def test_deterministic_registered_skill_executes_and_receipt_hides_query_values() -> None:
    plan = Plan(
        actions=(
            Action(
                ActionKind.OPEN_URL,
                {
                    "url": "https://www.google.com/search?q=secret-demo-query",
                    "purpose": "search",
                },
            ),
        ),
        source=PlanSource.DETERMINISTIC,
    )
    runtime, effects, _, ledger = _runtime(FixedPlanner(plan))

    result = runtime.handle("يا رايلونو ابحث")

    assert result.status is RuntimeStatus.COMPLETED
    assert effects.operations[0][0] == "open_url"
    assert len(ledger.receipts) == 1
    assert "secret-demo-query" not in repr(ledger.receipts[0])
    assert ledger.receipts[0].action["query_keys"] == ["q"]


def test_receipts_form_a_hash_chain_across_actions() -> None:
    planner = QueuePlanner(
        [
            Plan(actions=(Action(ActionKind.REPORT_TIME),)),
            Plan(
                actions=(
                    Action(
                        ActionKind.CONTROL_VOLUME,
                        {"operation": VolumeOperation.UP.value, "steps": 2},
                    ),
                )
            ),
        ]
    )
    runtime, _, _, ledger = _runtime(planner)

    runtime.handle("يا رايلونو كم الساعة")
    runtime.handle("يا رايلونو ارفع الصوت")

    first, second = ledger.receipts
    assert first.previous_hash == ""
    assert second.previous_hash == first.receipt_hash
    assert first.receipt_hash != second.receipt_hash


def test_new_command_invalidates_stale_pending_confirmation() -> None:
    planner = QueuePlanner(
        [
            Plan(
                actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
                source=PlanSource.OLLAMA,
            ),
            Plan(actions=(Action(ActionKind.REPORT_TIME),)),
        ]
    )
    runtime, effects, audit, _ = _runtime(planner)

    runtime.handle("يا رايلونو اختر تطبيق الحساب")
    replacement = runtime.handle("يا رايلونو كم الساعة")
    stale_confirmation = runtime.handle("يا رايلونو تأكيد")

    assert replacement.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("current_time",)]
    assert stale_confirmation.status is RuntimeStatus.UNHANDLED
    assert "لا يوجد" in stale_confirmation.message
    assert any(record.event == "confirmation_replaced" for record in audit.records)
