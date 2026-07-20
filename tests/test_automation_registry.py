from __future__ import annotations

from collections.abc import Mapping

import pytest

from future_assistant.automation import (
    BROWSER_SEARCH_MANIFEST,
    AutomationConfigurationError,
    AutomationEngine,
    CancellationToken,
    ConfirmationAuthority,
    DuplicateExecutorError,
    ExecutorNotAllowedError,
    ExecutorRegistry,
    Permission,
    RiskLevel,
    SkillManifest,
)


class FakeExecutor:
    executor_id = "test.executor"
    permissions = frozenset({Permission.BROWSER_OPEN_URL})

    def validate(self, arguments: Mapping[str, object]) -> None:
        return None

    async def execute(
        self,
        arguments: Mapping[str, object],
        cancellation: CancellationToken,
    ) -> Mapping[str, object]:
        return {}


def test_registry_only_accepts_preapproved_executor_ids() -> None:
    registry = ExecutorRegistry({"approved.executor"})

    with pytest.raises(ExecutorNotAllowedError):
        registry.register(FakeExecutor())

    assert registry.registered_executor_ids == frozenset()


def test_registry_rejects_duplicate_executor_registration() -> None:
    registry = ExecutorRegistry({FakeExecutor.executor_id})
    registry.register(FakeExecutor())

    with pytest.raises(DuplicateExecutorError):
        registry.register(FakeExecutor())


@pytest.mark.parametrize("executor_id", ["Bad Executor", "x", "shell;run"])
def test_registry_rejects_unsafe_allowlist_identifiers(executor_id: str) -> None:
    with pytest.raises(ValueError):
        ExecutorRegistry({executor_id})


def test_engine_fails_closed_when_manifest_executor_is_missing() -> None:
    registry = ExecutorRegistry({BROWSER_SEARCH_MANIFEST.executor_id})

    with pytest.raises(AutomationConfigurationError, match="unavailable executor"):
        AutomationEngine(
            [BROWSER_SEARCH_MANIFEST],
            registry,
            ConfirmationAuthority(),
            allowed_permissions={Permission.BROWSER_OPEN_URL},
        )


def test_engine_requires_exact_manifest_executor_permissions() -> None:
    registry = ExecutorRegistry({FakeExecutor.executor_id})
    registry.register(FakeExecutor())
    mismatched = SkillManifest(
        skill_id="test.skill",
        executor_id=FakeExecutor.executor_id,
        version="1.0.0",
        name="Mismatched",
        description="This should fail configuration.",
        permissions=frozenset({Permission.APP_LAUNCH}),
        risk_level=RiskLevel.LOW,
    )

    with pytest.raises(AutomationConfigurationError, match="exactly match"):
        AutomationEngine(
            [mismatched],
            registry,
            ConfirmationAuthority(),
            allowed_permissions={Permission.APP_LAUNCH},
        )


def test_engine_rejects_duplicate_skill_manifests() -> None:
    registry = ExecutorRegistry({FakeExecutor.executor_id})
    registry.register(FakeExecutor())
    manifest = SkillManifest(
        skill_id="test.skill",
        executor_id=FakeExecutor.executor_id,
        version="1.0.0",
        name="Duplicate",
        description="A duplicate manifest test.",
        permissions=FakeExecutor.permissions,
        risk_level=RiskLevel.LOW,
    )

    with pytest.raises(AutomationConfigurationError, match="more than once"):
        AutomationEngine(
            [manifest, manifest],
            registry,
            ConfirmationAuthority(),
            allowed_permissions=FakeExecutor.permissions,
        )
