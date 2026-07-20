"""Pure domain types shared by planners, policy, and execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ActionKind(StrEnum):
    OPEN_URL = "open_url"
    OPEN_APP = "open_app"
    REPORT_TIME = "report_time"
    CONTROL_VOLUME = "control_volume"


class VolumeOperation(StrEnum):
    UP = "up"
    DOWN = "down"
    TOGGLE_MUTE = "toggle_mute"


class PlanSource(StrEnum):
    DETERMINISTIC = "deterministic"
    OLLAMA = "ollama"
    DEMO = "demo"


class RuntimeStatus(StrEnum):
    SLEEPING = "sleeping"
    AWAKE = "awake"
    UNHANDLED = "unhandled"
    CONFIRMATION_REQUIRED = "confirmation_required"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Action:
    kind: ActionKind
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class Plan:
    actions: tuple[Action, ...] = ()
    reply: str | None = None
    source: PlanSource = PlanSource.DETERMINISTIC


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    action: Action
    ok: bool
    message: str
    blocked: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    status: RuntimeStatus
    message: str = ""
    plan: Plan | None = None
    executions: tuple[ExecutionResult, ...] = ()
