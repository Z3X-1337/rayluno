"""Central allowlist policy applied immediately before every side effect."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from .config import AssistantConfig
from .domain import Action, ActionKind, VolumeOperation


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    reason: str = ""


class SafetyPolicy:
    def __init__(self, config: AssistantConfig) -> None:
        self.config = config
        configured_schemes = {item.casefold() for item in config.allowed_schemes}
        self._schemes = configured_schemes & {"http", "https"}
        self._domains = {item.rstrip(".").casefold() for item in config.allowed_domains}
        self._apps = set(config.allowed_app_ids)

    def evaluate(self, action: Action) -> SafetyDecision:
        if action.kind is ActionKind.OPEN_URL:
            return self._url(action.parameters.get("url"))
        if action.kind is ActionKind.OPEN_APP:
            app_id = action.parameters.get("app_id")
            if not isinstance(app_id, str) or app_id not in self._apps:
                return SafetyDecision(False, "التطبيق غير موجود في قائمة السماح.")
            return SafetyDecision(True)
        if action.kind is ActionKind.REPORT_TIME:
            if action.parameters:
                return SafetyDecision(False, "أمر الوقت لا يقبل معاملات.")
            return SafetyDecision(True)
        if action.kind is ActionKind.CONTROL_VOLUME:
            operation = action.parameters.get("operation")
            steps = action.parameters.get("steps")
            if operation not in {item.value for item in VolumeOperation}:
                return SafetyDecision(False, "عملية الصوت غير مسموحة.")
            if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 10:
                return SafetyDecision(False, "درجة تغيير الصوت خارج النطاق الآمن.")
            return SafetyDecision(True)
        if action.kind is ActionKind.CREATE_TASK:
            title = action.parameters.get("title")
            priority = action.parameters.get("priority")
            due = action.parameters.get("due")
            if not isinstance(title, str) or not title.strip() or len(title) > 240:
                return SafetyDecision(False, "عنوان المهمة غير صالح.")
            if any(ord(character) < 32 for character in title):
                return SafetyDecision(False, "عنوان المهمة يحتوي على محارف غير آمنة.")
            if priority not in {"low", "normal", "high"}:
                return SafetyDecision(False, "أولوية المهمة غير صالحة.")
            if due not in {"none", "today", "tomorrow"}:
                if not isinstance(due, str) or len(due) != 10:
                    return SafetyDecision(False, "موعد المهمة غير صالح.")
                try:
                    date.fromisoformat(due)
                except ValueError:
                    return SafetyDecision(False, "موعد المهمة غير صالح.")
            return SafetyDecision(True)
        if action.kind is ActionKind.LIST_TASKS:
            include_completed = action.parameters.get("include_completed")
            limit = action.parameters.get("limit")
            if not isinstance(include_completed, bool):
                return SafetyDecision(False, "مرشح حالة المهام غير صالح.")
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
                return SafetyDecision(False, "عدد المهام المطلوب خارج النطاق الآمن.")
            return SafetyDecision(True)
        if action.kind in {ActionKind.COMPLETE_TASK, ActionKind.DELETE_TASK}:
            task_id = action.parameters.get("task_id")
            if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
                return SafetyDecision(False, "رقم المهمة غير صالح.")
            return SafetyDecision(True)
        return SafetyDecision(False, "نوع الإجراء غير مدعوم.")

    def _url(self, value) -> SafetyDecision:  # noqa: ANN001
        if not isinstance(value, str) or not value or len(value) > self.config.max_url_length:
            return SafetyDecision(False, "الرابط مفقود أو طويل جدا.")
        if any(ord(char) < 32 for char in value) or "\\" in value:
            return SafetyDecision(False, "الرابط يحتوي على محارف غير آمنة.")
        try:
            parts = urlsplit(value)
            port = parts.port
        except ValueError:
            return SafetyDecision(False, "صيغة الرابط غير صالحة.")
        scheme = parts.scheme.casefold()
        if scheme not in self._schemes:
            return SafetyDecision(False, "يُسمح فقط بروابط HTTP وHTTPS.")
        if parts.username is not None or parts.password is not None:
            return SafetyDecision(False, "بيانات الدخول داخل الرابط غير مسموحة.")
        if port is not None and port != (443 if scheme == "https" else 80):
            return SafetyDecision(False, "منفذ الرابط غير مسموح.")
        if not parts.hostname:
            return SafetyDecision(False, "اسم النطاق مفقود.")
        try:
            host = parts.hostname.rstrip(".").encode("idna").decode("ascii").casefold()
        except UnicodeError:
            return SafetyDecision(False, "اسم النطاق غير صالح.")
        if not any(host == domain or host.endswith(f".{domain}") for domain in self._domains):
            return SafetyDecision(False, "النطاق غير موجود في قائمة السماح.")
        return SafetyDecision(True)
