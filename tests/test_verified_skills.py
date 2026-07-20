from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from future_assistant.automation import (
    APP_LAUNCH_MANIFEST,
    BROWSER_SEARCH_MANIFEST,
    AppLaunchExecutor,
    AutomationEngine,
    BrowserSearchExecutor,
    ConfirmationAuthority,
    ExecutionStatus,
    ExecutorRegistry,
    Permission,
    ResultCode,
    SkillInvocation,
)
from future_assistant.verified_skills import (
    ReceiptJournal,
    UnknownConfirmationError,
    VerifiedSkillSession,
)


class FakeEffects:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.apps: list[str] = []

    async def open_url(self, url: str) -> None:
        self.urls.append(url)

    async def launch_app(self, app_id: str) -> None:
        self.apps.append(app_id)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


def _session(
    *,
    journal: ReceiptJournal | None = None,
    clock: MutableClock | None = None,
) -> tuple[VerifiedSkillSession, FakeEffects, MutableClock]:
    effects = FakeEffects()
    current = clock or MutableClock()
    registry = ExecutorRegistry(
        {
            BROWSER_SEARCH_MANIFEST.executor_id,
            APP_LAUNCH_MANIFEST.executor_id,
        }
    )
    registry.register(BrowserSearchExecutor(effects))
    registry.register(AppLaunchExecutor(effects, allowed_app_ids={"calculator", "notepad"}))
    confirmations = ConfirmationAuthority(clock=current)
    engine = AutomationEngine(
        [BROWSER_SEARCH_MANIFEST, APP_LAUNCH_MANIFEST],
        registry,
        confirmations,
        allowed_permissions={Permission.BROWSER_OPEN_URL, Permission.APP_LAUNCH},
    )
    return (
        VerifiedSkillSession(engine, receipts=journal, clock=current),
        effects,
        current,
    )


def test_low_risk_skill_executes_immediately_and_receipt_redacts_values() -> None:
    session, effects, _ = _session()
    secret_query = "private judge strategy"

    outcome = asyncio.run(
        session.submit(SkillInvocation("browser.search", {"query": secret_query}))
    )

    assert outcome.pending_confirmation is None
    assert outcome.receipt.status == ExecutionStatus.SUCCEEDED.value
    assert outcome.receipt.argument_keys == ("query",)
    assert outcome.receipt.result_keys == ("opened", "provider")
    assert effects.urls and "private+judge+strategy" in effects.urls[0]
    assert secret_query not in json.dumps(outcome.to_dict(), ensure_ascii=False)


def test_high_risk_skill_exposes_safe_confirmation_metadata_without_token() -> None:
    session, effects, _ = _session()

    outcome = asyncio.run(session.submit(SkillInvocation("app.launch", {"app_id": "calculator"})))

    pending = outcome.pending_confirmation
    assert pending is not None
    assert pending.skill_id == "app.launch"
    assert pending.risk_level == "high"
    assert pending.permissions == ("app.launch",)
    assert pending.argument_keys == ("app_id",)
    assert effects.apps == []
    exported = json.dumps(outcome.to_dict(), ensure_ascii=False)
    assert "token" not in exported.casefold()
    assert "calculator" not in exported


def test_approval_executes_once_and_replay_is_rejected() -> None:
    session, effects, _ = _session()
    requested = asyncio.run(session.submit(SkillInvocation("app.launch", {"app_id": "calculator"})))
    confirmation_id = requested.pending_confirmation.confirmation_id  # type: ignore[union-attr]

    approved = asyncio.run(session.approve(confirmation_id))

    assert approved.receipt.status == ExecutionStatus.SUCCEEDED.value
    assert approved.receipt.confirmation_state == "approved"
    assert effects.apps == ["calculator"]
    with pytest.raises(UnknownConfirmationError):
        asyncio.run(session.approve(confirmation_id))
    assert effects.apps == ["calculator"]


def test_rejection_never_executes_effect_and_creates_receipt() -> None:
    session, effects, _ = _session()
    requested = asyncio.run(session.submit(SkillInvocation("app.launch", {"app_id": "notepad"})))
    confirmation_id = requested.pending_confirmation.confirmation_id  # type: ignore[union-attr]

    rejected = session.reject(confirmation_id)

    assert rejected.receipt.status == ExecutionStatus.CANCELLED.value
    assert rejected.receipt.code == ResultCode.CANCELLED.value
    assert rejected.receipt.confirmation_state == "rejected"
    assert effects.apps == []


def test_expired_confirmation_fails_closed_and_is_consumed() -> None:
    clock = MutableClock()
    session, effects, _ = _session(clock=clock)
    requested = asyncio.run(session.submit(SkillInvocation("app.launch", {"app_id": "calculator"})))
    confirmation_id = requested.pending_confirmation.confirmation_id  # type: ignore[union-attr]
    clock.value += timedelta(minutes=3)

    approved = asyncio.run(session.approve(confirmation_id))

    assert approved.receipt.status == ExecutionStatus.BLOCKED.value
    assert approved.receipt.code == ResultCode.CONFIRMATION_EXPIRED.value
    assert effects.apps == []
    with pytest.raises(UnknownConfirmationError):
        asyncio.run(session.approve(confirmation_id))


def test_unknown_skill_is_blocked_but_still_receipted() -> None:
    session, _, _ = _session()

    outcome = asyncio.run(session.submit(SkillInvocation("unknown.skill", {})))

    assert outcome.receipt.status == ExecutionStatus.BLOCKED.value
    assert outcome.receipt.code == ResultCode.UNKNOWN_SKILL.value
    assert outcome.receipt.skill_version == "unknown"
    assert outcome.receipt.permissions == ()


def test_receipt_journal_forms_and_verifies_hash_chain(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    journal = ReceiptJournal(path)
    session, _, _ = _session(journal=journal)

    asyncio.run(session.submit(SkillInvocation("browser.search", {"query": "one"})))
    asyncio.run(session.submit(SkillInvocation("browser.search", {"query": "two"})))

    receipts = journal.receipts
    assert len(receipts) == 2
    assert receipts[0].previous_hash == "0" * 64
    assert receipts[1].previous_hash == receipts[0].receipt_hash
    assert ReceiptJournal.verify(receipts)
    assert "one" not in path.read_text(encoding="utf-8")
    assert "two" not in path.read_text(encoding="utf-8")

    reloaded = ReceiptJournal(path)
    assert reloaded.receipts == receipts


def test_receipt_journal_rejects_tampered_history(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    journal = ReceiptJournal(path)
    session, _, _ = _session(journal=journal)
    asyncio.run(session.submit(SkillInvocation("browser.search", {"query": "safe"})))

    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["status"] = "succeeded-but-edited"
    path.write_text(json.dumps(entry), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity verification"):
        ReceiptJournal(path)


def test_pending_list_expires_ui_handles_without_exposing_secrets() -> None:
    clock = MutableClock()
    session, _, _ = _session(clock=clock)
    outcome = asyncio.run(session.submit(SkillInvocation("app.launch", {"app_id": "calculator"})))

    assert session.pending_confirmations() == (outcome.pending_confirmation,)
    clock.value += timedelta(minutes=3)
    assert session.pending_confirmations() == ()
