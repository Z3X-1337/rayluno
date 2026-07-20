from future_assistant.config import AssistantConfig
from future_assistant.domain import Plan, PlanSource, RuntimeStatus
from future_assistant.judge_demo import (
    JUDGE_BLOCK_COMMAND_AR,
    JUDGE_DEMO_COMMAND_AR,
    JudgeDemoPlanner,
)
from future_assistant.runtime import DryRunEffects
from future_assistant.verified_runtime import build_verified_runtime
from future_assistant.verified_skills import HashChainedReceiptLedger


class EmptyPlanner:
    def plan(self, command: str) -> Plan | None:
        return None


def test_judge_demo_is_labelled_and_requires_confirmation_without_a_model() -> None:
    effects = DryRunEffects()
    ledger = HashChainedReceiptLedger()
    runtime = build_verified_runtime(
        AssistantConfig(require_wake_word=False, audit_path=None),
        effects=effects,
        planner=JudgeDemoPlanner(EmptyPlanner()),
        receipt_ledger=ledger,
    )

    proposed = runtime.handle(JUDGE_DEMO_COMMAND_AR)

    assert proposed.status is RuntimeStatus.CONFIRMATION_REQUIRED
    assert proposed.plan is not None
    assert proposed.plan.source is PlanSource.DEMO
    assert effects.operations == []

    executed = runtime.handle("تأكيد")

    assert executed.status is RuntimeStatus.COMPLETED
    assert len(effects.operations) == 2
    assert len(ledger.receipts) == 2
    assert all(
        receipt.policy_reason == "demo_proposed_consequential_skill"
        for receipt in ledger.receipts
    )


def test_judge_demo_can_show_fail_closed_behavior() -> None:
    runtime = build_verified_runtime(
        AssistantConfig(require_wake_word=False, audit_path=None),
        effects=DryRunEffects(),
        planner=JudgeDemoPlanner(EmptyPlanner()),
        receipt_ledger=HashChainedReceiptLedger(),
    )

    result = runtime.handle(JUDGE_BLOCK_COMMAND_AR)

    assert result.status is RuntimeStatus.BLOCKED
    assert "ليست مهارة مسجلة" in result.message
