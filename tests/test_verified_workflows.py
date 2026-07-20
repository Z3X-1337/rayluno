from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from future_assistant.automation import (
    APP_LAUNCH_MANIFEST,
    BROWSER_SEARCH_MANIFEST,
    AppLaunchExecutor,
    AutomationEngine,
    BrowserSearchExecutor,
    ConfirmationAuthority,
    ExecutorRegistry,
    Permission,
    SkillInvocation,
)
from future_assistant.verified_skills import (
    ReceiptJournal,
    UnknownConfirmationError,
    VerifiedSkillSession,
)
from future_assistant.verified_workflows import (
    VerifiedWorkflowSession,
    WorkflowPlan,
    WorkflowStateError,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepStatus,
)


class FakeEffects:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.apps: list[str] = []

    async def open_url(self, url: str) -> None:
        self.urls.append(url)

    async def launch_app(self, app_id: str) -> None:
        self.apps.append(app_id)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


def _workflow_session(
    *,
    clock: MutableClock | None = None,
) -> tuple[VerifiedWorkflowSession, FakeEffects, ReceiptJournal, MutableClock]:
    current = clock or MutableClock()
    effects = FakeEffects()
    journal = ReceiptJournal()
    registry = ExecutorRegistry(
        {
            BROWSER_SEARCH_MANIFEST.executor_id,
            APP_LAUNCH_MANIFEST.executor_id,
        }
    )
    registry.register(BrowserSearchExecutor(effects))
    registry.register(AppLaunchExecutor(effects, allowed_app_ids={"calculator", "notepad"}))
    engine = AutomationEngine(
        [BROWSER_SEARCH_MANIFEST, APP_LAUNCH_MANIFEST],
        registry,
        ConfirmationAuthority(clock=current),
        allowed_permissions={Permission.BROWSER_OPEN_URL, Permission.APP_LAUNCH},
    )
    skills = VerifiedSkillSession(engine, receipts=journal, clock=current)
    return VerifiedWorkflowSession(skills), effects, journal, current


def _step(
    step_id: str,
    label: str,
    skill_id: str,
    arguments: dict[str, object],
    *,
    request_id: str,
) -> WorkflowStep:
    return WorkflowStep(
        step_id,
        label,
        SkillInvocation(
            skill_id,
            arguments,
            actor_id="local-user",
            request_id=request_id,
        ),
    )


def _demo_plan(*, workflow_id: str = "workflow-demo-001") -> WorkflowPlan:
    return WorkflowPlan(
        "Prepare the judge workspace",
        (
            _step(
                "research.checklist",
                "Find a concise demo checklist",
                "browser.search",
                {"query": "private presentation checklist"},
                request_id="request-search-one",
            ),
            _step(
                "workspace.notepad",
                "Open the approved notes application",
                "app.launch",
                {"app_id": "notepad"},
                request_id="request-app-one",
            ),
            _step(
                "research.timing",
                "Find three minute demo timing guidance",
                "browser.search",
                {"query": "three minute product demo timing"},
                request_id="request-search-two",
            ),
        ),
        workflow_id=workflow_id,
    )


def test_preview_is_bounded_and_redacts_argument_values() -> None:
    workflows, _, _, _ = _workflow_session()
    snapshot = workflows.preview(_demo_plan())

    exported = json.dumps(snapshot.to_dict(), ensure_ascii=False)

    assert snapshot.status is WorkflowStatus.READY
    assert len(snapshot.workflow_digest) == 64
    assert [step.status for step in snapshot.steps] == [
        WorkflowStepStatus.PENDING,
        WorkflowStepStatus.PENDING,
        WorkflowStepStatus.PENDING,
    ]
    assert snapshot.steps[0].argument_keys == ("query",)
    assert snapshot.steps[1].argument_keys == ("app_id",)
    assert "private presentation checklist" not in exported
    assert "notepad" not in exported
    assert "token" not in exported.casefold()


def test_low_risk_workflow_runs_all_steps_serially() -> None:
    workflows, effects, journal, _ = _workflow_session()
    plan = WorkflowPlan(
        "Research sequence",
        (
            _step(
                "search.first",
                "Run first search",
                "browser.search",
                {"query": "first private query"},
                request_id="request-first",
            ),
            _step(
                "search.second",
                "Run second search",
                "browser.search",
                {"query": "second private query"},
                request_id="request-second",
            ),
        ),
        workflow_id="workflow-searches",
    )

    snapshot = asyncio.run(workflows.start(plan))

    assert snapshot.status is WorkflowStatus.SUCCEEDED
    assert snapshot.current_step is None
    assert [step.status for step in snapshot.steps] == [
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.SUCCEEDED,
    ]
    assert len(effects.urls) == 2
    assert effects.apps == []
    assert len(journal.receipts) == 2
    assert ReceiptJournal.verify(journal.receipts)


def test_workflow_pauses_before_high_risk_step_and_resumes_after_approval() -> None:
    workflows, effects, journal, _ = _workflow_session()

    paused = asyncio.run(workflows.start(_demo_plan()))

    assert paused.status is WorkflowStatus.CONFIRMATION_REQUIRED
    assert paused.current_step == 1
    assert [step.status for step in paused.steps] == [
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.CONFIRMATION_REQUIRED,
        WorkflowStepStatus.PENDING,
    ]
    assert len(effects.urls) == 1
    assert effects.apps == []
    confirmation = paused.steps[1].pending_confirmation
    assert confirmation is not None
    assert confirmation.skill_id == "app.launch"

    completed = asyncio.run(workflows.approve(confirmation.confirmation_id))

    assert completed.status is WorkflowStatus.SUCCEEDED
    assert completed.current_step is None
    assert [step.status for step in completed.steps] == [
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.SUCCEEDED,
    ]
    assert effects.apps == ["notepad"]
    assert len(effects.urls) == 2
    assert len(journal.receipts) == 4
    assert ReceiptJournal.verify(journal.receipts)
    with pytest.raises(UnknownConfirmationError):
        asyncio.run(workflows.approve(confirmation.confirmation_id))
    assert effects.apps == ["notepad"]


def test_rejection_cancels_workflow_and_skips_remaining_steps() -> None:
    workflows, effects, journal, _ = _workflow_session()
    paused = asyncio.run(workflows.start(_demo_plan()))
    confirmation = paused.steps[1].pending_confirmation
    assert confirmation is not None

    cancelled = asyncio.run(workflows.reject(confirmation.confirmation_id))

    assert cancelled.status is WorkflowStatus.CANCELLED
    assert cancelled.current_step is None
    assert [step.status for step in cancelled.steps] == [
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.CANCELLED,
        WorkflowStepStatus.SKIPPED,
    ]
    assert effects.apps == []
    assert len(effects.urls) == 1
    assert len(journal.receipts) == 3
    assert journal.receipts[-1].confirmation_state == "rejected"


def test_expired_confirmation_blocks_workflow_and_skips_remaining_steps() -> None:
    clock = MutableClock()
    workflows, effects, _, _ = _workflow_session(clock=clock)
    paused = asyncio.run(workflows.start(_demo_plan()))
    confirmation = paused.steps[1].pending_confirmation
    assert confirmation is not None
    clock.value += timedelta(minutes=3)

    blocked = asyncio.run(workflows.approve(confirmation.confirmation_id))

    assert blocked.status is WorkflowStatus.BLOCKED
    assert [step.status for step in blocked.steps] == [
        WorkflowStepStatus.SUCCEEDED,
        WorkflowStepStatus.BLOCKED,
        WorkflowStepStatus.SKIPPED,
    ]
    assert effects.apps == []
    assert len(effects.urls) == 1


def test_unknown_skill_is_rejected_before_any_workflow_effect() -> None:
    workflows, effects, journal, _ = _workflow_session()
    plan = WorkflowPlan(
        "Unknown capability",
        (
            _step(
                "unknown.step",
                "Attempt unknown skill",
                "unknown.skill",
                {},
                request_id="request-unknown",
            ),
        ),
        workflow_id="workflow-unknown",
    )

    with pytest.raises(ValueError, match="unknown skills"):
        asyncio.run(workflows.start(plan))

    assert effects.urls == []
    assert effects.apps == []
    assert journal.receipts == ()


def test_workflow_identifier_cannot_be_started_twice() -> None:
    workflows, _, _, _ = _workflow_session()
    plan = WorkflowPlan(
        "Single search",
        (
            _step(
                "search.once",
                "Run one search",
                "browser.search",
                {"query": "one"},
                request_id="request-once",
            ),
        ),
        workflow_id="workflow-single",
    )

    asyncio.run(workflows.start(plan))
    with pytest.raises(WorkflowStateError, match="already been started"):
        asyncio.run(workflows.start(plan))


def test_workflow_plan_rejects_recursion_duplicates_and_excess_steps() -> None:
    with pytest.raises(ValueError, match="cannot invoke other workflows"):
        _step(
            "workflow.child",
            "Recursive child",
            "workflow.child",
            {},
            request_id="request-recursive",
        )

    duplicate = _step(
        "search.same",
        "First",
        "browser.search",
        {"query": "one"},
        request_id="request-duplicate-one",
    )
    with pytest.raises(ValueError, match="identifiers must be unique"):
        WorkflowPlan(
            "Duplicate steps",
            (duplicate, duplicate),
            workflow_id="workflow-duplicate",
        )

    steps = tuple(
        _step(
            f"search.step-{index}",
            f"Search {index}",
            "browser.search",
            {"query": str(index)},
            request_id=f"request-step-{index}",
        )
        for index in range(6)
    )
    with pytest.raises(ValueError, match="1-5 steps"):
        WorkflowPlan("Too many steps", steps, workflow_id="workflow-too-many")


def test_all_steps_must_share_actor_and_request_ids_must_be_unique() -> None:
    first = _step(
        "search.first",
        "First",
        "browser.search",
        {"query": "one"},
        request_id="same-request",
    )
    duplicate_request = _step(
        "search.second",
        "Second",
        "browser.search",
        {"query": "two"},
        request_id="same-request",
    )
    with pytest.raises(ValueError, match="request identifiers must be unique"):
        WorkflowPlan(
            "Duplicate request IDs",
            (first, duplicate_request),
            workflow_id="workflow-duplicate-requests",
        )

    different_actor = WorkflowStep(
        "search.other",
        "Other actor",
        SkillInvocation(
            "browser.search",
            {"query": "three"},
            actor_id="other-user",
            request_id="request-other-actor",
        ),
    )
    with pytest.raises(ValueError, match="same actor_id"):
        WorkflowPlan(
            "Mixed actors",
            (first, different_actor),
            workflow_id="workflow-mixed-actors",
        )
