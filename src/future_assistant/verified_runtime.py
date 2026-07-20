"""Confirmation-aware runtime wrapper for registered, permission-scoped skills."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .actions import normalize_text
from .audit import AuditLogger
from .config import AssistantConfig
from .domain import ExecutionResult, Plan, RuntimeResult, RuntimeStatus
from .localization import Language, MessageKey, localize, resolve_language
from .media import MediaResolver
from .planner import Planner
from .runtime import AssistantRuntime, Effects, build_runtime
from .verified_skills import (
    ExecutionReceipt,
    HashChainedReceiptLedger,
    ReceiptIntegrityError,
    ReceiptSink,
    SkillAssessment,
    VerifiedSkillEngine,
)

_CONFIRM = {
    "تاكيد",
    "اكد",
    "نفذ",
    "موافق",
    "confirm",
    "confirmed",
    "execute",
    "proceed",
    "yes proceed",
}
_CANCEL = {
    "الغاء",
    "الغي",
    "لا تنفذ",
    "cancel",
    "abort",
    "do not execute",
}


@dataclass(frozen=True, slots=True)
class PendingExecution:
    confirmation_id: str
    command: str
    language: Language
    plan: Plan
    assessments: tuple[SkillAssessment, ...]
    created_at: datetime
    expires_at: datetime
    argument_keys: tuple[str, ...]
    argument_digest: str


class VerifiedAssistantRuntime:
    """Apply expiring confirmation handles and verifiable receipts to a runtime."""

    def __init__(
        self,
        runtime: AssistantRuntime,
        *,
        skill_engine: VerifiedSkillEngine | None = None,
        receipt_ledger: ReceiptSink | None = None,
        clock: Callable[[], datetime] | None = None,
        confirmation_ttl_seconds: int = 45,
    ) -> None:
        if not 1 <= confirmation_ttl_seconds <= 300:
            raise ValueError("confirmation_ttl_seconds must be between 1 and 300.")
        self.runtime = runtime
        self.skill_engine = skill_engine or VerifiedSkillEngine()
        self.receipt_ledger = receipt_ledger or HashChainedReceiptLedger()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.confirmation_ttl_seconds = confirmation_ttl_seconds
        self.pending: PendingExecution | None = None
        self.last_receipts: tuple[ExecutionReceipt, ...] = ()

    def __getattr__(self, name: str):  # noqa: ANN204
        return getattr(self.runtime, name)

    @property
    def receipt_integrity_ok(self) -> bool:
        verifier = getattr(self.receipt_ledger, "verify_integrity", None)
        if callable(verifier):
            try:
                return bool(verifier(reload=True))
            except Exception:
                return False
        return bool(getattr(self.receipt_ledger, "integrity_ok", True))

    def pending_public(self) -> dict[str, object] | None:
        pending = self.pending
        if pending is None:
            return None
        if self._now() >= pending.expires_at:
            self._expire_pending(pending)
            return None
        primary = next(
            (item for item in pending.assessments if item.requires_confirmation),
            pending.assessments[0],
        )
        return {
            "confirmation_id": pending.confirmation_id,
            "created_at": pending.created_at.isoformat(),
            "expires_at": pending.expires_at.isoformat(),
            "skill_id": primary.manifest.skill_id,
            "permission": primary.manifest.permission,
            "risk": primary.manifest.risk.value,
            "argument_keys": list(pending.argument_keys),
            "argument_digest": pending.argument_digest,
            "skills": [
                {
                    "skill_id": item.manifest.skill_id,
                    "permission": item.manifest.permission,
                    "risk": item.manifest.risk.value,
                    "confirmation": item.manifest.confirmation.value,
                }
                for item in pending.assessments
            ],
        }

    def approve(self, confirmation_id: str) -> RuntimeResult:
        self.last_receipts = ()
        return self._confirm(confirmation_id)

    def reject(self, confirmation_id: str) -> RuntimeResult:
        self.last_receipts = ()
        if self.pending is not None:
            language = self.pending.language
        else:
            language = resolve_language(self.runtime.config.language)
        return self._cancel(language, confirmation_id)

    def handle(self, text: str) -> RuntimeResult:
        self.last_receipts = ()
        text = text.strip()
        language = resolve_language(self.runtime.config.language, text=text)
        if not text:
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.EMPTY_INPUT, language),
            )

        command = self._extract_command(text)
        if command is None:
            return RuntimeResult(RuntimeStatus.SLEEPING)
        if not command:
            self.runtime.audit.record("wake_word_detected", command=text)
            return RuntimeResult(RuntimeStatus.AWAKE, localize(MessageKey.AWAKE, language))

        normalized = normalize_text(command).strip(" .،!?؟")
        if normalized in _CONFIRM:
            return self._confirm()
        if normalized in _CANCEL:
            return self._cancel(language)

        self._replace_pending_if_needed()
        self.runtime.audit.record("command_received", command=command)
        plan = self._plan(command, language)
        if isinstance(plan, RuntimeResult):
            return plan
        if plan is None:
            self.runtime.audit.record("command_unhandled", command=command)
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.UNHANDLED, language),
            )
        if not plan.actions:
            message = plan.reply or localize(MessageKey.UNHANDLED, language)
            return RuntimeResult(RuntimeStatus.COMPLETED, message, plan)

        assessments = self._assess(plan, command, language)
        if isinstance(assessments, RuntimeResult):
            return assessments
        if not self.receipt_integrity_ok:
            return self._integrity_block(command, language, plan)

        if any(item.requires_confirmation for item in assessments):
            return self._request_confirmation(command, language, plan, assessments)
        return self._execute(command, language, plan, assessments, confirmed=False)

    def _extract_command(self, text: str) -> str | None:
        if not self.runtime.config.require_wake_word:
            return text
        return self.runtime.wake_words.extract(text)

    def _replace_pending_if_needed(self) -> None:
        previous = self.pending
        if previous is None:
            return
        self.pending = None
        self._record_without_effect(
            previous,
            event="confirmation_replaced",
            confirmation_state="replaced",
            status="cancelled",
        )
        self.runtime.audit.record(
            "confirmation_replaced",
            command=previous.command,
            action=previous.plan.actions[0],
        )

    def _plan(self, command: str, language: Language) -> Plan | RuntimeResult | None:
        try:
            return self.runtime.planner.plan(command)
        except Exception as exc:
            self.runtime.audit.record(
                "planning_failed",
                command=command,
                detail=type(exc).__name__,
            )
            return RuntimeResult(
                RuntimeStatus.ERROR,
                localize(MessageKey.UNDERSTANDING_ERROR, language),
            )

    def _assess(
        self,
        plan: Plan,
        command: str,
        language: Language,
    ) -> tuple[SkillAssessment, ...] | RuntimeResult:
        assessments: list[SkillAssessment] = []
        for action in plan.actions:
            assessment = self.skill_engine.assess(action, plan.source)
            if assessment is None:
                self.runtime.audit.record(
                    "skill_blocked",
                    command=command,
                    action=action,
                    detail="unregistered_skill",
                )
                return RuntimeResult(
                    RuntimeStatus.BLOCKED,
                    self._unregistered_message(language),
                    plan,
                )
            assessments.append(assessment)
        return tuple(assessments)

    def _integrity_block(
        self,
        command: str,
        language: Language,
        plan: Plan,
    ) -> RuntimeResult:
        self.runtime.audit.record(
            "verified_execution_blocked",
            command=command,
            action=plan.actions[0],
            detail="receipt_integrity_failed",
        )
        return RuntimeResult(
            RuntimeStatus.BLOCKED,
            self._integrity_failure_message(language),
            plan,
        )

    def _request_confirmation(
        self,
        command: str,
        language: Language,
        plan: Plan,
        assessments: tuple[SkillAssessment, ...],
    ) -> RuntimeResult:
        pending = self._new_pending(command, language, plan, assessments)
        self.pending = pending
        self.last_receipts = self._record_without_effect(
            pending,
            event="confirmation_requested",
            confirmation_state="pending",
            status="pending",
        )
        first = next(item for item in assessments if item.requires_confirmation)
        self.runtime.audit.record(
            "confirmation_requested",
            command=command,
            action=plan.actions[0],
            detail=(
                f"skill:{first.manifest.skill_id};"
                f"permission:{first.manifest.permission};"
                f"risk:{first.manifest.risk.value}"
            ),
        )
        return RuntimeResult(
            RuntimeStatus.CONFIRMATION_REQUIRED,
            self._confirmation_message(first, language, self.confirmation_ttl_seconds),
            plan,
        )

    def _confirm(self, confirmation_id: str | None = None) -> RuntimeResult:
        pending = self.pending
        if pending is None:
            language = resolve_language(self.runtime.config.language)
            return RuntimeResult(RuntimeStatus.UNHANDLED, self._nothing_pending_message(language))
        if self._now() >= pending.expires_at:
            return self._expire_pending(pending)
        if confirmation_id is not None and not self._confirmation_matches(
            pending.confirmation_id,
            confirmation_id,
        ):
            self.runtime.audit.record(
                "confirmation_invalid",
                command=pending.command,
                action=pending.plan.actions[0],
                detail="handle_mismatch",
            )
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._invalid_confirmation_message(pending.language),
                pending.plan,
            )
        if not self.receipt_integrity_ok:
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._integrity_failure_message(pending.language),
                pending.plan,
            )
        self.pending = None
        self.runtime.audit.record(
            "confirmation_accepted",
            command=pending.command,
            action=pending.plan.actions[0],
        )
        return self._execute(
            pending.command,
            pending.language,
            pending.plan,
            pending.assessments,
            confirmed=True,
        )

    def _cancel(
        self,
        language: Language,
        confirmation_id: str | None = None,
    ) -> RuntimeResult:
        pending = self.pending
        if pending is None:
            return RuntimeResult(RuntimeStatus.UNHANDLED, self._nothing_pending_message(language))
        if self._now() >= pending.expires_at:
            return self._expire_pending(pending)
        if confirmation_id is not None and not self._confirmation_matches(
            pending.confirmation_id,
            confirmation_id,
        ):
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._invalid_confirmation_message(pending.language),
                pending.plan,
            )
        self.pending = None
        self.last_receipts = self._record_without_effect(
            pending,
            event="confirmation_rejected",
            confirmation_state="rejected",
            status="cancelled",
        )
        self.runtime.audit.record(
            "confirmation_cancelled",
            command=pending.command,
            action=pending.plan.actions[0],
        )
        return RuntimeResult(
            RuntimeStatus.COMPLETED,
            self._cancelled_message(pending.language),
            pending.plan,
        )

    def _expire_pending(self, pending: PendingExecution) -> RuntimeResult:
        if self.pending is pending:
            self.pending = None
        self.last_receipts = self._record_without_effect(
            pending,
            event="confirmation_expired",
            confirmation_state="expired",
            status="expired",
        )
        self.runtime.audit.record(
            "confirmation_expired",
            command=pending.command,
            action=pending.plan.actions[0],
        )
        return RuntimeResult(
            RuntimeStatus.BLOCKED,
            self._expired_confirmation_message(pending.language),
            pending.plan,
        )

    def _execute(
        self,
        command: str,
        language: Language,
        plan: Plan,
        assessments: tuple[SkillAssessment, ...],
        *,
        confirmed: bool,
    ) -> RuntimeResult:
        if not self.receipt_integrity_ok:
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._integrity_failure_message(language),
                plan,
            )
        confirmation_state = "approved" if confirmed else "not_required"
        authorization_receipts: list[ExecutionReceipt] = []
        try:
            for assessment, action in zip(assessments, plan.actions, strict=True):
                authorization_receipts.append(
                    self.receipt_ledger.record(
                        assessment,
                        ExecutionResult(action, False, "execution_authorized"),
                        event="execution_authorized",
                        confirmation_state=confirmation_state,
                        status_override="authorized",
                    )
                )
        except ReceiptIntegrityError:
            self.last_receipts = tuple(authorization_receipts)
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._authorization_failure_message(language),
                plan,
            )

        executions = tuple(
            self.runtime.executor.execute(action, command, language) for action in plan.actions
        )
        outcome_receipts: list[ExecutionReceipt] = []
        try:
            for assessment, execution in zip(assessments, executions, strict=True):
                outcome_receipts.append(
                    self.receipt_ledger.record(
                        assessment,
                        execution,
                        event="execution",
                        confirmation_state=confirmation_state,
                    )
                )
        except ReceiptIntegrityError:
            self.last_receipts = tuple(authorization_receipts + outcome_receipts)
            return RuntimeResult(
                RuntimeStatus.ERROR,
                self._receipt_write_failure_message(language),
                plan,
                executions,
            )
        self.last_receipts = tuple(authorization_receipts + outcome_receipts)
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
        if confirmed and self.last_receipts:
            message = f"{message} {self._receipt_message(self.last_receipts[-1], language)}"
        return RuntimeResult(status, message, plan, executions)

    def _new_pending(
        self,
        command: str,
        language: Language,
        plan: Plan,
        assessments: tuple[SkillAssessment, ...],
    ) -> PendingExecution:
        created_at = self._now()
        arguments: dict[str, object] = {}
        for index, action in enumerate(plan.actions):
            for key, value in action.parameters.items():
                arguments[f"{index}:{key}"] = value
        return PendingExecution(
            confirmation_id=secrets.token_urlsafe(18),
            command=command,
            language=language,
            plan=plan,
            assessments=assessments,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=self.confirmation_ttl_seconds),
            argument_keys=tuple(sorted(arguments)),
            argument_digest=self._digest(arguments),
        )

    def _record_without_effect(
        self,
        pending: PendingExecution,
        *,
        event: str,
        confirmation_state: str,
        status: str,
    ) -> tuple[ExecutionReceipt, ...]:
        if not self.receipt_integrity_ok:
            return ()
        receipts: list[ExecutionReceipt] = []
        for action, assessment in zip(
            pending.plan.actions,
            pending.assessments,
            strict=True,
        ):
            result = ExecutionResult(action, False, event, blocked=False)
            try:
                receipt = self.receipt_ledger.record(
                    assessment,
                    result,
                    event=event,
                    confirmation_state=confirmation_state,
                    status_override=status,
                )
            except ReceiptIntegrityError:
                return tuple(receipts)
            receipts.append(receipt)
        return tuple(receipts)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _digest(value: Mapping[str, object]) -> str:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _confirmation_matches(expected: str, received: str) -> bool:
        return bool(received) and secrets.compare_digest(expected, received.strip())

    @staticmethod
    def _confirmation_message(
        assessment: SkillAssessment,
        language: Language,
        ttl_seconds: int,
    ) -> str:
        manifest = assessment.manifest
        if language is Language.EN:
            return (
                "Confirmation required. "
                f"Skill: {manifest.skill_id}. Permission: {manifest.permission}. "
                f"Risk: {manifest.risk.value}. Expires in {ttl_seconds} seconds."
            )
        return (
            "يلزم تأكيد صريح. "
            f"المهارة: {manifest.skill_id}. الصلاحية: {manifest.permission}. "
            f"المخاطر: {manifest.risk.value}. تنتهي المهلة خلال {ttl_seconds} ثانية."
        )

    @staticmethod
    def _receipt_message(receipt: ExecutionReceipt, language: Language) -> str:
        if language is Language.EN:
            return f"Execution receipt: {receipt.receipt_id}."
        return f"إيصال التنفيذ: {receipt.receipt_id}."

    @staticmethod
    def _unregistered_message(language: Language) -> str:
        if language is Language.EN:
            return "The proposed action is not a registered Rayluno skill."
        return "الإجراء المقترح ليس مهارة مسجلة في رايلونو."

    @staticmethod
    def _nothing_pending_message(language: Language) -> str:
        if language is Language.EN:
            return "There is no action waiting for confirmation."
        return "لا يوجد إجراء بانتظار التأكيد."

    @staticmethod
    def _cancelled_message(language: Language) -> str:
        if language is Language.EN:
            return "The pending action was cancelled without execution."
        return "أُلغي الإجراء المعلّق دون تنفيذ."

    @staticmethod
    def _expired_confirmation_message(language: Language) -> str:
        if language is Language.EN:
            return "The confirmation expired. No action was executed."
        return "انتهت مهلة التأكيد ولم يُنفّذ أي إجراء."

    @staticmethod
    def _invalid_confirmation_message(language: Language) -> str:
        if language is Language.EN:
            return "The confirmation handle is invalid or was already consumed."
        return "معرّف التأكيد غير صالح أو تم استخدامه مسبقًا."

    @staticmethod
    def _integrity_failure_message(language: Language) -> str:
        if language is Language.EN:
            return "Verified execution is paused because the receipt journal failed validation."
        return "أُوقف التنفيذ الموثق لأن سجل الإيصالات لم يجتز التحقق."

    @staticmethod
    def _authorization_failure_message(language: Language) -> str:
        if language is Language.EN:
            return "No action was executed because authorization proof could not be sealed."
        return "لم يُنفّذ أي إجراء لأن تعذّر ختم إثبات التصريح بالتنفيذ."

    @staticmethod
    def _authorization_failure_message(language: Language) -> str:
        if language is Language.EN:
            return "No action was executed because authorization proof could not be sealed."
        return "لم يُنفّذ أي إجراء لأن تعذّر ختم إثبات التصريح بالتنفيذ."

    @staticmethod
    def _receipt_write_failure_message(language: Language) -> str:
        if language is Language.EN:
            return "The action ran, but its execution receipt could not be sealed safely."
        return "نُفّذ الإجراء، لكن تعذّر ختم إيصال التنفيذ بأمان."


def build_verified_runtime(
    config: AssistantConfig | None = None,
    *,
    effects: Effects | None = None,
    audit: AuditLogger | None = None,
    ollama_client=None,  # noqa: ANN001
    media_resolver: MediaResolver | None = None,
    feature_checker=None,  # noqa: ANN001
    planner: Planner | None = None,
    skill_engine: VerifiedSkillEngine | None = None,
    receipt_ledger: ReceiptSink | None = None,
    clock: Callable[[], datetime] | None = None,
    confirmation_ttl_seconds: int = 45,
) -> VerifiedAssistantRuntime:
    config = config or AssistantConfig.from_env()
    runtime = build_runtime(
        config,
        effects=effects,
        audit=audit,
        ollama_client=ollama_client,
        media_resolver=media_resolver,
        feature_checker=feature_checker,
    )
    if planner is not None:
        runtime.planner = planner
    if receipt_ledger is None:
        receipt_path = _default_receipt_path(config)
        receipt_ledger = HashChainedReceiptLedger(receipt_path)
    return VerifiedAssistantRuntime(
        runtime,
        skill_engine=skill_engine,
        receipt_ledger=receipt_ledger,
        clock=clock,
        confirmation_ttl_seconds=confirmation_ttl_seconds,
    )


def _default_receipt_path(config: AssistantConfig) -> Path | None:
    if config.audit_path is None:
        return None
    return Path(config.audit_path).with_name("execution-receipts.jsonl")


__all__ = [
    "PendingExecution",
    "VerifiedAssistantRuntime",
    "build_verified_runtime",
]
