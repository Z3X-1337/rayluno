"""Immutable domain objects for capability-scoped automation skills."""

from __future__ import annotations

import json
import math
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_MAX_JSON_DEPTH = 20
_MAX_JSON_CONTAINER_ITEMS = 1_000
_MAX_JSON_STRING_LENGTH = 32_768
_MAX_JSON_KEY_LENGTH = 256
_MAX_JSON_INTEGER = 2**63 - 1


class Permission(StrEnum):
    """Small, explicit capabilities that an executor may exercise."""

    BROWSER_OPEN_URL = "browser.open_url"
    APP_LAUNCH = "app.launch"


class RiskLevel(StrEnum):
    """Human-review risk classification attached to every skill manifest."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }[self]

    def at_least(self, threshold: RiskLevel) -> bool:
        return self.rank >= threshold.rank


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class ResultCode(StrEnum):
    OK = "ok"
    UNKNOWN_SKILL = "unknown_skill"
    PERMISSION_DENIED = "permission_denied"
    INVALID_ARGUMENTS = "invalid_arguments"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CONFIRMATION_INVALID = "confirmation_invalid"
    CONFIRMATION_EXPIRED = "confirmation_expired"
    CONFIRMATION_MISMATCH = "confirmation_mismatch"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    EXECUTOR_FAILED = "executor_failed"


def validate_identifier(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or not 3 <= len(value) <= 100 or not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a lowercase capability identifier of 3-100 characters."
        )


def _validate_label(value: str, *, field_name: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field_name} must contain 1-{maximum} characters.")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters.")


def _validate_json_text(value: str, *, path: str, maximum: int) -> None:
    if len(value) > maximum:
        raise ValueError(f"{path} exceeds the maximum string length of {maximum}.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{path} contains invalid Unicode.") from exc


def _freeze_json(value: object, *, path: str, depth: int = 0) -> object:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError(f"{path} exceeds the maximum JSON nesting depth.")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        _validate_json_text(value, path=path, maximum=_MAX_JSON_STRING_LENGTH)
        return value
    if isinstance(value, int):
        if abs(value) > _MAX_JSON_INTEGER:
            raise ValueError(f"{path} exceeds the supported 64-bit integer range.")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers.")
        return value
    if isinstance(value, Mapping):
        if len(value) > _MAX_JSON_CONTAINER_ITEMS:
            raise ValueError(f"{path} contains too many object members.")
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} must use string object keys.")
            _validate_json_text(key, path=f"{path} key", maximum=_MAX_JSON_KEY_LENGTH)
            frozen[key] = _freeze_json(item, path=f"{path}.{key}", depth=depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_JSON_CONTAINER_ITEMS:
            raise ValueError(f"{path} contains too many array items.")
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        )
    raise TypeError(f"{path} contains a non-JSON value of type {type(value).__name__}.")


def freeze_json_object(value: Mapping[str, object]) -> Mapping[str, object]:
    """Deep-copy and freeze a JSON-compatible mapping."""

    if not isinstance(value, Mapping):
        raise TypeError("A JSON object mapping is required.")
    frozen = _freeze_json(value, path="$")
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded by the check above
        raise TypeError("A JSON object mapping is required.")
    return frozen


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def canonical_json(value: Mapping[str, object]) -> str:
    """Return a deterministic representation suitable for confirmation binding."""

    frozen = freeze_json_object(value)
    return json.dumps(
        _thaw_json(frozen),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class SkillManifest:
    skill_id: str
    executor_id: str
    version: str
    name: str
    description: str
    permissions: frozenset[Permission]
    risk_level: RiskLevel
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        validate_identifier(self.skill_id, field_name="skill_id")
        validate_identifier(self.executor_id, field_name="executor_id")
        if not isinstance(self.version, str) or not _SEMVER.fullmatch(self.version):
            raise ValueError("version must be a semantic version such as 1.0.0.")
        _validate_label(self.name, field_name="name", maximum=80)
        _validate_label(self.description, field_name="description", maximum=500)
        try:
            permissions = frozenset(self.permissions)
        except TypeError as exc:
            raise TypeError("permissions must be an iterable of Permission values.") from exc
        if not permissions or not all(isinstance(item, Permission) for item in permissions):
            raise ValueError("permissions must contain at least one Permission value.")
        if not isinstance(self.risk_level, RiskLevel):
            raise TypeError("risk_level must be a RiskLevel value.")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or not 0.01 <= self.timeout_seconds <= 60.0
        ):
            raise ValueError("timeout_seconds must be between 0.01 and 60 seconds.")
        object.__setattr__(self, "permissions", permissions)
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))

    def requires_confirmation(self, threshold: RiskLevel = RiskLevel.HIGH) -> bool:
        return self.risk_level.at_least(threshold)


@dataclass(frozen=True, slots=True)
class SkillInvocation:
    skill_id: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    actor_id: str = "local-user"
    request_id: str = field(default_factory=lambda: secrets.token_hex(16))

    def __post_init__(self) -> None:
        validate_identifier(self.skill_id, field_name="skill_id")
        _validate_label(self.actor_id, field_name="actor_id", maximum=128)
        _validate_label(self.request_id, field_name="request_id", maximum=128)
        object.__setattr__(self, "arguments", freeze_json_object(self.arguments))

    def confirmation_payload(self) -> Mapping[str, object]:
        return {
            "skill_id": self.skill_id,
            "arguments": self.arguments,
            "actor_id": self.actor_id,
            "request_id": self.request_id,
        }


@dataclass(frozen=True, slots=True)
class AutomationResult:
    invocation: SkillInvocation
    status: ExecutionStatus
    code: ResultCode
    detail: str = ""
    data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExecutionStatus):
            raise TypeError("status must be an ExecutionStatus value.")
        if not isinstance(self.code, ResultCode):
            raise TypeError("code must be a ResultCode value.")
        if not isinstance(self.detail, str) or len(self.detail) > 300:
            raise ValueError("detail must be a string of at most 300 characters.")
        object.__setattr__(self, "data", freeze_json_object(self.data))
