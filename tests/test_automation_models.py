from __future__ import annotations

from types import MappingProxyType

import pytest

from future_assistant.automation import (
    AutomationResult,
    ExecutionStatus,
    Permission,
    ResultCode,
    RiskLevel,
    SkillInvocation,
    SkillManifest,
)
from future_assistant.automation.models import canonical_json


def _manifest(**overrides: object) -> SkillManifest:
    values: dict[str, object] = {
        "skill_id": "test.skill",
        "executor_id": "test.executor",
        "version": "1.2.3",
        "name": "Test skill",
        "description": "A test-only skill.",
        "permissions": {Permission.BROWSER_OPEN_URL},
        "risk_level": RiskLevel.MEDIUM,
        "timeout_seconds": 5,
    }
    values.update(overrides)
    return SkillManifest(**values)  # type: ignore[arg-type]


def test_manifest_is_normalized_and_exposes_risk_confirmation_policy() -> None:
    manifest = _manifest()

    assert manifest.permissions == frozenset({Permission.BROWSER_OPEN_URL})
    assert manifest.timeout_seconds == 5.0
    assert not manifest.requires_confirmation()
    assert manifest.requires_confirmation(RiskLevel.MEDIUM)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("skill_id", "Bad Skill", ValueError),
        ("executor_id", "x", ValueError),
        ("version", "v1", ValueError),
        ("name", "", ValueError),
        ("permissions", set(), ValueError),
        ("permissions", {"browser.open_url"}, ValueError),
        ("risk_level", "high", TypeError),
        ("timeout_seconds", 0, ValueError),
        ("timeout_seconds", 61, ValueError),
        ("timeout_seconds", True, ValueError),
    ],
)
def test_manifest_rejects_ambiguous_or_unbounded_fields(
    field: str, value: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        _manifest(**{field: value})


def test_invocation_deep_copies_and_freezes_json_arguments() -> None:
    original = {"query": "safe", "options": {"languages": ["ar", "en"]}}

    invocation = SkillInvocation("browser.search", original, request_id="request-001")
    original["query"] = "changed"
    original["options"]["languages"].append("fr")  # type: ignore[index,union-attr]

    assert invocation.arguments["query"] == "safe"
    options = invocation.arguments["options"]
    assert isinstance(options, MappingProxyType)
    assert options["languages"] == ("ar", "en")
    with pytest.raises(TypeError):
        invocation.arguments["query"] = "mutated"  # type: ignore[index]


@pytest.mark.parametrize(
    "arguments",
    [
        {"value": object()},
        {"value": {1: "not-a-string-key"}},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": 2**63},
        {"value": "\ud800"},
        {"value": {"not", "json"}},
    ],
)
def test_invocation_rejects_non_json_or_non_finite_arguments(
    arguments: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        SkillInvocation("browser.search", arguments)


def test_canonical_json_is_order_independent_and_preserves_unicode() -> None:
    first = canonical_json({"query": "جارفيس", "nested": {"b": 2, "a": 1}})
    second = canonical_json({"nested": {"a": 1, "b": 2}, "query": "جارفيس"})

    assert first == second
    assert "جارفيس" in first


def test_invocation_bounds_json_nesting_depth() -> None:
    nested: object = "value"
    for _ in range(22):
        nested = {"next": nested}

    with pytest.raises(ValueError, match="nesting depth"):
        SkillInvocation("browser.search", {"nested": nested})


def test_result_data_is_also_deeply_immutable() -> None:
    invocation = SkillInvocation("browser.search", {"query": "test"})
    result = AutomationResult(
        invocation,
        ExecutionStatus.SUCCEEDED,
        ResultCode.OK,
        data={"items": [1, 2]},
    )

    assert result.data["items"] == (1, 2)
    with pytest.raises(TypeError):
        result.data["other"] = True  # type: ignore[index]
