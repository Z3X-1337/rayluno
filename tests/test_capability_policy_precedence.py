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


def _now() -> datetime:
    return datetime(2026, 7, 21, 1, 0, tzinfo=UTC)


def _manifest(
    *,
    skill_id: str = "application.notepad.write",
    permission: str = "application.notepad.write",
    risk: SkillRisk = SkillRisk.MEDIUM,
) -> SkillManifest:
    return SkillManifest(
        skill_id,
        ActionKind.OPEN_APP,
        permission,
        risk,
        ConfirmationPolicy.ALWAYS,
    )


def test_exact_skill_rule_wins_over_broad_permission_rule() -> None:
    manifest = _manifest()
    engine = CapabilityPolicyEngine(
        profile=PermissionProfile.SAFE,
        rules=(
            CapabilityRule(
                permission_prefix="application",
                decision=PermissionDecision.ALLOW,
            ),
            CapabilityRule(
                skill_id=manifest.skill_id,
                decision=PermissionDecision.DENY,
            ),
        ),
    )

    result = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())

    assert result.decision is PermissionDecision.DENY
    assert result.matched_rule is not None
    assert result.matched_rule.skill_id == manifest.skill_id


def test_longest_permission_prefix_wins() -> None:
    manifest = _manifest()
    engine = CapabilityPolicyEngine(
        profile=PermissionProfile.SAFE,
        rules=(
            CapabilityRule(
                permission_prefix="application",
                decision=PermissionDecision.DENY,
            ),
            CapabilityRule(
                permission_prefix="application.notepad",
                decision=PermissionDecision.ALLOW,
            ),
        ),
    )

    result = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())

    assert result.decision is PermissionDecision.ALLOW
    assert result.matched_rule is not None
    assert result.matched_rule.permission_prefix == "application.notepad"


def test_same_specificity_prefers_more_restrictive_decision() -> None:
    manifest = _manifest()
    engine = CapabilityPolicyEngine(
        profile=PermissionProfile.SAFE,
        rules=(
            CapabilityRule(
                permission_prefix="application.notepad",
                decision=PermissionDecision.ALLOW,
            ),
            CapabilityRule(
                permission_prefix="application.notepad",
                decision=PermissionDecision.CONFIRM,
            ),
        ),
    )

    result = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())

    assert result.decision is PermissionDecision.CONFIRM


def test_expired_rule_is_ignored() -> None:
    manifest = _manifest(risk=SkillRisk.LOW)
    engine = CapabilityPolicyEngine(
        profile=PermissionProfile.SAFE,
        rules=(
            CapabilityRule(
                skill_id=manifest.skill_id,
                decision=PermissionDecision.DENY,
                expires_at=_now() - timedelta(seconds=1),
            ),
        ),
    )

    result = engine.evaluate(manifest, PlanSource.DETERMINISTIC, now=_now())

    assert result.decision is PermissionDecision.ALLOW
    assert result.matched_rule is None


def test_elevation_requires_matching_registered_skill() -> None:
    now = _now()
    session = ElevatedSession(
        session_id="session-1",
        permission_prefixes=frozenset({"system.settings"}),
        allowed_skill_ids=frozenset({"system.display.change"}),
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    engine = CapabilityPolicyEngine(profile=PermissionProfile.BALANCED)

    permitted = engine.evaluate(
        _manifest(
            skill_id="system.display.change",
            permission="system.settings.display",
            risk=SkillRisk.CRITICAL,
        ),
        PlanSource.DETERMINISTIC,
        elevated_session=session,
        now=now + timedelta(minutes=1),
    )
    other_skill = engine.evaluate(
        _manifest(
            skill_id="system.sound.change",
            permission="system.settings.sound",
            risk=SkillRisk.CRITICAL,
        ),
        PlanSource.DETERMINISTIC,
        elevated_session=session,
        now=now + timedelta(minutes=1),
    )

    assert permitted.decision is PermissionDecision.CONFIRM
    assert permitted.elevation_satisfied is True
    assert other_skill.decision is PermissionDecision.ELEVATE


def test_empty_or_malformed_scopes_are_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        CapabilityRule(
            decision=PermissionDecision.DENY,
            skill_id="   ",
        )
    with pytest.raises(ValueError, match="without empty segments"):
        CapabilityRule(
            decision=PermissionDecision.DENY,
            permission_prefix="system..settings",
        )


def test_elevation_requires_permission_and_skill_scope() -> None:
    now = _now()

    with pytest.raises(ValueError, match="permission scope"):
        ElevatedSession(
            session_id="missing-permission",
            permission_prefixes=frozenset(),
            allowed_skill_ids=frozenset({"system.settings.change"}),
            created_at=now,
            expires_at=now + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="skill ID"):
        ElevatedSession(
            session_id="missing-skill",
            permission_prefixes=frozenset({"system.settings"}),
            allowed_skill_ids=frozenset(),
            created_at=now,
            expires_at=now + timedelta(minutes=1),
        )
