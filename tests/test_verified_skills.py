import json
from datetime import UTC, datetime, timedelta

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


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def _runtime(
    planner,
    *,
    clock: MutableClock | None = None,
    ledger: HashChainedReceiptLedger | None = None,
    ttl_seconds: int = 45,
) -> tuple[VerifiedAssistantRuntime, FakeEffects, MemoryAuditLogger, HashChainedReceiptLedger]:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    base = AssistantRuntime(
        AssistantConfig(audit_path=None),
        planner,
        effects,
        audit,
    )
    clock = clock or MutableClock(datetime(2026, 7, 20, 9, 0, tzinfo=UTC))
    ledger = ledger or HashChainedReceiptLedger(clock=clock)
    runtime = VerifiedAssistantRuntime(
        base,
        receipt_ledger=ledger,
        clock=clock,
        confirmation_ttl_seconds=ttl_seconds,
    )
    return runtime, effects, audit, ledger


def test_model_proposed_app_launch_requires_one_time_confirmation() -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    runtime, effects, audit, ledger = _runtime(FixedPlanner(plan))

    proposed = runtime.handle("يا رايلونو شغل الأداة المناسبة للحساب")
    pending = runtime.pending_public()

    assert proposed.status is RuntimeStatus.CONFIRMATION_REQUIRED
    assert "application.launch" in proposed.message
    assert "applications.launch" in proposed.message
    assert effects.operations == []
    assert pending is not None
    assert pending["confirmation_id"]
    assert pending["argument_digest"]
    assert len(ledger.receipts) == 1
    assert ledger.receipts[0].event == "confirmation_requested"
    assert ledger.receipts[0].status == "pending"

    confirmed = runtime.approve(str(pending["confirmation_id"]))

    assert confirmed.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("open_app", "calculator")]
    assert "ryl-" in confirmed.message
    assert len(ledger.receipts) == 2
    assert ledger.receipts[-1].skill_id == "application.launch"
    assert ledger.receipts[-1].confirmation_state == "approved"

    replay = runtime.approve(str(pending["confirmation_id"]))

    assert replay.status is RuntimeStatus.UNHANDLED
    assert effects.operations == [("open_app", "calculator")]
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
    pending = runtime.pending_public()
    assert pending is not None
    cancelled = runtime.reject(str(pending["confirmation_id"]))

    assert cancelled.status is RuntimeStatus.COMPLETED
    assert effects.operations == []
    assert [receipt.status for receipt in ledger.receipts] == ["pending", "cancelled"]
    assert ledger.receipts[-1].confirmation_state == "rejected"
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
    assert ledger.receipts[0].argument_keys == ("purpose", "url")
    assert len(ledger.receipts[0].argument_digest) == 64


def test_receipts_form_a_verified_hash_chain_across_actions() -> None:
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
    assert first.previous_hash == "0" * 64
    assert second.previous_hash == first.receipt_hash
    assert first.receipt_hash != second.receipt_hash
    assert ledger.verify_integrity()


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
    runtime, effects, audit, ledger = _runtime(planner)

    runtime.handle("يا رايلونو اختر تطبيق الحساب")
    replacement = runtime.handle("يا رايلونو كم الساعة")
    stale_confirmation = runtime.handle("يا رايلونو تأكيد")

    assert replacement.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("current_time",)]
    assert stale_confirmation.status is RuntimeStatus.UNHANDLED
    assert "لا يوجد" in stale_confirmation.message
    assert [receipt.status for receipt in ledger.receipts] == [
        "pending",
        "cancelled",
        "completed",
    ]
    assert any(record.event == "confirmation_replaced" for record in audit.records)


def test_expired_confirmation_is_recorded_without_side_effect() -> None:
    clock = MutableClock(datetime(2026, 7, 20, 9, 0, tzinfo=UTC))
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    runtime, effects, audit, ledger = _runtime(
        FixedPlanner(plan),
        clock=clock,
        ttl_seconds=10,
    )

    runtime.handle("يا رايلونو افتح الحاسبة")
    pending = runtime.pending_public()
    assert pending is not None
    clock.advance(seconds=11)

    expired = runtime.approve(str(pending["confirmation_id"]))

    assert expired.status is RuntimeStatus.BLOCKED
    assert effects.operations == []
    assert [receipt.status for receipt in ledger.receipts] == ["pending", "expired"]
    assert ledger.receipts[-1].event == "confirmation_expired"
    assert audit.records[-1].event == "confirmation_expired"


def test_invalid_handle_does_not_consume_valid_pending_plan() -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    runtime, effects, _, _ = _runtime(FixedPlanner(plan))

    runtime.handle("يا رايلونو افتح الحاسبة")
    pending = runtime.pending_public()
    assert pending is not None

    invalid = runtime.approve("not-the-right-handle")
    assert invalid.status is RuntimeStatus.BLOCKED
    assert effects.operations == []
    assert runtime.pending_public() is not None

    valid = runtime.approve(str(pending["confirmation_id"]))
    assert valid.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("open_app", "calculator")]


def test_tampered_receipt_file_disables_future_verified_execution(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "execution-receipts.jsonl"
    clock = MutableClock(datetime(2026, 7, 20, 9, 0, tzinfo=UTC))
    first_ledger = HashChainedReceiptLedger(path, clock=clock)
    plan = Plan(actions=(Action(ActionKind.REPORT_TIME),))
    first_runtime, first_effects, _, _ = _runtime(
        FixedPlanner(plan),
        clock=clock,
        ledger=first_ledger,
    )

    completed = first_runtime.handle("يا رايلونو كم الساعة")
    assert completed.status is RuntimeStatus.COMPLETED
    assert first_effects.operations == [("current_time",)]

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["status"] = "failed"
    path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")

    tampered_ledger = HashChainedReceiptLedger(path, clock=clock)
    blocked_runtime, blocked_effects, _, _ = _runtime(
        FixedPlanner(plan),
        clock=clock,
        ledger=tampered_ledger,
    )

    blocked = blocked_runtime.handle("يا رايلونو كم الساعة")

    assert not tampered_ledger.integrity_ok
    assert blocked.status is RuntimeStatus.BLOCKED
    assert "سجل الإيصالات" in blocked.message
    assert blocked_effects.operations == []
