"""Fast deterministic routing for common Arabic commands."""

from __future__ import annotations

import re

from .actions import ActionFactory, normalize_text
from .domain import Plan, PlanSource, VolumeOperation


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

    def __init__(self, actions: ActionFactory) -> None:
        self.actions = actions

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

        tasks = self._route_tasks(normalized)
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

    def _route_tasks(self, normalized: str) -> Plan | None:
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
            return self._plan(self.actions.list_tasks())

        if normalized in {
            "اعرض كل المهام",
            "اعرض المهام المكتملة",
            "سجل المهام",
            "show all tasks",
            "show completed tasks",
            "task history",
        }:
            return self._plan(self.actions.list_tasks(include_completed=True))

        complete_patterns = (
            r"^(?:انجز|اكمل|انهي|اتمم)(?: المهمه| المهمة)?\s+(?:رقم\s+)?(\d+)$",
            r"^(?:complete|finish|done with|mark)(?: task)?\s+(\d+)(?: as done| complete)?$",
            r"^mark task\s+(\d+)\s+(?:done|complete)$",
        )
        for pattern in complete_patterns:
            match = re.match(pattern, normalized)
            if match:
                action = self.actions.complete_task(int(match.group(1)))
                return self._plan(action) if action else None

        delete_patterns = (
            r"^(?:احذف|امسح|الغ)(?: المهمه| المهمة)?\s+(?:رقم\s+)?(\d+)$",
            r"^(?:delete|remove|cancel)(?: task)?\s+(\d+)$",
        )
        for pattern in delete_patterns:
            match = re.match(pattern, normalized)
            if match:
                action = self.actions.delete_task(int(match.group(1)))
                return self._plan(action) if action else None

        create_patterns = (
            r"^(?:اضف|ضيف|سجل|دون)(?: لي)?(?: مهمه| مهمة)?\s+(.+)$",
            r"^(?:ذكرني)(?: ان| ب)?\s+(.+)$",
            r"^(?:add|create)(?: a)? task(?: to)?\s+(.+)$",
            r"^remind me to\s+(.+)$",
        )
        for pattern in create_patterns:
            match = re.match(pattern, normalized)
            if not match:
                continue
            title, priority, due = self._task_metadata(match.group(1))
            action = self.actions.create_task(title, priority=priority, due=due)
            return self._plan(action) if action else None
        return None

    @staticmethod
    def _task_metadata(value: str) -> tuple[str, str, str | None]:
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

        due_patterns = (
            (r"(?:\s+)(?:اليوم|لهذا اليوم)$", "today"),
            (r"(?:\s+)(?:غدا|بكرا|للغد)$", "tomorrow"),
            (r"(?:\s+)(?:today)$", "today"),
            (r"(?:\s+)(?:tomorrow)$", "tomorrow"),
        )
        for pattern, value_due in due_patterns:
            if re.search(pattern, title):
                title = re.sub(pattern, "", title).strip()
                due = value_due
                break
        return title, priority, due

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
