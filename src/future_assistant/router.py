"""Fast deterministic routing for common Arabic commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from .actions import ActionFactory, normalize_text
from .agenda_commands import AgendaCommandPlanner
from .domain import Plan, PlanSource, VolumeOperation
from .reminders import AgendaService, ReminderService, SQLiteReminderStore
from .task_commands import TaskCommandPlanner
from .tasks import SQLiteTaskStore, TaskService


class DeterministicRouter:
    """Routes high-frequency Arabic and English commands without a model round-trip."""

    _time_phrases = {
        "الوقت",
        "الوقت الان",
        "كم الساعة",
        "كم الساعه",
        "كم الساعة الان",
        "كم الساعه الان",
        "ما الوقت",
        "ما هو الوقت",
        "الساعة كم",
        "الساعه كم",
        "time",
        "the time",
        "what time is it",
        "what's the time",
        "tell me the time",
        "current time",
    }

    def __init__(
        self,
        actions: ActionFactory,
        task_service: TaskService | None = None,
        reminder_service: ReminderService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.actions = actions
        service = task_service or TaskService(SQLiteTaskStore(actions.config.tasks_path), clock=clock)
        reminders = reminder_service or ReminderService(
            SQLiteReminderStore(actions.config.reminders_path), clock=clock
        )
        self.agenda_commands = AgendaCommandPlanner(
            reminders, AgendaService(service, reminders, clock=clock)
        )
        self.task_commands = TaskCommandPlanner(service)

    @staticmethod
    def _plan(action, reply: str | None = None) -> Plan:  # noqa: ANN001
        return Plan(actions=(action,), reply=reply, source=PlanSource.DETERMINISTIC)

    def route(self, command: str) -> Plan | None:
        normalized = normalize_text(command).strip("،,.!؟? ")
        if not normalized:
            return None

        if normalized in self._time_phrases:
            return self._plan(self.actions.report_time())

        volume = self._route_volume(normalized)
        if volume is not None:
            return volume

        agenda = self.agenda_commands.plan(normalized, command)
        if agenda is not None:
            return agenda

        tasks = self.task_commands.plan(normalized, command)
        if tasks is not None:
            return tasks

        youtube = self._route_youtube(normalized)
        if youtube is not None:
            return youtube

        search = re.match(
            r"^(?:(?:ابحث(?: لي)?|دور|دور لي|فتش)(?: عن| علي)?|"
            r"(?:search|look up|find)(?: for)?)\s+(.+)$",
            normalized,
        )
        if search:
            action = self.actions.web_search(search.group(1))
            return self._plan(action) if action else None

        target_match = re.match(
            r"^(?:(?:افتح|شغل)(?: لي)?(?: موقع| تطبيق| برنامج)?|"
            r"(?:open|launch|start)(?: the)?(?: website| site| app| application)?)\s+(.+)$",
            normalized,
        )
        if target_match:
            target = target_match.group(1).strip()
            app_action = self.actions.open_app(target)
            if app_action is not None:
                return self._plan(app_action)
            site_action = self.actions.open_site(target)
            if site_action is not None:
                return self._plan(site_action)
            if "." in target and " " not in target:
                url_action = self.actions.open_url(target)
                return self._plan(url_action) if url_action else None

        song = re.match(
            r"^(?:(?:شغل|شغلي|شغل لي)\s+"
            r"(?:اغنيه|اغنية|انشوده|انشودة|موسيقي|فيديو|مقطع)?|"
            r"(?:play)(?: the)?(?: song| music| video| clip)?)\s+(.+)$",
            normalized,
        )
        if song:
            action = self.actions.youtube_media(song.group(1))
            return self._plan(action) if action else None

        return None

    def _route_volume(self, normalized: str) -> Plan | None:
        if any(
            phrase in normalized
            for phrase in (
                "ارفع الصوت",
                "علي الصوت",
                "زيد الصوت",
                "صوت اعلي",
                "volume up",
                "raise the volume",
                "increase the volume",
                "turn the volume up",
            )
        ):
            return self._plan(self.actions.control_volume(VolumeOperation.UP))
        if any(
            phrase in normalized
            for phrase in (
                "اخفض الصوت",
                "وطي الصوت",
                "قلل الصوت",
                "صوت اوطي",
                "volume down",
                "lower the volume",
                "decrease the volume",
                "turn the volume down",
            )
        ):
            return self._plan(self.actions.control_volume(VolumeOperation.DOWN))
        if any(
            phrase in normalized
            for phrase in (
                "اكتم الصوت",
                "الغ كتم الصوت",
                "بدل كتم الصوت",
                "mute",
                "mute the sound",
                "mute the volume",
                "toggle mute",
                "unmute",
            )
        ):
            return self._plan(self.actions.control_volume(VolumeOperation.TOGGLE_MUTE, steps=1))
        return None

    def _route_youtube(self, normalized: str) -> Plan | None:
        if normalized in {
            "افتح يوتيوب",
            "شغل يوتيوب",
            "افتح موقع يوتيوب",
            "open youtube",
            "launch youtube",
            "start youtube",
        }:
            action = self.actions.open_site("يوتيوب")
            return self._plan(action) if action else None

        search_patterns = (
            r"^(?:ابحث|دور|فتش)(?: لي)?\s+(?:في|علي)\s+يوتيوب(?:\s+عن)?\s+(.+)$",
            r"^(?:search|find|look up)\s+(.+?)\s+(?:on|in)\s+youtube$",
            r"^(?:search\s+)?youtube\s+(?:for\s+)?(.+)$",
            r"^يوتيوب\s+(.+)$",
        )
        for pattern in search_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            action = self.actions.youtube_search(match.group(1))
            return self._plan(action) if action else None

        media_patterns = (
            r"^(?:افتح|شغل)\s+يوتيوب\s+(?:علي\s+)?(.+)$",
            r"^(?:افتح|شغل)\s+(.+?)\s+(?:علي|في)\s+يوتيوب$",
            r"^(?:افتح|شغل)(?: لي)?\s+(?:فيديو|مقطع|اغنيه|اغنية|انشوده|انشودة)\s+(.+)$",
            r"^(?:open|play)\s+(?:youtube\s+)?(?:for\s+)?(.+?)\s+(?:on|in)\s+youtube$",
            r"^(?:open|play)\s+youtube\s+(?:for\s+)?(.+)$",
            r"^(?:play|open)\s+(?:(?:a|the)\s+)?(?:video|song|track|clip)\s+(.+)$",
        )
        for pattern in media_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            query = re.sub(
                r"^(?:فيديو|مقطع|اغنيه|اغنية|انشوده|انشودة|video|song|track|clip)\s+",
                "",
                match.group(1),
            )
            action = self.actions.youtube_media(query)
            return self._plan(action) if action else None
        return None
