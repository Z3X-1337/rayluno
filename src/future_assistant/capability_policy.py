"""User-owned capability policy decisions for registered Rayluno skills."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .domain import PlanSource
from .verified_skills import SkillManifest, SkillRisk


class PermissionDecision(StrEnum):
    """The only four outcomes a capability policy may produce."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    ELEVATE = "elevate"
    DENY = "deny"


class PermissionProfile(StrEnum):
    """Built-in user-selectable baselines."""

    SAFE = "safe"
    BALANCED = "balanced"
    POWER_USER = "power_user"


_DECISION_RESTRICTIVENESS = {
    PermissionDecision.ALLOW: 0,
    PermissionDecision.CONFIRM: 1,
    PermissionDecision.ELEVATE: 2,
    PermissionDecision.DENY: 3,
}


def _normalized_scope(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} cannot be empty.")
    if cleaned.startswith(".") or cleaned.endswith(".") or ".." in cleaned:
        raise ValueError(f"{label} must be a dotted identifier without empty segments.")
    return cleaned


@dataclass(frozen=True, slots=True)
class CapabilityRule:
    """A user-owned override for one registered skill or permission prefix."""

    decision: PermissionDecision
    skill_id: str | None = None
    permission_prefix: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if (self.skill_id is None) == (self.permission_prefix is None):
            raise ValueError("Exactly one of skill_id or permission_prefix is required.")
        if self.skill_id is not None:
            object.__setattr__(
                self,
                "skill_id",
                _normalized_scope(self.skill_id, label="skill_id"),
            )
        if self.permission_prefix is not None:
            object.__setattr__(
                self,
                "permission_prefix",
                _normalized_scope(self.permission_prefix, label="permission_prefix"),
            )
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware.")

    def matches(self, manifest: SkillManifest, now: datetime) -> bool:
        if self.expires_at is not None and now >= self.expires_at:
            return False
        if self.skill_id is not None:
            return manifest.skill_id == self.skill_id
        assert self.permission_prefix is not None
        return manifest.permission == self.permission_prefix or manifest.permission.startswith(
            f"{self.permission_prefix}."
        )

    def precedence(self) -> tuple[int, int, int]:
        """Prefer exact skills, then longest prefix, then the safer decision."""

        if self.skill_id is not None:
            specificity = (2, len(self.skill_id))
        else:
            assert self.permission_prefix is not None
            specificity = (1, len(self.permission_prefix))
        return (*specificity, _DECISION_RESTRICTIVENESS[self.decision])


@dataclass(frozen=True, slots=True)
class ElevatedSession:
    """Short-lived user-approved elevation scoped to permissions and skill IDs."""

    session_id: str
    permission_prefixes: frozenset[str]
    allowed_skill_ids: frozenset[str]
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        session_id = self.session_id.strip()
        if not session_id:
            raise ValueError("session_id is required.")
        if not self.permission_prefixes:
            raise ValueError("At least one permission scope is required.")
        if not self.allowed_skill_ids:
            raise ValueError("At least one allowed skill ID is required.")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Elevation timestamps must be timezone-aware.")
        if self.expires_at <= self.created_at:
            raise ValueError("Elevation must expire after it starts.")
        if self.expires_at - self.created_at > timedelta(minutes=15):
            raise ValueError("Elevation sessions may not exceed 15 minutes.")

        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(
            self,
            "permission_prefixes",
            frozenset(
                _normalized_scope(prefix, label="permission_prefix")
                for prefix in self.permission_prefixes
            ),
        )
        object.__setattr__(
            self,
            "allowed_skill_ids",
            frozenset(
                _normalized_scope(skill_id, label="skill_id")
                for skill_id in self.allowed_skill_ids
            ),
        )

    def allows(self, manifest: SkillManifest, now: datetime) -> bool:
        if now >= self.expires_at or manifest.skill_id not in self.allowed_skill_ids:
            return False
        return any(
            manifest.permission == prefix or manifest.permission.startswith(f"{prefix}.")
            for prefix in self.permission_prefixes
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: PermissionDecision
    reason: str
    matched_rule: CapabilityRule | None = None
    elevation_satisfied: bool = False


class CapabilityPolicyEngine:
    """Resolve user policy without granting unregistered or arbitrary authority."""

    def __init__(
        self,
        *,
        profile: PermissionProfile = PermissionProfile.SAFE,
        rules: tuple[CapabilityRule, ...] = (),
    ) -> None:
        self.profile = profile
        self.rules = rules

    def evaluate(
        self,
        manifest: SkillManifest,
        source: PlanSource,
        *,
        elevated_session: ElevatedSession | None = None,
        now: datetime | None = None,
    ) -> PolicyDecision:
        current = self._aware_utc(now or datetime.now(UTC))
        rule = self._matching_rule(manifest, current)
        if rule is not None:
            return self._apply_rule(rule, manifest, elevated_session, current)
        return self._profile_decision(manifest, source, elevated_session, current)

    def _matching_rule(
        self,
        manifest: SkillManifest,
        now: datetime,
    ) -> CapabilityRule | None:
        matching = (rule for rule in self.rules if rule.matches(manifest, now))
        return max(matching, key=CapabilityRule.precedence, default=None)

    def _apply_rule(
        self,
        rule: CapabilityRule,
        manifest: SkillManifest,
        elevated_session: ElevatedSession | None,
        now: datetime,
    ) -> PolicyDecision:
        if rule.decision is PermissionDecision.DENY:
            return PolicyDecision(PermissionDecision.DENY, "user_rule", rule)
        if rule.decision is PermissionDecision.CONFIRM:
            return PolicyDecision(PermissionDecision.CONFIRM, "user_rule", rule)

        elevated = self._is_elevated(manifest, elevated_session, now)
        if manifest.risk is SkillRisk.CRITICAL:
            if elevated:
                return PolicyDecision(
                    PermissionDecision.CONFIRM,
                    "critical_elevation_satisfied_confirmation_required",
                    rule,
                    elevation_satisfied=True,
                )
            return PolicyDecision(
                PermissionDecision.ELEVATE,
                "critical_user_rule_requires_elevation",
                rule,
            )

        if rule.decision is PermissionDecision.ELEVATE:
            if elevated:
                decision = (
                    PermissionDecision.CONFIRM
                    if manifest.risk is SkillRisk.HIGH
                    else PermissionDecision.ALLOW
                )
                return PolicyDecision(
                    decision,
                    "user_rule_satisfied_by_scoped_elevation",
                    rule,
                    elevation_satisfied=True,
                )
            return PolicyDecision(PermissionDecision.ELEVATE, "user_rule", rule)

        return PolicyDecision(PermissionDecision.ALLOW, "user_rule", rule)

    def _profile_decision(
        self,
        manifest: SkillManifest,
        source: PlanSource,
        elevated_session: ElevatedSession | None,
        now: datetime,
    ) -> PolicyDecision:
        if manifest.risk is SkillRisk.CRITICAL:
            elevated = self._is_elevated(manifest, elevated_session, now)
            if elevated:
                return PolicyDecision(
                    PermissionDecision.CONFIRM,
                    "critical_elevation_satisfied_confirmation_required",
                    elevation_satisfied=True,
                )
            if self.profile is PermissionProfile.SAFE:
                return PolicyDecision(PermissionDecision.DENY, "safe_profile_blocks_critical")
            return PolicyDecision(PermissionDecision.ELEVATE, "critical_skill_requires_elevation")

        if self.profile is PermissionProfile.SAFE:
            if manifest.risk is SkillRisk.LOW and source is PlanSource.DETERMINISTIC:
                return PolicyDecision(PermissionDecision.ALLOW, "safe_low_deterministic")
            return PolicyDecision(PermissionDecision.CONFIRM, "safe_profile_confirmation")

        if self.profile is PermissionProfile.BALANCED:
            if manifest.risk is SkillRisk.LOW:
                return PolicyDecision(PermissionDecision.ALLOW, "balanced_low_risk")
            if manifest.risk is SkillRisk.MEDIUM and source is PlanSource.DETERMINISTIC:
                return PolicyDecision(PermissionDecision.ALLOW, "balanced_medium_deterministic")
            return PolicyDecision(PermissionDecision.CONFIRM, "balanced_profile_confirmation")

        if manifest.risk in {SkillRisk.LOW, SkillRisk.MEDIUM}:
            return PolicyDecision(PermissionDecision.ALLOW, "power_user_low_or_medium")
        return PolicyDecision(PermissionDecision.CONFIRM, "power_user_high_risk_confirmation")

    @staticmethod
    def _is_elevated(
        manifest: SkillManifest,
        elevated_session: ElevatedSession | None,
        now: datetime,
    ) -> bool:
        return bool(elevated_session and elevated_session.allows(manifest, now))

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Policy evaluation time must be timezone-aware.")
        return value.astimezone(UTC)


__all__ = [
    "CapabilityPolicyEngine",
    "CapabilityRule",
    "ElevatedSession",
    "PermissionDecision",
    "PermissionProfile",
    "PolicyDecision",
]
