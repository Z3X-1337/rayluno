"""Explicit allowlist registry for reviewed automation executors."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Protocol

from .cancellation import CancellationToken
from .errors import (
    AutomationConfigurationError,
    DuplicateExecutorError,
    ExecutorNotAllowedError,
)
from .models import Permission, validate_identifier


class AutomationExecutor(Protocol):
    executor_id: str
    permissions: frozenset[Permission]

    def validate(self, arguments: Mapping[str, object]) -> None: ...

    async def execute(
        self,
        arguments: Mapping[str, object],
        cancellation: CancellationToken,
    ) -> Mapping[str, object]: ...


class ExecutorRegistry:
    """Registry that cannot register an executor unless its ID was pre-approved."""

    def __init__(self, allowed_executor_ids: Collection[str]) -> None:
        allowed = frozenset(allowed_executor_ids)
        for executor_id in allowed:
            validate_identifier(executor_id, field_name="executor_id")
        self._allowed = allowed
        self._executors: dict[str, AutomationExecutor] = {}

    @property
    def allowed_executor_ids(self) -> frozenset[str]:
        return self._allowed

    @property
    def registered_executor_ids(self) -> frozenset[str]:
        return frozenset(self._executors)

    def register(self, executor: AutomationExecutor) -> None:
        executor_id = getattr(executor, "executor_id", None)
        if not isinstance(executor_id, str):
            raise AutomationConfigurationError("Executor must expose a valid executor_id.")
        validate_identifier(executor_id, field_name="executor_id")
        if executor_id not in self._allowed:
            raise ExecutorNotAllowedError(f"Executor {executor_id!r} is not allowlisted.")
        if executor_id in self._executors:
            raise DuplicateExecutorError(f"Executor {executor_id!r} is already registered.")
        permissions = getattr(executor, "permissions", None)
        if (
            not isinstance(permissions, frozenset)
            or not permissions
            or not all(isinstance(permission, Permission) for permission in permissions)
        ):
            raise AutomationConfigurationError(
                "Executor permissions must be a non-empty frozenset of Permission values."
            )
        if not callable(getattr(executor, "validate", None)) or not callable(
            getattr(executor, "execute", None)
        ):
            raise AutomationConfigurationError("Executor must implement validate() and execute().")
        self._executors[executor_id] = executor

    def get(self, executor_id: str) -> AutomationExecutor | None:
        if executor_id not in self._allowed:
            return None
        return self._executors.get(executor_id)
