"""Bilingual reminder and daily-agenda command planner."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import Plan, PlanSource
from .localization import Language, detect_language
from .reminders import AgendaService, AgendaSnapshot, Reminder, ReminderService
from .tasks import Task, TaskPriority

_NUMBER_WORDS = {
    "واحد": 1,
    "واحده": 1,
    "دقيقه": 1,
    "خمس": 5,
    "خمسه": 5,
    "عشر": 10,
    "عشره": 10,
    "ربع": 15,
    "خمسه عشر": 15,
    "ثلاثين": 30,
    "نصف": 30,
    "ساعه": 60,
    "one": 1,
    "five": 5,
    "ten": 10,
    "fifteen": 15,
    "thirty": 30,
    "sixty": 60,
    "an hour": 60,
}


class AgendaCommandPlanner:
    def __init__(self, reminders: ReminderService, agenda: AgendaService) -> None:
        self.reminders = reminders
        self.agenda = agenda

    def plan(self, normalized: str, original: str) -> Plan | None:
        language = detect_language(original, fallback=Language.AR)

        if normalized in {
            "ما خطتي اليوم",
            "شو خطتي اليوم",
            "ملخص اليوم",
            "اجندة اليوم",
            "اجنده اليوم",
            "جدول اليوم",
            "what is my plan today",
            "what's my plan today",
            "today's plan",
            "daily agenda",
            "daily brief",
        }:
            return self._reply(self._format_agenda(self.agenda.snapshot(), language))

        if normalized in {
            "شو عندي متاخر",
            "ما المتاخر",
            "المهام المتاخرة",
            "التذكيرات المتاخرة",
            "what is overdue",
            "what's overdue",
            "show overdue",
        }:
            return self._reply(self._format_overdue(self.agenda.snapshot(), language))

        if normalized in {
            "التذكيرات",
            "اعرض التذكيرات",
            "تذكيراتي",
            "show reminders",
            "list reminders",
            "show my reminders",
        }:
            return self._reply(self._format_reminders(self.reminders.list(), language))

        reminder_id = self._match_id(
            normalized,
            (
                r"^(?:انجز|اكمل|انهي)(?: التذكير)?\s+(?:رقم\s+)?(\d+)$",
                r"^(?:complete|finish)(?: reminder)?\s+(\d+)$",
            ),
        )
        if reminder_id is not None:
            reminder = self.reminders.complete(reminder_id)
            return self._reply(self._mutation_message("completed", reminder, language))

        snooze = self._match_snooze(normalized)
        if snooze is not None:
            reminder_id, minutes = snooze
            reminder = self.reminders.snooze(reminder_id, minutes)
            return self._reply(self._mutation_message("snoozed", reminder, language, minutes))

        parsed = self._parse_creation(normalized)
        if parsed is None:
            return None
        mode, value, title, priority = parsed
        if mode == "after":
            reminder = self.reminders.create_after(title, minutes=value, priority=priority)
        else:
            reminder = self.reminders.create_at(
                title,
                hour=value // 60,
                minute=value % 60,
                priority=priority,
            )
        return self._reply(self._created_message(reminder, language))

    @staticmethod
    def _reply(message: str) -> Plan:
        return Plan(reply=message, source=PlanSource.DETERMINISTIC)

    @staticmethod
    def _match_id(normalized: str, patterns: Sequence[str]) -> int | None:
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                return int(match.group(1))
        return None

    def _match_snooze(self, normalized: str) -> tuple[int, int] | None:
        patterns = (
            r"^(?:اجل|أجل|غفوه)(?: التذكير)?\s+(?:رقم\s+)?(\d+)\s+(.+?)"
            r"(?:\s+دقائق?|\s+دقيقه)?$",
            r"^snooze(?: reminder)?\s+(\d+)\s+(?:for\s+)?(.+?)(?:\s+minutes?)?$",
        )
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            minutes = self._minutes(match.group(2))
            if minutes is not None:
                return int(match.group(1)), minutes
        return None

    def _parse_creation(self, normalized: str) -> tuple[str, int, str, str] | None:
        relative_patterns = (
            r"^ذكرني بعد\s+(.+?)\s+(?:دقائق?|دقيقه)\s+(.+)$",
            r"^ذكرني بعد\s+(ساعه|ساعة)\s+(.+)$",
            r"^remind me in\s+(.+?)\s+minutes?\s+to\s+(.+)$",
            r"^remind me in\s+(an hour|one hour)\s+to\s+(.+)$",
        )
        for pattern in relative_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            minutes = self._minutes(match.group(1))
            if minutes is None:
                return None
            title, priority = self._priority(match.group(2))
            return "after", minutes, title, priority

        absolute_patterns = (
            (
                r"^ذكرني(?: اليوم| بكرا| غدا)?\s+(?:الساعه|الساعة)\s+"
                r"(\d{1,2})(?::(\d{2}))?\s*(صباحا|صباح|مساء|مساءا)?\s+(.+)$"
            ),
            r"^remind me at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+to\s+(.+)$",
        )
        for pattern in absolute_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            marker = (match.group(3) or "").casefold()
            if marker in {"pm", "مساء", "مساءا"} and hour < 12:
                hour += 12
            elif marker in {"am", "صباح", "صباحا"} and hour == 12:
                hour = 0
            if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                return None
            title, priority = self._priority(match.group(4))
            return "at", hour * 60 + minute, title, priority
        return None

    @staticmethod
    def _minutes(value: str) -> int | None:
        token = " ".join(value.strip().split())
        if token.isdigit():
            number = int(token)
            return number if 1 <= number <= 1440 else None
        return _NUMBER_WORDS.get(token)

    @staticmethod
    def _priority(value: str) -> tuple[str, str]:
        title = value.strip()
        priority = "normal"
        for pattern, level in (
            (r"\s+(?:باولوية عالية|بأولوية عالية|عاجل|عاجلة|high priority|urgent)$", "high"),
            (r"\s+(?:باولوية منخفضة|بأولوية منخفضة|غير عاجل|low priority)$", "low"),
        ):
            if re.search(pattern, title):
                title = re.sub(pattern, "", title).strip()
                priority = level
                break
        return title, priority

    @staticmethod
    def _created_message(reminder: Reminder, language: Language) -> str:
        local_due = reminder.due_at.astimezone()
        when = local_due.strftime("%Y-%m-%d %H:%M")
        if language is Language.AR:
            return f"أنشأت التذكير رقم {reminder.id} في {when}: {reminder.title}."
        return f"I created reminder {reminder.id} for {when}: {reminder.title}."

    @staticmethod
    def _mutation_message(
        event: str,
        reminder: Reminder | None,
        language: Language,
        minutes: int | None = None,
    ) -> str:
        if reminder is None:
            return (
                "لم أجد تذكيرا بهذا الرقم."
                if language is Language.AR
                else "I couldn't find a reminder with that number."
            )
        if event == "completed":
            return (
                f"أنجزت التذكير رقم {reminder.id}: {reminder.title}."
                if language is Language.AR
                else f"I completed reminder {reminder.id}: {reminder.title}."
            )
        return (
            f"أجلت التذكير رقم {reminder.id} مدة {minutes} دقيقة."
            if language is Language.AR
            else f"I snoozed reminder {reminder.id} for {minutes} minutes."
        )

    @staticmethod
    def _format_reminders(reminders: Sequence[Reminder], language: Language) -> str:
        if not reminders:
            return "لا توجد تذكيرات." if language is Language.AR else "There are no reminders."
        entries = []
        for reminder in reminders:
            due = reminder.due_at.astimezone().strftime("%Y-%m-%d %H:%M")
            entries.append(f"{reminder.id}) {reminder.title} — {due}")
        heading = "تذكيراتك: " if language is Language.AR else "Your reminders: "
        return heading + "؛ ".join(entries)

    @staticmethod
    def _format_overdue(snapshot: AgendaSnapshot, language: Language) -> str:
        task_count = len(snapshot.overdue_tasks)
        reminder_count = len(snapshot.overdue_reminders)
        if task_count == 0 and reminder_count == 0:
            return "لا يوجد شيء متأخر." if language is Language.AR else "Nothing is overdue."
        if language is Language.AR:
            return f"لديك {task_count} مهام متأخرة و{reminder_count} تذكيرات متأخرة."
        return f"You have {task_count} overdue tasks and {reminder_count} overdue reminders."

    @classmethod
    def _format_agenda(cls, snapshot: AgendaSnapshot, language: Language) -> str:
        focus = cls._focus_item(snapshot)
        counts = (
            len(snapshot.overdue_tasks),
            len(snapshot.today_tasks),
            len(snapshot.due_now_reminders),
            len(snapshot.upcoming_reminders),
        )
        if language is Language.AR:
            base = (
                f"ملخص اليوم: {counts[0]} متأخر، {counts[1]} مهام اليوم، "
                f"{counts[2]} تذكيرات قريبة، و{counts[3]} لاحقا اليوم."
            )
            return base + (f" ابدأ بـ: {focus}." if focus else " لا توجد التزامات عاجلة.")
        base = (
            f"Today's brief: {counts[0]} overdue, {counts[1]} tasks due today, "
            f"{counts[2]} reminders due soon, and {counts[3]} later today."
        )
        return base + (f" Start with: {focus}." if focus else " Nothing is urgent.")

    @staticmethod
    def _focus_item(snapshot: AgendaSnapshot) -> str | None:
        candidates: list[Task | Reminder] = [
            *snapshot.overdue_reminders,
            *snapshot.due_now_reminders,
            *snapshot.overdue_tasks,
            *snapshot.today_tasks,
        ]
        if not candidates:
            return None
        priority_order = {TaskPriority.HIGH: 0, TaskPriority.NORMAL: 1, TaskPriority.LOW: 2}
        candidates.sort(key=lambda item: (priority_order[item.priority], item.id))
        return candidates[0].title
