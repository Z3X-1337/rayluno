"""Short-lived, one-time confirmation grants bound to exact invocations."""

from __future__ import annotations

import hashlib
import math
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .models import SkillInvocation, canonical_json

_ABSOLUTE_MAX_TTL_SECONDS = 300.0


class ConfirmationValidation(StrEnum):
    ACCEPTED = "accepted"
    INVALID = "invalid"
    EXPIRED = "expired"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ConfirmationGrant:
    token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class _PendingConfirmation:
    invocation_fingerprint: str
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ConfirmationAuthority:
    """In-memory authority that stores only token hashes and consumes grants once."""

    def __init__(
        self,
        *,
        default_ttl_seconds: float = 30.0,
        max_ttl_seconds: float = 120.0,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if (
            isinstance(max_ttl_seconds, bool)
            or not isinstance(max_ttl_seconds, (int, float))
            or not math.isfinite(max_ttl_seconds)
            or not 1.0 <= max_ttl_seconds <= _ABSOLUTE_MAX_TTL_SECONDS
        ):
            raise ValueError("max_ttl_seconds must be between 1 and 300 seconds.")
        if (
            isinstance(default_ttl_seconds, bool)
            or not isinstance(default_ttl_seconds, (int, float))
            or not math.isfinite(default_ttl_seconds)
            or not 1.0 <= default_ttl_seconds <= max_ttl_seconds
        ):
            raise ValueError("default_ttl_seconds must be between 1 and max_ttl_seconds.")
        self._default_ttl_seconds = float(default_ttl_seconds)
        self._max_ttl_seconds = float(max_ttl_seconds)
        self._clock = clock
        self._pending: dict[str, _PendingConfirmation] = {}
        self._lock = threading.Lock()
        self._now()

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def issue(
        self,
        invocation: SkillInvocation,
        *,
        ttl_seconds: float | None = None,
    ) -> ConfirmationGrant:
        ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if (
            isinstance(ttl, bool)
            or not isinstance(ttl, (int, float))
            or not math.isfinite(ttl)
            or not 1.0 <= ttl <= self._max_ttl_seconds
        ):
            raise ValueError(
                f"ttl_seconds must be between 1 and {self._max_ttl_seconds:g} seconds."
            )
        now = self._now()
        expires_at = now + timedelta(seconds=float(ttl))
        token = secrets.token_urlsafe(32)
        token_digest = self._token_digest(token)
        pending = _PendingConfirmation(self._fingerprint(invocation), expires_at)
        with self._lock:
            self._purge_locked(now)
            self._pending[token_digest] = pending
        return ConfirmationGrant(token, expires_at)

    def consume(self, token: str, invocation: SkillInvocation) -> ConfirmationValidation:
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return ConfirmationValidation.INVALID
        now = self._now()
        token_digest = self._token_digest(token)
        with self._lock:
            pending = self._pending.pop(token_digest, None)
        if pending is None:
            return ConfirmationValidation.INVALID
        if pending.expires_at <= now:
            return ConfirmationValidation.EXPIRED
        actual_fingerprint = self._fingerprint(invocation)
        if not secrets.compare_digest(pending.invocation_fingerprint, actual_fingerprint):
            return ConfirmationValidation.MISMATCH
        return ConfirmationValidation.ACCEPTED

    def purge_expired(self) -> int:
        now = self._now()
        with self._lock:
            return self._purge_locked(now)

    def _purge_locked(self, now: datetime) -> int:
        expired = [digest for digest, pending in self._pending.items() if pending.expires_at <= now]
        for digest in expired:
            del self._pending[digest]
        return len(expired)

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("The confirmation clock must return a timezone-aware datetime.")
        return value.astimezone(UTC)

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint(invocation: SkillInvocation) -> str:
        payload = canonical_json(invocation.confirmation_payload()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
