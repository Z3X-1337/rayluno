"""Policy gate and bounded execution lifecycle for automation skills."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping
from contextlib import suppress

from .cancellation import CancellationToken
from .confirmation import ConfirmationAuthority, ConfirmationGrant, ConfirmationValidation
from .errors import (
    AutomationCancelled,
    AutomationConfigurationError,
    ConfirmationIssueError,
    ConfirmationNotRequiredError,
    InvalidArgumentsError,
)
from .models import (
    AutomationResult,
    ExecutionStatus,
    Permission,
    ResultCode,
    RiskLevel,
    SkillInvocation,
    SkillManifest,
)
from .registry import AutomationExecutor, ExecutorRegistry


class AutomationEngine:
    """Validate, confirm, execute, cancel, and time-box registered skills."""

    def __init__(
        self,
        manifests: Collection[SkillManifest],
        registry: ExecutorRegistry,
        confirmations: ConfirmationAuthority,
        *,
        allowed_permissions: Collection[Permission],
        confirmation_threshold: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        permissions = frozenset(allowed_permissions)
        if not all(isinstance(permission, Permission) for permission in permissions):
            raise AutomationConfigurationError(
                "allowed_permissions must contain only Permission values."
            )
        if not isinstance(confirmation_threshold, RiskLevel):
            raise AutomationConfigurationError("confirmation_threshold must be a RiskLevel.")
        self._registry = registry
        self._confirmations = confirmations
        self._allowed_permissions = permissions
        self._confirmation_threshold = confirmation_threshold
        self._manifests: dict[str, SkillManifest] = {}
        for manifest in manifests:
            if manifest.skill_id in self._manifests:
                raise AutomationConfigurationError(
                    f"Skill manifest {manifest.skill_id!r} is registered more than once."
                )
            executor = registry.get(manifest.executor_id)
            if executor is None:
                raise AutomationConfigurationError(
                    f"Skill {manifest.skill_id!r} references an unavailable executor."
                )
            if manifest.permissions != executor.permissions:
                raise AutomationConfigurationError(
                    f"Skill {manifest.skill_id!r} permissions do not exactly match its executor."
                )
            self._manifests[manifest.skill_id] = manifest

    @property
    def manifests(self) -> tuple[SkillManifest, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def request_confirmation(
        self,
        invocation: SkillInvocation,
        *,
        ttl_seconds: float | None = None,
    ) -> ConfirmationGrant:
        manifest, executor, blocked = self._preflight(invocation)
        if blocked is not None or manifest is None or executor is None:
            code = blocked.code.value if blocked is not None else ResultCode.UNKNOWN_SKILL.value
            raise ConfirmationIssueError(f"Cannot issue confirmation: {code}.")
        validation_error = self._validate_arguments(executor, invocation)
        if validation_error is not None:
            raise ConfirmationIssueError(
                f"Cannot issue confirmation: {validation_error.code.value}."
            )
        if not manifest.requires_confirmation(self._confirmation_threshold):
            raise ConfirmationNotRequiredError(
                f"Skill {manifest.skill_id!r} does not require confirmation."
            )
        return self._confirmations.issue(invocation, ttl_seconds=ttl_seconds)

    async def execute(
        self,
        invocation: SkillInvocation,
        *,
        confirmation_token: str | None = None,
        cancellation: CancellationToken | None = None,
    ) -> AutomationResult:
        manifest, executor, blocked = self._preflight(invocation)
        if blocked is not None or manifest is None or executor is None:
            return blocked or self._result(
                invocation,
                ExecutionStatus.BLOCKED,
                ResultCode.UNKNOWN_SKILL,
                "Skill is not registered.",
            )

        validation_error = self._validate_arguments(executor, invocation)
        if validation_error is not None:
            return validation_error

        cancellation = cancellation or CancellationToken()
        if cancellation.cancelled:
            return self._cancelled(invocation)

        confirmation_result = self._confirm(manifest, invocation, confirmation_token)
        if confirmation_result is not None:
            return confirmation_result

        return await self._execute_bounded(manifest, executor, invocation, cancellation)

    def _preflight(
        self, invocation: SkillInvocation
    ) -> tuple[
        SkillManifest | None,
        AutomationExecutor | None,
        AutomationResult | None,
    ]:
        manifest = self._manifests.get(invocation.skill_id)
        if manifest is None:
            return (
                None,
                None,
                self._result(
                    invocation,
                    ExecutionStatus.BLOCKED,
                    ResultCode.UNKNOWN_SKILL,
                    "Skill is not registered.",
                ),
            )
        if not manifest.permissions <= self._allowed_permissions:
            return (
                manifest,
                None,
                self._result(
                    invocation,
                    ExecutionStatus.BLOCKED,
                    ResultCode.PERMISSION_DENIED,
                    "One or more manifest permissions are disabled by policy.",
                ),
            )
        executor = self._registry.get(manifest.executor_id)
        if executor is None:  # defensive check if a custom mutable registry is supplied
            return (
                manifest,
                None,
                self._result(
                    invocation,
                    ExecutionStatus.BLOCKED,
                    ResultCode.PERMISSION_DENIED,
                    "The manifest executor is unavailable.",
                ),
            )
        return manifest, executor, None

    def _validate_arguments(
        self,
        executor: AutomationExecutor,
        invocation: SkillInvocation,
    ) -> AutomationResult | None:
        try:
            executor.validate(invocation.arguments)
        except InvalidArgumentsError as exc:
            return self._result(
                invocation,
                ExecutionStatus.BLOCKED,
                ResultCode.INVALID_ARGUMENTS,
                str(exc),
            )
        except Exception:
            return self._result(
                invocation,
                ExecutionStatus.FAILED,
                ResultCode.EXECUTOR_FAILED,
                "Executor validation failed.",
            )
        return None

    def _confirm(
        self,
        manifest: SkillManifest,
        invocation: SkillInvocation,
        token: str | None,
    ) -> AutomationResult | None:
        if not manifest.requires_confirmation(self._confirmation_threshold):
            return None
        if token is None:
            return self._result(
                invocation,
                ExecutionStatus.CONFIRMATION_REQUIRED,
                ResultCode.CONFIRMATION_REQUIRED,
                "Explicit confirmation is required for this risk level.",
            )
        validation = self._confirmations.consume(token, invocation)
        if validation is ConfirmationValidation.ACCEPTED:
            return None
        code = {
            ConfirmationValidation.INVALID: ResultCode.CONFIRMATION_INVALID,
            ConfirmationValidation.EXPIRED: ResultCode.CONFIRMATION_EXPIRED,
            ConfirmationValidation.MISMATCH: ResultCode.CONFIRMATION_MISMATCH,
        }[validation]
        return self._result(
            invocation,
            ExecutionStatus.BLOCKED,
            code,
            "Confirmation grant was not accepted.",
        )

    async def _execute_bounded(
        self,
        manifest: SkillManifest,
        executor: AutomationExecutor,
        invocation: SkillInvocation,
        cancellation: CancellationToken,
    ) -> AutomationResult:
        try:
            execution_task = asyncio.create_task(
                executor.execute(invocation.arguments, cancellation)
            )
        except Exception:
            return self._failed(invocation)
        cancellation_task = asyncio.create_task(cancellation.wait())
        try:
            done, _ = await asyncio.wait(
                {execution_task, cancellation_task},
                timeout=manifest.timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if execution_task in done:
                return await self._completed_execution(execution_task, invocation, cancellation)
            if cancellation_task in done:
                await self._stop_task(execution_task)
                return self._cancelled(invocation)
            cancellation.cancel()
            await self._stop_task(execution_task)
            return self._result(
                invocation,
                ExecutionStatus.TIMED_OUT,
                ResultCode.TIMED_OUT,
                "Skill exceeded its manifest timeout.",
            )
        except asyncio.CancelledError:
            cancellation.cancel()
            await self._stop_task(execution_task)
            raise
        finally:
            await self._stop_task(cancellation_task)

    async def _completed_execution(
        self,
        task: asyncio.Task[object],
        invocation: SkillInvocation,
        cancellation: CancellationToken,
    ) -> AutomationResult:
        try:
            data = await task
            if cancellation.cancelled:
                return self._cancelled(invocation)
            return self._result(
                invocation,
                ExecutionStatus.SUCCEEDED,
                ResultCode.OK,
                data=data,
            )
        except (AutomationCancelled, asyncio.CancelledError):
            cancellation.cancel()
            return self._cancelled(invocation)
        except InvalidArgumentsError as exc:
            return self._result(
                invocation,
                ExecutionStatus.BLOCKED,
                ResultCode.INVALID_ARGUMENTS,
                str(exc),
            )
        except Exception:
            return self._failed(invocation)

    @staticmethod
    async def _stop_task(task: asyncio.Task[object]) -> None:
        if not task.done():
            task.cancel()
        with suppress(Exception, asyncio.CancelledError):
            await task

    def _failed(self, invocation: SkillInvocation) -> AutomationResult:
        return self._result(
            invocation,
            ExecutionStatus.FAILED,
            ResultCode.EXECUTOR_FAILED,
            "Executor failed without exposing internal error details.",
        )

    def _cancelled(self, invocation: SkillInvocation) -> AutomationResult:
        return self._result(
            invocation,
            ExecutionStatus.CANCELLED,
            ResultCode.CANCELLED,
            "Skill execution was cancelled.",
        )

    @staticmethod
    def _result(
        invocation: SkillInvocation,
        status: ExecutionStatus,
        code: ResultCode,
        detail: str = "",
        *,
        data: object | None = None,
    ) -> AutomationResult:
        if data is None:
            payload = {}
        elif isinstance(data, Mapping):
            payload = data
        else:
            return AutomationResult(
                invocation,
                ExecutionStatus.FAILED,
                ResultCode.EXECUTOR_FAILED,
                "Executor returned an invalid result payload.",
            )
        try:
            return AutomationResult(invocation, status, code, detail, payload)
        except (TypeError, ValueError):
            return AutomationResult(
                invocation,
                ExecutionStatus.FAILED,
                ResultCode.EXECUTOR_FAILED,
                "Executor returned an invalid result payload.",
            )
