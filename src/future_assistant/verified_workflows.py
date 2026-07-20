"""Bounded multi-step workflows built on Rayluno's verified skill session.

A workflow is a finite, immutable list of reviewed skill invocations. Execution is serial,
pauses before confirmed effects, and stops on the first rejection, block, timeout, or
failure. Public snapshots expose argument names and digests, never raw values.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from .automation import ExecutionStatus, SkillInvocation
from .automation.models import canonical_json
from .verified_skills import (
    ExecutionReceipt,
    PendingConfirmation,
    UnknownConfirmationError,
    VerifiedSkillSession,
)

_MAX_WORKFLOW_STEPS: Final = 5
_STEP_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_WORKFLOW_SCHEMA: Final = "rayluno.verified-workflow/v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_label(value: str, *, field_name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be text.")
    cleaned = " ".join(value.strip().split())
    if not cleaned or len(cleaned) > maximum:
        raise ValueError(f"{field_name} must contain 1-{maximum} characters.")
    if any(ord(character) < 32 for character in cleaned):
        raise ValueError(f"{field_name} cannot contain control characters.")
    return cleaned


class WorkflowStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    CONFIRMATION_REQUIRED = "confirmation_required"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.BLOCKED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.TIMED_OUT,
            WorkflowStatus.FAILED,
        }


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CONFIRMATION_REQUIRED = "confirmation_required"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    label: str
    invocation: SkillInvocation

    def __post_init__(self) -> None:
        if (
            not isinstance(self.step_id, str)
            or not 3 <= len(self.step_id) <= 80
            or not _STEP_IDENTIFIER.fullmatch(self.step_id)
        ):
            raise ValueError("step_id must be a lowercase identifier of 3-80 characters.")
        object.__setattr__(
            self,
            "label",
            _validate_label(self.label, field_name="label", maximum=120),
        )
        if not isinstance(self.invocation, SkillInvocation):
            raise TypeError("invocation must be a SkillInvocation.")
        if self.invocation.skill_id.startswith("workflow."):
            raise ValueError("Workflows cannot invoke other workflows recursively.")


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    name: str
    steps: tuple[WorkflowStep, ...]
    workflow_id: str = field(default_factory=lambda: secrets.token_hex(16))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _validate_label(self.name, field_name="name", maximum=120),
        )
        if not isinstance(self.workflow_id, str) or not 8 <= len(self.workflow_id) <= 128:
            raise ValueError("workflow_id must contain 8-128 characters.")
        try:
            steps = tuple(self.steps)
        except TypeError as exc:
            raise TypeError("steps must be an iterable of WorkflowStep values.") from exc
        if not 1 <= len(steps) <= _MAX_WORKFLOW_STEPS:
            raise ValueError(f"A workflow must contain 1-{_MAX_WORKFLOW_STEPS} steps.")
        if not all(isinstance(step, WorkflowStep) for step in steps):
            raise TypeError("steps must contain only WorkflowStep values.")
        step_ids = [step.step_id for step in steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Workflow step identifiers must be unique.")
        request_ids = [step.invocation.request_id for step in steps]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Workflow invocation request identifiers must be unique.")
        actors = {step.invocation.actor_id for step in steps}
        if len(actors) != 1:
            raise ValueError("Every workflow step must use the same actor_id.")
        object.__setattr__(self, "steps", steps)

    @property
    def actor_id(self) -> str:
        return self.steps[0].invocation.actor_id

    @property
    def digest(self) -> str:
        value = "|".join(
            ":".join(
                (
                    step.step_id,
                    step.invocation.skill_id,
                    step.invocation.request_id,
                    canonical_json(step.invocation.arguments),
                )
            )
            for step in self.steps
        )
        return _sha256(f"{self.workflow_id}:{self.name}:{value}")


@dataclass(frozen=True, slots=True)
class WorkflowStepView:
    step_id: str
    label: str
    skill_id: str
    skill_version: str
    risk_level: str
    permissions: tuple[str, ...]
    status: WorkflowStepStatus
    argument_keys: tuple[str, ...]
    argument_digest: str
    receipt: ExecutionReceipt | None = None
    pending_confirmation: PendingConfirmation | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "label": self.label,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "risk_level": self.risk_level,
            "permissions": list(self.permissions),
            "status": self.status.value,
            "argument_keys": list(self.argument_keys),
            "argument_digest": self.argument_digest,
            "receipt": self.receipt.to_dict() if self.receipt is not None else None,
            "pending_confirmation": (
                self.pending_confirmation.to_dict()
                if self.pending_confirmation is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    schema: str
    workflow_id: str
    name: str
    workflow_digest: str
    actor_id: str
    status: WorkflowStatus
    current_step: int | None
    created_at: datetime
    updated_at: datetime
    steps: tuple[WorkflowStepView, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "workflow_id": self.workflow_id,
            "name": self.name,
            "workflow_digest": self.workflow_digest,
            "actor_id": self.actor_id,
            "status": self.status.value,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(slots=True)
class _MutableStep:
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    receipt: ExecutionReceipt | None = None
    pending_confirmation: PendingConfirmation | None = None


@dataclass(slots=True)
class _WorkflowRun:
    plan: WorkflowPlan
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    steps: list[_MutableStep]
    current_step: int | None = None


class UnknownWorkflowError(LookupError):
    """Raised when a workflow identifier is unknown to this process."""


class WorkflowStateError(RuntimeError):
    """Raised when a workflow operation is invalid for its current state."""


class VerifiedWorkflowSession:
    """Execute finite workflows serially through a VerifiedSkillSession."""

    def __init__(self, skills: VerifiedSkillSession) -> None:
        if not isinstance(skills, VerifiedSkillSession):
            raise TypeError("skills must be a VerifiedSkillSession.")
        self._skills = skills
        self._manifests = {manifest.skill_id: manifest for manifest in skills.manifests}
        self._runs: dict[str, _WorkflowRun] = {}
        self._pending: dict[str, tuple[str, int]] = {}
        self._lock = threading.RLock()

    def preview(self, plan: WorkflowPlan) -> WorkflowSnapshot:
        self._validate_plan(plan)
        now = _utc_now()
        run = _WorkflowRun(
            plan,
            WorkflowStatus.READY,
            now,
            now,
            [_MutableStep() for _ in plan.steps],
        )
        return self._snapshot(run)

    async def start(self, plan: WorkflowPlan) -> WorkflowSnapshot:
        self._validate_plan(plan)
        now = _utc_now()
        with self._lock:
            if plan.workflow_id in self._runs:
                raise WorkflowStateError("This workflow_id has already been started.")
            run = _WorkflowRun(
                plan,
                WorkflowStatus.READY,
                now,
                now,
                [_MutableStep() for _ in plan.steps],
            )
            self._runs[plan.workflow_id] = run
        return await self._advance(plan.workflow_id)

    def get(self, workflow_id: str) -> WorkflowSnapshot:
        with self._lock:
            run = self._runs.get(workflow_id)
            if run is None:
                raise UnknownWorkflowError("Unknown workflow_id.")
            return self._snapshot(run)

    async def approve(self, confirmation_id: str) -> WorkflowSnapshot:
        workflow_id, step_index = self._consume_pending(confirmation_id)
        with self._lock:
            run = self._require_run(workflow_id)
            step = run.steps[step_index]
            if step.status is not WorkflowStepStatus.CONFIRMATION_REQUIRED:
                raise WorkflowStateError("The workflow step is not awaiting confirmation.")
            step.status = WorkflowStepStatus.RUNNING
            step.pending_confirmation = None
            run.status = WorkflowStatus.RUNNING
            run.updated_at = _utc_now()

        try:
            outcome = await self._skills.approve(confirmation_id)
        except UnknownConfirmationError:
            with self._lock:
                run = self._require_run(workflow_id)
                run.steps[step_index].status = WorkflowStepStatus.BLOCKED
                run.status = WorkflowStatus.BLOCKED
                run.updated_at = _utc_now()
                self._skip_remaining(run, step_index + 1)
                return self._snapshot(run)

        with self._lock:
            run = self._require_run(workflow_id)
            mutable = run.steps[step_index]
            mutable.receipt = outcome.receipt
            mutable.status = self._step_status(outcome.receipt.status)
            run.updated_at = _utc_now()
            if mutable.status is not WorkflowStepStatus.SUCCEEDED:
                run.status = self._workflow_status(mutable.status)
                self._skip_remaining(run, step_index + 1)
                return self._snapshot(run)
        return await self._advance(workflow_id)

    async def reject(self, confirmation_id: str) -> WorkflowSnapshot:
        workflow_id, step_index = self._consume_pending(confirmation_id)
        with self._lock:
            run = self._require_run(workflow_id)
            step = run.steps[step_index]
            if step.status is not WorkflowStepStatus.CONFIRMATION_REQUIRED:
                raise WorkflowStateError("The workflow step is not awaiting confirmation.")
        try:
            outcome = self._skills.reject(confirmation_id)
        except UnknownConfirmationError as exc:
            raise WorkflowStateError("The confirmation expired or was already consumed.") from exc

        with self._lock:
            run = self._require_run(workflow_id)
            mutable = run.steps[step_index]
            mutable.pending_confirmation = None
            mutable.receipt = outcome.receipt
            mutable.status = WorkflowStepStatus.CANCELLED
            run.status = WorkflowStatus.CANCELLED
            run.updated_at = _utc_now()
            self._skip_remaining(run, step_index + 1)
            return self._snapshot(run)

    async def _advance(self, workflow_id: str) -> WorkflowSnapshot:
        while True:
            with self._lock:
                run = self._require_run(workflow_id)
                if run.status.terminal:
                    return self._snapshot(run)
                index = self._next_pending(run)
                if index is None:
                    run.current_step = None
                    run.status = WorkflowStatus.SUCCEEDED
                    run.updated_at = _utc_now()
                    return self._snapshot(run)
                mutable = run.steps[index]
                mutable.status = WorkflowStepStatus.RUNNING
                mutable.pending_confirmation = None
                run.current_step = index
                run.status = WorkflowStatus.RUNNING
                run.updated_at = _utc_now()
                invocation = run.plan.steps[index].invocation

            outcome = await self._skills.submit(invocation)

            with self._lock:
                run = self._require_run(workflow_id)
                mutable = run.steps[index]
                mutable.receipt = outcome.receipt
                run.updated_at = _utc_now()
                if outcome.pending_confirmation is not None:
                    confirmation = outcome.pending_confirmation
                    mutable.status = WorkflowStepStatus.CONFIRMATION_REQUIRED
                    mutable.pending_confirmation = confirmation
                    run.status = WorkflowStatus.CONFIRMATION_REQUIRED
                    self._pending[confirmation.confirmation_id] = (workflow_id, index)
                    return self._snapshot(run)

                mutable.status = self._step_status(outcome.receipt.status)
                if mutable.status is WorkflowStepStatus.SUCCEEDED:
                    continue
                run.status = self._workflow_status(mutable.status)
                self._skip_remaining(run, index + 1)
                return self._snapshot(run)

    def _validate_plan(self, plan: WorkflowPlan) -> None:
        if not isinstance(plan, WorkflowPlan):
            raise TypeError("plan must be a WorkflowPlan.")
        unknown = [
            step.invocation.skill_id
            for step in plan.steps
            if step.invocation.skill_id not in self._manifests
        ]
        if unknown:
            raise ValueError(f"Workflow contains unknown skills: {', '.join(sorted(set(unknown)))}")

    def _snapshot(self, run: _WorkflowRun) -> WorkflowSnapshot:
        views = tuple(
            self._step_view(plan_step, mutable)
            for plan_step, mutable in zip(run.plan.steps, run.steps, strict=True)
        )
        return WorkflowSnapshot(
            _WORKFLOW_SCHEMA,
            run.plan.workflow_id,
            run.plan.name,
            run.plan.digest,
            run.plan.actor_id,
            run.status,
            run.current_step,
            run.created_at,
            run.updated_at,
            views,
        )

    def _step_view(self, step: WorkflowStep, mutable: _MutableStep) -> WorkflowStepView:
        manifest = self._manifests[step.invocation.skill_id]
        return WorkflowStepView(
            step.step_id,
            step.label,
            step.invocation.skill_id,
            manifest.version,
            manifest.risk_level.value,
            tuple(sorted(permission.value for permission in manifest.permissions)),
            mutable.status,
            tuple(sorted(step.invocation.arguments)),
            _sha256(canonical_json(step.invocation.arguments)),
            mutable.receipt,
            mutable.pending_confirmation,
        )

    def _consume_pending(self, confirmation_id: str) -> tuple[str, int]:
        if not isinstance(confirmation_id, str) or not confirmation_id:
            raise UnknownConfirmationError("Confirmation handle is invalid.")
        with self._lock:
            value = self._pending.pop(confirmation_id, None)
        if value is None:
            raise UnknownConfirmationError(
                "Confirmation handle is invalid, expired, or already consumed."
            )
        return value

    def _require_run(self, workflow_id: str) -> _WorkflowRun:
        run = self._runs.get(workflow_id)
        if run is None:
            raise UnknownWorkflowError("Unknown workflow_id.")
        return run

    @staticmethod
    def _next_pending(run: _WorkflowRun) -> int | None:
        for index, step in enumerate(run.steps):
            if step.status is WorkflowStepStatus.PENDING:
                return index
        return None

    @staticmethod
    def _skip_remaining(run: _WorkflowRun, start: int) -> None:
        for step in run.steps[start:]:
            if step.status is WorkflowStepStatus.PENDING:
                step.status = WorkflowStepStatus.SKIPPED
        run.current_step = None

    @staticmethod
    def _step_status(status: str) -> WorkflowStepStatus:
        return {
            ExecutionStatus.SUCCEEDED.value: WorkflowStepStatus.SUCCEEDED,
            ExecutionStatus.BLOCKED.value: WorkflowStepStatus.BLOCKED,
            ExecutionStatus.CANCELLED.value: WorkflowStepStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT.value: WorkflowStepStatus.TIMED_OUT,
            ExecutionStatus.FAILED.value: WorkflowStepStatus.FAILED,
        }.get(status, WorkflowStepStatus.FAILED)

    @staticmethod
    def _workflow_status(status: WorkflowStepStatus) -> WorkflowStatus:
        return {
            WorkflowStepStatus.BLOCKED: WorkflowStatus.BLOCKED,
            WorkflowStepStatus.CANCELLED: WorkflowStatus.CANCELLED,
            WorkflowStepStatus.TIMED_OUT: WorkflowStatus.TIMED_OUT,
            WorkflowStepStatus.FAILED: WorkflowStatus.FAILED,
        }.get(status, WorkflowStatus.FAILED)


__all__ = [
    "UnknownWorkflowError",
    "VerifiedWorkflowSession",
    "WorkflowPlan",
    "WorkflowSnapshot",
    "WorkflowStateError",
    "WorkflowStatus",
    "WorkflowStep",
    "WorkflowStepStatus",
    "WorkflowStepView",
]
