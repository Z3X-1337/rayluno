"""Confirmation-aware runtime wrapper for registered, permission-scoped skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .actions import normalize_text
from .audit import AuditLogger
from .config import AssistantConfig
from .domain import Plan, RuntimeResult, RuntimeStatus
from .localization import Language, MessageKey, localize, resolve_language
from .media import MediaResolver
from .planner import Planner
from .runtime import AssistantRuntime, Effects, build_runtime
from .verified_skills import (
    ExecutionReceipt,
    HashChainedReceiptLedger,
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
    command: str
    language: Language
    plan: Plan
    assessments: tuple[SkillAssessment, ...]


class VerifiedAssistantRuntime:
    """Adds atomic confirmation boundaries and execution receipts to AssistantRuntime."""

    def __init__(
        self,
        runtime: AssistantRuntime,
        *,
        skill_engine: VerifiedSkillEngine | None = None,
        receipt_ledger: ReceiptSink | None = None,
    ) -> None:
        self.runtime = runtime
        self.skill_engine = skill_engine or VerifiedSkillEngine()
        self.receipt_ledger = receipt_ledger or HashChainedReceiptLedger()
        self.pending: PendingExecution | None = None
        self.last_receipts: tuple[ExecutionReceipt, ...] = ()

    def __getattr__(self, name: str):  # noqa: ANN204
        return getattr(self.runtime, name)

    def handle(self, text: str) -> RuntimeResult:
        text = text.strip()
        language = resolve_language(self.runtime.config.language, text=text)
        if not text:
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.EMPTY_INPUT, language),
            )

        command = text
        if self.runtime.config.require_wake_word:
            extracted = self.runtime.wake_words.extract(text)
            if extracted is None:
                return RuntimeResult(RuntimeStatus.SLEEPING)
            command = extracted
        if not command:
            self.runtime.audit.record("wake_word_detected", command=text)
            return RuntimeResult(RuntimeStatus.AWAKE, localize(MessageKey.AWAKE, language))

        normalized = normalize_text(command).strip(" .،!?؟")
        if normalized in _CONFIRM:
            return self._confirm()
        if normalized in _CANCEL:
            return self._cancel(language)

        if self.pending is not None:
            previous = self.pending
            self.pending = None
            self.runtime.audit.record(
                "confirmation_replaced",
                command=previous.command,
                action=previous.plan.actions[0],
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
            return RuntimeResult(
                RuntimeStatus.ERROR,
                localize(MessageKey.UNDERSTANDING_ERROR, language),
            )
        if plan is None:
            self.runtime.audit.record("command_unhandled", command=command)
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.UNHANDLED, language),
            )
        if not plan.actions:
            message = plan.reply or localize(MessageKey.UNHANDLED, language)
            return RuntimeResult(RuntimeStatus.COMPLETED, message, plan)

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

        assessment_tuple = tuple(assessments)
        if any(item.requires_confirmation for item in assessment_tuple):
            self.pending = PendingExecution(command, language, plan, assessment_tuple)
            first = next(item for item in assessment_tuple if item.requires_confirmation)
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
                self._confirmation_message(first, language),
                plan,
            )

        return self._execute(command, language, plan, assessment_tuple, confirmed=False)

    def _confirm(self) -> RuntimeResult:
        pending = self.pending
        if pending is None:
            language = resolve_language(self.runtime.config.language)
            return RuntimeResult(RuntimeStatus.UNHANDLED, self._nothing_pending_message(language))
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

    def _cancel(self, language: Language) -> RuntimeResult:
        pending = self.pending
        if pending is None:
            return RuntimeResult(RuntimeStatus.UNHANDLED, self._nothing_pending_message(language))
        self.pending = None
        self.runtime.audit.record(
            "confirmation_cancelled",
            command=pending.command,
            action=pending.plan.actions[0],
        )
        return RuntimeResult(RuntimeStatus.COMPLETED, self._cancelled_message(language), pending.plan)

    def _execute(
        self,
        command: str,
        language: Language,
        plan: Plan,
        assessments: tuple[SkillAssessment, ...],
        *,
        confirmed: bool,
    ) -> RuntimeResult:
        executions = tuple(
            self.runtime.executor.execute(action, command, language) for action in plan.actions
        )
        self.last_receipts = tuple(
            self.receipt_ledger.record(assessment, execution)
            for assessment, execution in zip(assessments, executions, strict=True)
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
        if confirmed and self.last_receipts:
            message = f"{message} {self._receipt_message(self.last_receipts[-1], language)}"
        return RuntimeResult(status, message, plan, executions)

    @staticmethod
    def _confirmation_message(assessment: SkillAssessment, language: Language) -> str:
        manifest = assessment.manifest
        if language is Language.EN:
            return (
                "Confirmation required. "
                f"Skill: {manifest.skill_id}. Permission: {manifest.permission}. "
                f"Risk: {manifest.risk.value}. Say 'confirm' or 'cancel'."
            )
        return (
            "يلزم تأكيد صريح. "
            f"المهارة: {manifest.skill_id}. الصلاحية: {manifest.permission}. "
            f"المخاطر: {manifest.risk.value}. قل «تأكيد» أو «إلغاء»."
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
    )


def _default_receipt_path(config: AssistantConfig) -> Path | None:
    if config.audit_path is None:
        return None
    return Path(config.audit_path).with_name("execution-receipts.jsonl")
