"""Bilingual deterministic commands for explicit personal memory."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from .domain import Plan, PlanSource
from .localization import Language, detect_language
from .memory import (
    MemoryCategory,
    MemoryFact,
    MemoryService,
    SensitiveMemoryError,
)

_CLEAR_TTL_SECONDS = 60


class MemoryCommandPlanner:
    def __init__(
        self,
        service: MemoryService,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.service = service
        self.clock = clock or (lambda: datetime.now(UTC))
        self._clear_pending_until: datetime | None = None

    def plan(self, normalized: str, original: str) -> Plan | None:
        language = detect_language(original, fallback=Language.AR)

        if normalized in {
            "تاكيد حذف كل الذاكره",
            "تاكيد حذف كل الذاكرة",
            "confirm delete all memory",
            "confirm clear all memory",
        }:
            return self._confirm_clear(language)

        if normalized in {
            "احذف كل الذاكره",
            "احذف كل الذاكرة",
            "امسح كل الذاكره",
            "امسح كل الذاكرة",
            "انس كل شيء عني",
            "انسى كل شيء عني",
            "delete all memory",
            "clear all memory",
            "forget everything about me",
        }:
            self._clear_pending_until = self._now() + timedelta(seconds=_CLEAR_TTL_SECONDS)
            return self._reply(self._clear_confirmation_message(language))

        if normalized in {
            "ماذا تتذكر عني",
            "ماذا تذكر عني",
            "شو بتتذكر عني",
            "شو تتذكر عني",
            "اعرض ذاكرتك",
            "اعرض ما تتذكره عني",
            "ذاكرتي",
            "what do you remember about me",
            "show memory",
            "show my memory",
            "show what you remember about me",
            "list memories",
        }:
            return self._reply(self._format_memories(self.service.list(), language))

        memory_id = self._match_memory_id(normalized)
        if memory_id is not None:
            fact = self.service.forget(memory_id)
            return self._reply(self._forgot_message(fact, language))

        statement = self._match_remember_statement(normalized, original)
        if statement is None:
            return None
        category = self._category(statement)
        try:
            write = self.service.remember(statement, category=category.value)
        except SensitiveMemoryError:
            return self._reply(self._sensitive_refusal(language))
        except ValueError:
            return self._reply(self._invalid_statement(language))
        return self._reply(
            self._remembered_message(
                write.fact,
                language,
                created=write.created,
            )
        )

    def _confirm_clear(self, language: Language) -> Plan:
        deadline = self._clear_pending_until
        self._clear_pending_until = None
        if deadline is None or self._now() > deadline:
            return self._reply(self._clear_expired_message(language))
        count = self.service.clear()
        return self._reply(self._cleared_message(count, language))

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _reply(message: str) -> Plan:
        return Plan(reply=message, source=PlanSource.DETERMINISTIC)

    @staticmethod
    def _match_memory_id(normalized: str) -> int | None:
        patterns = (
            r"^(?:انس|انسى|احذف|امسح)(?: من)?(?: الذاكره| الذاكرة)?(?: رقم)?\s+(\d+)$",
            r"^(?:forget|delete|remove)(?: memory)?\s+(\d+)$",
            r"^forget memory\s+(\d+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _match_remember_statement(normalized: str, original: str) -> str | None:
        normalized_patterns = (
            r"^(?:تذكر|تذكّر|احفظ|سجل في ذاكرتك|سجل بذاكرتك|خلي ببالك)(?: ان| أن)?\s+(.+)$",
            r"^(?:remember|save)(?: that)?\s+(.+)$",
            r"^keep in mind(?: that)?\s+(.+)$",
        )
        fallback = None
        for pattern in normalized_patterns:
            match = re.match(pattern, normalized)
            if match:
                fallback = match.group(1).strip()
                break
        if fallback is None:
            return None

        original_patterns = (
            (
                r"^\s*(?:تذكر|تذكّر|احفظ|سجل في ذاكرتك|سجل بذاكرتك|خلي ببالك)"
                r"(?:\s+(?:ان|أن))?\s+(.+?)\s*$"
            ),
            r"^\s*(?:remember|save)(?:\s+that)?\s+(.+?)\s*$",
            r"^\s*keep in mind(?:\s+that)?\s+(.+?)\s*$",
        )
        for pattern in original_patterns:
            match = re.match(pattern, original, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" \t\r\n،,.!؟?")
        return fallback

    @staticmethod
    def _category(statement: str) -> MemoryCategory:
        normalized = statement.casefold()
        if any(
            marker in normalized
            for marker in (
                "افضل",
                "أفضل",
                "احب",
                "أحب",
                "بحب",
                "لا احب",
                "لا أحب",
                "prefer",
                "i like",
                "i love",
                "i dislike",
            )
        ):
            return MemoryCategory.PREFERENCE
        if any(
            marker in normalized
            for marker in (
                "اسمي",
                "أنا ",
                "انا ",
                "عمري",
                "my name",
                "i am ",
                "i'm ",
                "my age",
            )
        ):
            return MemoryCategory.IDENTITY
        return MemoryCategory.CONTEXT

    @staticmethod
    def _remembered_message(
        fact: MemoryFact,
        language: Language,
        *,
        created: bool,
    ) -> str:
        if language is Language.AR:
            prefix = "حفظت" if created else "هذه المعلومة محفوظة مسبقًا وحدّثت تاريخها"
            return f"{prefix} في الذاكرة رقم {fact.id}: {fact.statement}."
        prefix = "I saved" if created else "This was already saved, so I refreshed"
        return f"{prefix} memory {fact.id}: {fact.statement}."

    @staticmethod
    def _forgot_message(fact: MemoryFact | None, language: Language) -> str:
        if fact is None:
            return (
                "لم أجد معلومة بهذا الرقم."
                if language is Language.AR
                else "I couldn't find a memory with that number."
            )
        return (
            f"حذفت الذاكرة رقم {fact.id}: {fact.statement}."
            if language is Language.AR
            else f"I deleted memory {fact.id}: {fact.statement}."
        )

    @staticmethod
    def _format_memories(
        memories: Sequence[MemoryFact],
        language: Language,
    ) -> str:
        if not memories:
            return (
                "لا أتذكر عنك شيئًا بعد. لن أحفظ أي معلومة إلا عندما تطلب ذلك صراحة."
                if language is Language.AR
                else (
                    "I don't remember anything about you yet. "
                    "I only save facts when you explicitly ask."
                )
            )
        category_labels = {
            Language.AR: {
                MemoryCategory.IDENTITY: "هوية",
                MemoryCategory.PREFERENCE: "تفضيل",
                MemoryCategory.CONTEXT: "سياق",
                MemoryCategory.OTHER: "أخرى",
            },
            Language.EN: {
                MemoryCategory.IDENTITY: "identity",
                MemoryCategory.PREFERENCE: "preference",
                MemoryCategory.CONTEXT: "context",
                MemoryCategory.OTHER: "other",
            },
        }
        entries = [
            f"{fact.id}) {fact.statement} [{category_labels[language][fact.category]}]"
            for fact in memories
        ]
        if language is Language.AR:
            return f"أتذكر {len(memories)} معلومات بموافقتك: " + "؛ ".join(entries)
        noun = "memory" if len(memories) == 1 else "memories"
        return f"I remember {len(memories)} explicit {noun}: " + "; ".join(entries)

    @staticmethod
    def _clear_confirmation_message(language: Language) -> str:
        if language is Language.AR:
            return (
                "سأحذف كل الذاكرة الشخصية المحلية. للتأكيد خلال 60 ثانية قل: تأكيد حذف كل الذاكرة."
            )
        return (
            "I will delete all local personal memory. Within 60 seconds say: "
            "confirm delete all memory."
        )

    @staticmethod
    def _clear_expired_message(language: Language) -> str:
        if language is Language.AR:
            return "لا يوجد طلب صالح لحذف كل الذاكرة؛ لم يُحذف شيء."
        return "There is no valid delete-all request; nothing was deleted."

    @staticmethod
    def _cleared_message(count: int, language: Language) -> str:
        if language is Language.AR:
            return f"حذفت كل الذاكرة الشخصية المحلية: {count} عناصر."
        return f"I deleted all local personal memory: {count} items."

    @staticmethod
    def _sensitive_refusal(language: Language) -> str:
        return (
            "لن أحفظ كلمات المرور أو رموز الدخول أو مفاتيح API أو بيانات الدفع. "
            "استخدم مدير كلمات مرور موثوقًا لهذه المعلومات."
            if language is Language.AR
            else "I won't store passwords, access tokens, API keys, or payment details. "
            "Use a trusted password manager for secrets."
        )

    @staticmethod
    def _invalid_statement(language: Language) -> str:
        return (
            "لم أستطع حفظ هذه المعلومة. اجعلها واضحة ومختصرة دون بيانات حساسة."
            if language is Language.AR
            else "I couldn't save that memory. Keep it clear, concise, and free of sensitive data."
        )


__all__ = ["MemoryCommandPlanner"]
