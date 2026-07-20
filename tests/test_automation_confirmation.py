from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from future_assistant.automation import (
    ConfirmationAuthority,
    ConfirmationValidation,
    SkillInvocation,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _invocation(**overrides: object) -> SkillInvocation:
    values: dict[str, object] = {
        "skill_id": "app.launch",
        "arguments": {"app_id": "calculator"},
        "actor_id": "user-1",
        "request_id": "request-1",
    }
    values.update(overrides)
    return SkillInvocation(**values)  # type: ignore[arg-type]


def test_confirmation_is_exactly_bound_and_single_use() -> None:
    authority = ConfirmationAuthority()
    invocation = _invocation()
    grant = authority.issue(invocation)

    assert grant.token not in repr(grant)
    assert authority.consume(grant.token, invocation) is ConfirmationValidation.ACCEPTED
    assert authority.consume(grant.token, invocation) is ConfirmationValidation.INVALID
    assert authority.pending_count == 0


def test_unknown_token_does_not_invalidate_a_real_grant() -> None:
    authority = ConfirmationAuthority()
    invocation = _invocation()
    grant = authority.issue(invocation)

    assert authority.consume("x" * 43, invocation) is ConfirmationValidation.INVALID
    assert authority.consume(grant.token, invocation) is ConfirmationValidation.ACCEPTED


def test_concurrent_confirmation_consumers_cannot_both_succeed() -> None:
    authority = ConfirmationAuthority()
    invocation = _invocation()
    grant = authority.issue(invocation)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: authority.consume(grant.token, invocation), range(2)))

    assert results.count(ConfirmationValidation.ACCEPTED) == 1
    assert results.count(ConfirmationValidation.INVALID) == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"arguments": {"app_id": "notepad"}},
        {"actor_id": "user-2"},
        {"request_id": "request-2"},
    ],
)
def test_confirmation_cannot_be_moved_to_another_invocation(changed: dict[str, object]) -> None:
    authority = ConfirmationAuthority()
    original = _invocation()
    grant = authority.issue(original)

    assert authority.consume(grant.token, _invocation(**changed)) is ConfirmationValidation.MISMATCH
    assert authority.consume(grant.token, original) is ConfirmationValidation.INVALID


def test_expired_confirmation_is_rejected_and_consumed() -> None:
    clock = FakeClock()
    authority = ConfirmationAuthority(
        default_ttl_seconds=2,
        max_ttl_seconds=10,
        clock=clock,
    )
    invocation = _invocation()
    grant = authority.issue(invocation)

    clock.advance(2)

    assert authority.consume(grant.token, invocation) is ConfirmationValidation.EXPIRED
    assert authority.consume(grant.token, invocation) is ConfirmationValidation.INVALID


def test_purge_removes_expired_grants_only() -> None:
    clock = FakeClock()
    authority = ConfirmationAuthority(
        default_ttl_seconds=5,
        max_ttl_seconds=20,
        clock=clock,
    )
    authority.issue(_invocation(request_id="short"), ttl_seconds=2)
    authority.issue(_invocation(request_id="long"), ttl_seconds=10)

    clock.advance(3)

    assert authority.purge_expired() == 1
    assert authority.pending_count == 1


@pytest.mark.parametrize("ttl", [0, 11, True, float("nan"), float("inf")])
def test_authority_enforces_a_short_bounded_ttl(ttl: object) -> None:
    authority = ConfirmationAuthority(default_ttl_seconds=5, max_ttl_seconds=10)

    with pytest.raises(ValueError):
        authority.issue(_invocation(), ttl_seconds=ttl)  # type: ignore[arg-type]


def test_authority_rejects_naive_clock() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ConfirmationAuthority(clock=lambda: datetime(2026, 7, 11))


@pytest.mark.parametrize(
    "options",
    [
        {"default_ttl_seconds": True},
        {"max_ttl_seconds": True},
        {"max_ttl_seconds": float("inf")},
        {"default_ttl_seconds": float("nan")},
    ],
)
def test_authority_rejects_non_numeric_or_non_finite_configuration(
    options: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        ConfirmationAuthority(**options)  # type: ignore[arg-type]
