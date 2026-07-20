"""Safe construction of the small action vocabulary."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import AssistantConfig
from .domain import Action, ActionKind, VolumeOperation

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")


def normalize_text(value: str) -> str:
    value = _ARABIC_DIACRITICS.sub("", value).replace("ـ", "")
    value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return " ".join(value.casefold().strip().split())


class ActionFactory:
    def __init__(self, config: AssistantConfig) -> None:
        self.config = config
        self._sites = {normalize_text(key): url for key, url in config.sites.items()}
        self._apps = {normalize_text(key): app_id for key, app_id in config.apps.items()}

    def _clean_query(self, query: str) -> str | None:
        query = " ".join(query.strip(" \t\r\n،,.!؟?").split())
        if not query or len(query) > self.config.max_query_length:
            return None
        return query

    @staticmethod
    def _with_query(url: str, name: str, value: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query[name] = value
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    def web_search(self, query: str) -> Action | None:
        cleaned = self._clean_query(query)
        if cleaned is None:
            return None
        return Action(
            ActionKind.OPEN_URL,
            {"url": self._with_query(self.config.search_url, "q", cleaned), "purpose": "search"},
        )

    def youtube_search(self, query: str) -> Action | None:
        cleaned = self._clean_query(query)
        if cleaned is None:
            return None
        return Action(
            ActionKind.OPEN_URL,
            {
                "url": self._with_query(self.config.youtube_search_url, "search_query", cleaned),
                "purpose": "youtube_search",
            },
        )

    def youtube_media(self, query: str) -> Action | None:
        """Build a safe results URL that may be upgraded to a direct video at runtime."""
        cleaned = self._clean_query(query)
        if cleaned is None:
            return None
        return Action(
            ActionKind.OPEN_URL,
            {
                "url": self._with_query(
                    self.config.youtube_search_url,
                    "search_query",
                    cleaned,
                ),
                "purpose": "youtube_media",
                "media_query": cleaned,
            },
        )

    def open_site(self, alias: str) -> Action | None:
        url = self._sites.get(normalize_text(alias))
        if url is None:
            return None
        return Action(ActionKind.OPEN_URL, {"url": url, "purpose": "site"})

    def open_url(self, value: str) -> Action | None:
        value = value.strip().strip("،,.!؟?")
        if not value or any(char.isspace() for char in value):
            return None
        if "://" not in value:
            value = f"https://{value}"
        return Action(ActionKind.OPEN_URL, {"url": value, "purpose": "site"})

    def open_app(self, alias: str) -> Action | None:
        app_id = self._apps.get(normalize_text(alias))
        if app_id is None:
            return None
        return Action(ActionKind.OPEN_APP, {"app_id": app_id})

    def create_task(
        self,
        title: str,
        *,
        priority: str = "normal",
        due: str | None = None,
    ) -> Action | None:
        cleaned = self._clean_query(title)
        if cleaned is None or priority not in {"low", "normal", "high"}:
            return None
        if due not in {None, "none", "today", "tomorrow"} and not (
            isinstance(due, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", due)
        ):
            return None
        return Action(
            ActionKind.CREATE_TASK,
            {"title": cleaned, "priority": priority, "due": due or "none"},
        )

    @staticmethod
    def list_tasks(*, include_completed: bool = False, limit: int = 10) -> Action:
        return Action(
            ActionKind.LIST_TASKS,
            {"include_completed": include_completed, "limit": limit},
        )

    @staticmethod
    def complete_task(task_id: int) -> Action | None:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
            return None
        return Action(ActionKind.COMPLETE_TASK, {"task_id": task_id})

    @staticmethod
    def delete_task(task_id: int) -> Action | None:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
            return None
        return Action(ActionKind.DELETE_TASK, {"task_id": task_id})

    @staticmethod
    def report_time() -> Action:
        return Action(ActionKind.REPORT_TIME)

    @staticmethod
    def control_volume(operation: VolumeOperation, steps: int = 2) -> Action:
        return Action(
            ActionKind.CONTROL_VOLUME,
            {"operation": operation.value, "steps": steps},
        )
