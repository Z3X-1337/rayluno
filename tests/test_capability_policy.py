from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from future_assistant.capability_policy import (
    CapabilityPolicyEngine,
    CapabilityRule,
    ElevatedSession,
    PermissionDecision,
    PermissionProfile,
)
from future_assistant.domain import ActionKind, PlanSource
from future_assistant.verified_skills import (
    ConfirmationPolicy,
    SkillManifest,
    SkillRisk,
)


def _manifest(
    *,
    skill_id: str = "test.skill",
    permission: str = "system.test.write",
    risk: SkillRisk = SkillRisk.MEDIUM,
) -> SkillManifest:
    return SkillManifest(
        skill_id,
        ActionKind.OPEN_APP,
        permission,
        risk,
        ConfirmationPolicy.ALWAYS,
    )


def _now() -> datetime:
    return datetime(2026, 7, 21, 0, 0, tzinfo=UTC)


def test_safe_profile_allows_only_low_deterministic_without_confirmation() -> None:
    engine = CapabilityPolicyEngine(profile=PermissionProfile.SAFE)

    allowed = engine.evaluate(
        _manifest(risk=SkillRisk.LOW),
        PlanSource.DETERMINISTIC,
        now=_now(),
    )
    proposed = engine.evaluate(
        _manifest(risk=SkillRisk.LOW),
        PlanSource.OLLAMA,
        now=_now(),
    )
    critical = engine.evaluate(
        _manifest(risk=SkillRisk.CRITICAL),
        PlanSource.DETERMINISTIC,
        now=_now(),
    )

    assert allowed.decision is PermissionDecision.ALLOW
    assert proposed.decision is PermissionDecision.CONFIRM
    assert critical.decision is PermissionDecision.DENY


def test_balanced_profile_distinguishes_deterministic_and_model_medium_risk() -> None:
    engine = CapabilityPolicyEngine(profile=PermissionProfile.BALANCED)
    manifest = _manifest(risk=SkillRisk.MEDIUM)

    deterministic = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())
    proposed = engine.evaluate(manifest, PlanSource.OLLAMA, now=_now())

    assert deterministic.decision is PermissionDecision.ALLOW
    assert proposed.decision is PermissionDecision.CONFIRM


def test_power_user_still_requires_confirmation_for_high_risk() -> None:
    engine = CapabilityPolicyEngine(profile=PermissionProfile.POWER_USER)

    result = engine.evaluate(
        _manifest(risk=SkillRisk.HIGH),
        PlanSource.DETERMINISTIC,
        now=_now(),
    )

    assert result.decision is PermissionDecision.CONFIRM


def test_user_rule_can_deny_or_allow_registered_noncritical_skill() -> None:
    manifest = _manifest(skill_id="application.launch", risk=SkillRisk.MEDIUM)
    deny = CapabilityPolicyEngine(
        profile=PermissionProfile.POWER_USER,
        rules=(
            CapabilityRule(
                skill_id="application.launch",
                decision=PermissionDecision.DENY,
            ),
        ),
    )
    allow = CapabilityPolicyEngine(
        profile=PermissionProfile.SAFE,
        rules=(
            CapabilityRule(
                skill_id="application.launch",
                decision=PermissionDecision.ALLOW,
            ),
        ),
    )

    denied = deny.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())
    allowed = allow.evaluate(manifest, PlanSource.OLLAMA, now=_now())

    assert denied.decision is PermissionDecision.DENY
    assert allowed.decision is PermissionDecision.ALLOW


def test_critical_allow_override_is_downgraded_to_elevation() -> None:
    manifest = _manifest(risk=SkillRisk.CRITICAL)
    engine = CapabilityPolicyEngine(
        profile=PermissionProfile.POWER_USER,
        rules=(
            CapabilityRule(
                skill_id=manifest.skill_id,
                decision=PermissionDecision.ALLOW,
            ),
        ),
    )

    result = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())

    assert result.decision is PermissionDecision.ELEVATE


def test_scoped_elevation_requires_confirmation_for_critical_skill() -> None:
    now = _now()
    session = ElevatedSession(
        session_id="elev-1",
        permission_prefixes=frozenset({"system.settings"}),
        allowed_skill_ids=frozenset({"test.skill"}),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    engine = CapabilityPolicyEngine(profile=PermissionProfile.BALANCED)

    matching = engine.evaluate(
        _manifest(permission="system.settings.display", risk=SkillRisk.CRITICAL),
        PlanSource.DETERMINISTIC,
        elevated_session=session,
        now=now + timedelta(minutes=1),
    )
    outside_scope = engine.evaluate(
        _manifest(permission="system.accounts.write", risk=SkillRisk.CRITICAL),
        PlanSource.DETERMINISTIC,
        elevated_session=session,
        now=now + timedelta(minutes=1),
    )
    expired = engine.evaluate(
        _manifest(permission="system.settings.display", risk=SkillRisk.CRITICAL),
        PlanSource.DETERMINISTIC,
        elevated_session=session,
        now=now + timedelta(minutes=6),
    )

    assert matching.decision is PermissionDecision.CONFIRM
    assert matching.elevation_satisfied is True
    assert outside_scope.decision is PermissionDecision.ELEVATE
    assert expired.decision is PermissionDecision.ELEVATE


def test_elevation_cannot_last_longer_than_fifteen_minutes() -> None:
    now = _now()

    with pytest.raises(ValueError, match="15 minutes"):
        ElevatedSession(
            session_id="too-long",
            permission_prefixes=frozenset({"system"}),
            allowed_skill_ids=frozenset({"test.skill"}),
            created_at=now,
            expires_at=now + timedelta(minutes=16),
        )


def test_rule_requires_exactly_one_selector() -> None:
    with pytest.raises(ValueError, match="Exactly one"):
        CapabilityRule(decision=PermissionDecision.DENY)
    with pytest.raises(ValueError, match="Exactly one"):
        CapabilityRule(
            decision=PermissionDecision.DENY,
            skill_id="a",
            permission_prefix="system",
        )
