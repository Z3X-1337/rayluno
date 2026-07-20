"""Bilingual deterministic commands for explicit personal memory."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import Plan, PlanSource
from .localization import Language, detect_language
from .memory import (
    MemoryCategory,
    MemoryFact,
    MemoryService,
    SensitiveMemoryError,
)


class MemoryCommandPlanner:
    def __init__(self, service: MemoryService) -> None:
        self.service = service

    def plan(self, normalized: str, original: str) -> Plan | None:
        language = detect_language(original, fallback=Language.AR)
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

        statement = self._match_remember_statement(normalized)
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
    def _match_remember_statement(normalized: str) -> str | None:
        patterns = (
            r"^(?:تذكر|تذكّر|احفظ|سجل في ذاكرتك|سجل بذاكرتك|خلي ببالك)(?: ان| أن)?\s+(.+)$",
            r"^(?:remember|save)(?: that)?\s+(.+)$",
            r"^keep in mind(?: that)?\s+(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                return match.group(1).strip()
        return None

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
                else "I don't remember anything about you yet. I only save facts when you explicitly ask."
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
    def _sensitive_refusal(language: Language) -> str:
        return (
            "لن أحفظ كلمات المرور أو رموز الدخول أو مفاتيح API أو بيانات الدفع. استخدم مدير كلمات مرور موثوقًا لهذه المعلومات."
            if language is Language.AR
            else "I won't store passwords, access tokens, API keys, or payment details. Use a trusted password manager for secrets."
        )

    @staticmethod
    def _invalid_statement(language: Language) -> str:
        return (
            "لم أستطع حفظ هذه المعلومة. اجعلها واضحة ومختصرة دون بيانات حساسة."
            if language is Language.AR
            else "I couldn't save that memory. Keep it clear, concise, and free of sensitive data."
        )


__all__ = ["MemoryCommandPlanner"]
