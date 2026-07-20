"""Bilingual personal-task command planner.

This module owns task-specific parsing and persistence. It returns reply-only plans, so
operating-system effects and arbitrary shell execution remain outside the task path.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import Plan, PlanSource
from .localization import Language, detect_language
from .tasks import Task, TaskPriority, TaskService


class TaskCommandPlanner:
    def __init__(self, service: TaskService) -> None:
        self.service = service

    def plan(self, normalized: str, original: str) -> Plan | None:
        language = detect_language(original, fallback=Language.AR)
        if normalized in {
            "المهام",
            "مهامي",
            "اعرض المهام",
            "اعرض مهامي",
            "ما هي مهامي",
            "شو مهامي",
            "show tasks",
            "show my tasks",
            "list tasks",
            "list my tasks",
            "what are my tasks",
        }:
            return self._reply(self._format_tasks(self.service.list(), language))

        if normalized in {
            "اعرض كل المهام",
            "اعرض المهام المكتملة",
            "سجل المهام",
            "show all tasks",
            "show completed tasks",
            "task history",
        }:
            return self._reply(
                self._format_tasks(
                    self.service.list(include_completed=True),
                    language,
                )
            )

        task_id = self._match_task_id(
            normalized,
            (
                r"^(?:انجز|اكمل|انهي|اتمم)(?: المهمه| المهمة)?\s+(?:رقم\s+)?(\d+)$",
                r"^(?:complete|finish|done with|mark)(?: task)?\s+(\d+)(?: as done| complete)?$",
                r"^mark task\s+(\d+)\s+(?:done|complete)$",
            ),
        )
        if task_id is not None:
            return self._reply(
                self._task_message("completed", language, self.service.complete(task_id))
            )

        task_id = self._match_task_id(
            normalized,
            (
                r"^(?:احذف|امسح|الغ)(?: المهمه| المهمة)?\s+(?:رقم\s+)?(\d+)$",
                r"^(?:delete|remove|cancel)(?: task)?\s+(\d+)$",
            ),
        )
        if task_id is not None:
            return self._reply(
                self._task_message("deleted", language, self.service.delete(task_id))
            )

        for pattern in (
            r"^(?:اضف|ضيف|سجل|دون)(?: لي)?(?: مهمه| مهمة)?\s+(.+)$",
            r"^(?:ذكرني)(?: ان| ب)?\s+(.+)$",
            r"^(?:add|create)(?: a)? task(?: to)?\s+(.+)$",
            r"^remind me to\s+(.+)$",
        ):
            match = re.match(pattern, normalized)
            if not match:
                continue
            title, priority, due = self._metadata(match.group(1))
            task = self.service.create(title, priority=priority, due=due)
            return self._reply(self._task_message("created", language, task))
        return None

    @staticmethod
    def _reply(message: str) -> Plan:
        return Plan(reply=message, source=PlanSource.DETERMINISTIC)

    @staticmethod
    def _match_task_id(normalized: str, patterns: Sequence[str]) -> int | None:
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _task_message(event: str, language: Language, task: Task | None) -> str:
        if task is None:
            return (
                "لم أجد مهمة بهذا الرقم."
                if language is Language.AR
                else "I couldn't find a task with that number."
            )
        templates = {
            Language.AR: {
                "created": "أضفت المهمة رقم {task_id}: {title}.",
                "completed": "أنجزت المهمة رقم {task_id}: {title}.",
                "deleted": "حذفت المهمة رقم {task_id}: {title}.",
            },
            Language.EN: {
                "created": "I added task {task_id}: {title}.",
                "completed": "I completed task {task_id}: {title}.",
                "deleted": "I deleted task {task_id}: {title}.",
            },
        }
        return templates[language][event].format(task_id=task.id, title=task.title)

    @staticmethod
    def _format_tasks(tasks: Sequence[Task], language: Language) -> str:
        if not tasks:
            return (
                "لا توجد مهام في هذه القائمة."
                if language is Language.AR
                else "There are no tasks in this list."
            )
        labels = {
            TaskPriority.HIGH: ("عالية" if language is Language.AR else "high"),
            TaskPriority.NORMAL: ("عادية" if language is Language.AR else "normal"),
            TaskPriority.LOW: ("منخفضة" if language is Language.AR else "low"),
        }
        entries = []
        for task in tasks:
            due = ""
            if task.due_date is not None:
                due_label = "موعد" if language is Language.AR else "due"
                due = f"، {due_label} {task.due_date.isoformat()}"
            priority_label = "أولوية" if language is Language.AR else "priority"
            state = "✓" if task.completed_at is not None else "○"
            entries.append(
                f"{state} {task.id}) {task.title} "
                f"({priority_label} {labels[task.priority]}{due})"
            )
        if language is Language.AR:
            heading = f"لديك {len(tasks)} مهام: "
        else:
            noun = "task" if len(tasks) == 1 else "tasks"
            heading = f"You have {len(tasks)} {noun}: "
        return heading + "؛ ".join(entries)

    @staticmethod
    def _metadata(value: str) -> tuple[str, str, str | None]:
        title = value.strip()
        due = None
        priority = "normal"

        high_patterns = (
            r"(?:\s+)(?:بأولوية عالية|باولوية عالية|عاجلة|مهمة جدا)$",
            r"(?:\s+)(?:high priority|urgent)$",
        )
        low_patterns = (
            r"(?:\s+)(?:بأولوية منخفضة|باولوية منخفضة|غير عاجلة)$",
            r"(?:\s+)(?:low priority)$",
        )
        if any(re.search(pattern, title) for pattern in high_patterns):
            for pattern in high_patterns:
                title = re.sub(pattern, "", title).strip()
            priority = "high"
        elif any(re.search(pattern, title) for pattern in low_patterns):
            for pattern in low_patterns:
                title = re.sub(pattern, "", title).strip()
            priority = "low"

        for pattern, due_value in (
            (r"(?:\s+)(?:اليوم|لهذا اليوم)$", "today"),
            (r"(?:\s+)(?:غدا|بكرا|للغد)$", "tomorrow"),
            (r"(?:\s+)(?:today)$", "today"),
            (r"(?:\s+)(?:tomorrow)$", "tomorrow"),
        ):
            if re.search(pattern, title):
                title = re.sub(pattern, "", title).strip()
                due = due_value
                break
        return title, priority, due
