"""Bridge assistant plans into capability-scoped verified skills.

This module deliberately prepares commands without invoking the runtime's system effects.
Supported effects are routed through the verified skill engine; unsupported effects continue
through the legacy executor so migration can be incremental and explicit.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .automation import (
    APP_LAUNCH_MANIFEST,
    BROWSER_SEARCH_MANIFEST,
    AppLaunchExecutor,
    AutomationEngine,
    BrowserSearchExecutor,
    ConfirmationAuthority,
    ExecutorRegistry,
    Permission,
    SkillInvocation,
)
from .domain import Action, ActionKind, Plan, RuntimeResult, RuntimeStatus
from .localization import Language, MessageKey, localize, resolve_language
from .runtime import AssistantRuntime
from .verified_skills import (
    ReceiptJournal,
    UnknownConfirmationError,
    VerifiedSkillOutcome,
    VerifiedSkillSession,
)


@dataclass(frozen=True, slots=True)
class VerifiedCommandResult:
    ok: bool
    status: str
    message: str
    action: str
    command: str
    pending_confirmation: dict[str, object] | None = None
    receipt: dict[str, object] | None = None
    verified: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "action": self.action,
            "command": self.command,
            "pending_confirmation": self.pending_confirmation,
            "receipt": self.receipt,
            "verified": self.verified,
        }


@dataclass(frozen=True, slots=True)
class _PreparedCommand:
    input_text: str
    command: str
    language: Language
    plan: Plan | None = None
    terminal_result: RuntimeResult | None = None


@dataclass(frozen=True, slots=True)
class _PendingContext:
    command: str
    language: Language
    action: Action


class _AutomationEffects:
    """Async adapter around the runtime's already-injected operating-system effects."""

    def __init__(self, runtime: AssistantRuntime) -> None:
        self._effects = runtime.executor.effects

    async def open_url(self, url: str) -> None:
        self._effects.open_url(url)

    async def launch_app(self, app_id: str) -> None:
        self._effects.open_app(app_id)


def default_receipts_path(runtime: AssistantRuntime) -> Path:
    return Path(runtime.config.tasks_path).parent / "execution-receipts.jsonl"


def build_verified_session(
    runtime: AssistantRuntime,
    *,
    journal: ReceiptJournal | None = None,
) -> tuple[VerifiedSkillSession, ReceiptJournal]:
    effects = _AutomationEffects(runtime)
    search_host = urlsplit(runtime.config.search_url).hostname or ""
    registry = ExecutorRegistry(
        {
            BROWSER_SEARCH_MANIFEST.executor_id,
            APP_LAUNCH_MANIFEST.executor_id,
        }
    )
    registry.register(
        BrowserSearchExecutor(
            effects,
            search_endpoint=runtime.config.search_url,
            allowed_hosts={search_host},
            max_query_length=runtime.config.max_query_length,
        )
    )
    registry.register(
        AppLaunchExecutor(
            effects,
            allowed_app_ids=runtime.config.allowed_app_ids,
        )
    )
    engine = AutomationEngine(
        [BROWSER_SEARCH_MANIFEST, APP_LAUNCH_MANIFEST],
        registry,
        ConfirmationAuthority(),
        allowed_permissions={Permission.BROWSER_OPEN_URL, Permission.APP_LAUNCH},
    )
    receipt_journal = journal or ReceiptJournal(default_receipts_path(runtime))
    return VerifiedSkillSession(engine, receipts=receipt_journal), receipt_journal


class VerifiedRuntimeBridge:
    """Plan without effects, route reviewed actions, and expose safe UI results."""

    def __init__(
        self,
        runtime: AssistantRuntime,
        *,
        session: VerifiedSkillSession | None = None,
        journal: ReceiptJournal | None = None,
    ) -> None:
        self.runtime = runtime
        if session is None:
            session, built_journal = build_verified_session(runtime, journal=journal)
            self._journal = built_journal
        else:
            self._journal = journal or ReceiptJournal()
        self._session = session
        self._pending: dict[str, _PendingContext] = {}
        self._lock = threading.RLock()

    @property
    def receipt_integrity_ok(self) -> bool:
        return ReceiptJournal.verify(self._journal.receipts)

    def execute(self, command: str) -> VerifiedCommandResult:
        prepared = self._prepare(command)
        if prepared.terminal_result is not None:
            return self._legacy_result(prepared.terminal_result, command)
        action = self._single_action(prepared)
        invocation = self._invocation(action) if action is not None else None
        if action is None or invocation is None:
            return self._legacy_result(self._execute_legacy(prepared), command)

        outcome = asyncio.run(self._session.submit(invocation))
        if outcome.pending_confirmation is not None:
            confirmation_id = outcome.pending_confirmation.confirmation_id
            with self._lock:
                self._pending[confirmation_id] = _PendingContext(
                    command,
                    prepared.language,
                    action,
                )
            return VerifiedCommandResult(
                True,
                "confirmation_required",
                localize(MessageKey.CONFIRMATION_REQUIRED, prepared.language),
                action.kind.value,
                command,
                pending_confirmation=outcome.pending_confirmation.to_dict(),
                receipt=outcome.receipt.to_dict(),
                verified=True,
            )
        return self._outcome_result(outcome, command, prepared.language, action)

    def approve(self, confirmation_id: str) -> VerifiedCommandResult:
        context = self._pop_context(confirmation_id)
        try:
            outcome = asyncio.run(self._session.approve(confirmation_id))
        except UnknownConfirmationError:
            return self._invalid_confirmation(context.command, context.action, context.language)
        return self._outcome_result(
            outcome,
            context.command,
            context.language,
            context.action,
        )

    def reject(self, confirmation_id: str) -> VerifiedCommandResult:
        context = self._pop_context(confirmation_id)
        try:
            outcome = self._session.reject(confirmation_id)
        except UnknownConfirmationError:
            return self._invalid_confirmation(context.command, context.action, context.language)
        return VerifiedCommandResult(
            True,
            RuntimeStatus.BLOCKED.value,
            self._cancelled_message(context.language),
            context.action.kind.value,
            context.command,
            receipt=outcome.receipt.to_dict(),
            verified=True,
        )

    def recent_receipts(self, *, limit: int = 20) -> list[dict[str, object]]:
        bounded = max(1, min(int(limit), 100))
        return [receipt.to_dict() for receipt in self._journal.receipts[-bounded:]][::-1]

    def _prepare(self, text: str) -> _PreparedCommand:
        text = text.strip()
        language = resolve_language(self.runtime.config.language, text=text)
        if not text:
            return _PreparedCommand(
                text,
                "",
                language,
                terminal_result=RuntimeResult(
                    RuntimeStatus.UNHANDLED,
                    localize(MessageKey.EMPTY_INPUT, language),
                ),
            )

        command = text
        if self.runtime.config.require_wake_word:
            extracted = self.runtime.wake_words.extract(text)
            if extracted is None:
                return _PreparedCommand(
                    text,
                    "",
                    language,
                    terminal_result=RuntimeResult(RuntimeStatus.SLEEPING),
                )
            command = extracted
        if not command:
            self.runtime.audit.record("wake_word_detected", command=text)
            return _PreparedCommand(
                text,
                "",
                language,
                terminal_result=RuntimeResult(
                    RuntimeStatus.AWAKE,
                    localize(MessageKey.AWAKE, language),
                ),
            )

        self.runtime.audit.record("command_received", command=command)
        try:
            plan = self.runtime.planner.plan(command)
        except Exception as exc:
            self.runtime.audit.record(
                "planning_failed",
                command=command,
                detail=type(exc).__name__,
            )
            return _PreparedCommand(
                text,
                command,
                language,
                terminal_result=RuntimeResult(
                    RuntimeStatus.ERROR,
                    localize(MessageKey.UNDERSTANDING_ERROR, language),
                ),
            )
        if plan is None:
            self.runtime.audit.record("command_unhandled", command=command)
            return _PreparedCommand(
                text,
                command,
                language,
                terminal_result=RuntimeResult(
                    RuntimeStatus.UNHANDLED,
                    localize(MessageKey.UNHANDLED, language),
                ),
            )
        if not plan.actions:
            message = plan.reply or localize(MessageKey.UNHANDLED, language)
            return _PreparedCommand(
                text,
                command,
                language,
                plan=plan,
                terminal_result=RuntimeResult(RuntimeStatus.COMPLETED, message, plan),
            )
        return _PreparedCommand(text, command, language, plan=plan)

    def _execute_legacy(self, prepared: _PreparedCommand) -> RuntimeResult:
        plan = prepared.plan
        if plan is None or not plan.actions:
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.UNHANDLED, prepared.language),
                plan,
            )
        executions = tuple(
            self.runtime.executor.execute(action, prepared.command, prepared.language)
            for action in plan.actions
        )
        successes = sum(result.ok for result in executions)
        blocked = sum(result.blocked for result in executions)
        if successes == len(executions):
            status = RuntimeStatus.COMPLETED
        elif blocked == len(executions):
            status = RuntimeStatus.BLOCKED
        elif successes:
            status = RuntimeStatus.PARTIAL
        else:
            status = RuntimeStatus.ERROR
        message = " ".join(result.message for result in executions)
        return RuntimeResult(status, message, plan, executions)

    @staticmethod
    def _single_action(prepared: _PreparedCommand) -> Action | None:
        plan = prepared.plan
        if plan is None or len(plan.actions) != 1:
            return None
        return plan.actions[0]

    @staticmethod
    def _invocation(action: Action) -> SkillInvocation | None:
        if action.kind is ActionKind.OPEN_APP:
            app_id = action.parameters.get("app_id")
            if isinstance(app_id, str):
                return SkillInvocation("app.launch", {"app_id": app_id})
            return None
        if action.kind is ActionKind.OPEN_URL and action.parameters.get("purpose") == "search":
            url = action.parameters.get("url")
            if not isinstance(url, str):
                return None
            try:
                values = parse_qs(urlsplit(url).query, keep_blank_values=True).get("q", [])
            except ValueError:
                return None
            if len(values) == 1 and values[0]:
                return SkillInvocation("browser.search", {"query": values[0]})
        return None

    def _pop_context(self, confirmation_id: str) -> _PendingContext:
        with self._lock:
            context = self._pending.pop(confirmation_id, None)
        if context is None:
            raise UnknownConfirmationError(
                "Confirmation handle is invalid, expired, or already consumed."
            )
        return context

    @staticmethod
    def _legacy_result(result: RuntimeResult, command: str) -> VerifiedCommandResult:
        action = "none"
        if result.plan and result.plan.actions:
            action = result.plan.actions[0].kind.value
        return VerifiedCommandResult(
            result.status in {RuntimeStatus.AWAKE, RuntimeStatus.COMPLETED, RuntimeStatus.PARTIAL},
            result.status.value,
            result.message or "لم أفهم الأمر بعد.",
            action,
            command,
            verified=False,
        )

    @classmethod
    def _invalid_confirmation(
        cls,
        command: str,
        action: Action,
        language: Language,
    ) -> VerifiedCommandResult:
        message = (
            "انتهت صلاحية التأكيد أو تم استخدامه مسبقًا."
            if language is Language.AR
            else "The confirmation expired or was already used."
        )
        return VerifiedCommandResult(
            False,
            RuntimeStatus.BLOCKED.value,
            message,
            action.kind.value,
            command,
            verified=True,
        )

    @staticmethod
    def _cancelled_message(language: Language) -> str:
        return "تم إلغاء الإجراء." if language is Language.AR else "The action was cancelled."

    @classmethod
    def _outcome_result(
        cls,
        outcome: VerifiedSkillOutcome,
        command: str,
        language: Language,
        action: Action,
    ) -> VerifiedCommandResult:
        status = outcome.receipt.status
        succeeded = status == "succeeded"
        if succeeded:
            key = (
                MessageKey.OPENED_APP
                if action.kind is ActionKind.OPEN_APP
                else MessageKey.OPENED_SEARCH
            )
            message = localize(key, language)
            runtime_status = RuntimeStatus.COMPLETED.value
        elif status == "blocked":
            message = localize(MessageKey.SAFETY_REFUSAL, language)
            runtime_status = RuntimeStatus.BLOCKED.value
        elif status == "cancelled":
            message = cls._cancelled_message(language)
            runtime_status = RuntimeStatus.BLOCKED.value
        else:
            message = localize(MessageKey.EXECUTION_ERROR, language)
            runtime_status = RuntimeStatus.ERROR.value
        return VerifiedCommandResult(
            succeeded,
            runtime_status,
            message,
            action.kind.value,
            command,
            receipt=outcome.receipt.to_dict(),
            verified=True,
        )


__all__ = [
    "VerifiedCommandResult",
    "VerifiedRuntimeBridge",
    "build_verified_session",
    "default_receipts_path",
]
