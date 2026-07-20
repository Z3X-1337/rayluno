"""Wake-word gate, policy enforcement, and injectable system effects."""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .actions import ActionFactory
from .audit import AuditLogger, JsonlAuditLogger, NullAuditLogger
from .config import AssistantConfig
from .domain import (
    Action,
    ActionKind,
    ExecutionResult,
    RuntimeResult,
    RuntimeStatus,
    VolumeOperation,
)
from .localization import Language, MessageKey, localize, resolve_language
from .media import MediaResolver, YouTubeMediaResolver
from .planner import HybridPlanner, OllamaPlanner, Planner, RouterPlanner
from .router import DeterministicRouter
from .safety import SafetyPolicy


class Effects(Protocol):
    def open_url(self, url: str) -> None: ...

    def open_app(self, app_id: str) -> None: ...

    def current_time(self) -> datetime: ...

    def control_volume(self, operation: VolumeOperation, steps: int) -> None: ...


def _default_app_commands() -> dict[str, tuple[str, ...]]:
    if sys.platform == "win32":
        return {
            "calculator": ("calc.exe",),
            "notepad": ("notepad.exe",),
            "file_manager": ("explorer.exe",),
            "paint": ("mspaint.exe",),
        }
    if sys.platform == "darwin":
        return {
            "calculator": ("open", "-a", "Calculator"),
            "notepad": ("open", "-a", "TextEdit"),
            "file_manager": ("open", "."),
            "paint": ("open", "-a", "Preview"),
        }
    return {
        "calculator": ("gnome-calculator",),
        "notepad": ("gedit",),
        "file_manager": ("xdg-open", "."),
        "paint": ("pinta",),
    }


class SystemEffects:
    """Concrete effects; every external primitive can be replaced in tests."""

    def __init__(
        self,
        *,
        url_opener: Callable[[str], bool] = webbrowser.open_new_tab,
        process_launcher: Callable[..., object] = subprocess.Popen,
        command_runner: Callable[..., object] = subprocess.run,
        clock: Callable[[], datetime] = datetime.now,
        app_commands: Mapping[str, Sequence[str]] | None = None,
        volume_controller: Callable[[VolumeOperation, int], None] | None = None,
    ) -> None:
        self._url_opener = url_opener
        self._process_launcher = process_launcher
        self._command_runner = command_runner
        self._clock = clock
        self._app_commands = dict(app_commands or _default_app_commands())
        self._volume_controller = volume_controller

    def open_url(self, url: str) -> None:
        if not self._url_opener(url):
            raise RuntimeError("لم يقبل المتصفح فتح الرابط.")

    def open_app(self, app_id: str) -> None:
        command = self._app_commands.get(app_id)
        if command is None:
            raise RuntimeError("لا يوجد مشغّل لهذا التطبيق على النظام الحالي.")
        self._process_launcher(
            list(command),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def current_time(self) -> datetime:
        return self._clock()

    def control_volume(self, operation: VolumeOperation, steps: int) -> None:
        if self._volume_controller is not None:
            self._volume_controller(operation, steps)
            return
        if sys.platform == "win32":
            self._windows_volume(operation, steps)
        elif sys.platform == "darwin":
            self._mac_volume(operation, steps)
        else:
            self._linux_volume(operation, steps)

    @staticmethod
    def _windows_volume(operation: VolumeOperation, steps: int) -> None:
        virtual_keys = {
            VolumeOperation.TOGGLE_MUTE: 0xAD,
            VolumeOperation.DOWN: 0xAE,
            VolumeOperation.UP: 0xAF,
        }
        key = virtual_keys[operation]
        repeat = 1 if operation is VolumeOperation.TOGGLE_MUTE else steps
        for _ in range(repeat):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)  # type: ignore[attr-defined]
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)  # type: ignore[attr-defined]

    def _linux_volume(self, operation: VolumeOperation, steps: int) -> None:
        if operation is VolumeOperation.TOGGLE_MUTE:
            command = ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]
        else:
            sign = "+" if operation is VolumeOperation.UP else "-"
            command = [
                "pactl",
                "set-sink-volume",
                "@DEFAULT_SINK@",
                f"{sign}{steps * 5}%",
            ]
        self._command_runner(command, check=True, capture_output=True)

    def _mac_volume(self, operation: VolumeOperation, steps: int) -> None:
        if operation is VolumeOperation.TOGGLE_MUTE:
            script = "set volume output muted not (output muted of (get volume settings))"
        else:
            delta = steps * 5 * (1 if operation is VolumeOperation.UP else -1)
            script = (
                "set v to output volume of (get volume settings)\n"
                f"set volume output volume (v + ({delta}))"
            )
        self._command_runner(["osascript", "-e", script], check=True, capture_output=True)


class DryRunEffects:
    def __init__(self, clock: Callable[[], datetime] = datetime.now) -> None:
        self.operations: list[tuple[object, ...]] = []
        self._clock = clock

    def open_url(self, url: str) -> None:
        self.operations.append(("open_url", url))

    def open_app(self, app_id: str) -> None:
        self.operations.append(("open_app", app_id))

    def current_time(self) -> datetime:
        self.operations.append(("current_time",))
        return self._clock()

    def control_volume(self, operation: VolumeOperation, steps: int) -> None:
        self.operations.append(("control_volume", operation.value, steps))


class WakeWordMatcher:
    def __init__(self, wake_words: Sequence[str]) -> None:
        words = sorted({word.strip() for word in wake_words if word.strip()}, key=len, reverse=True)
        self._patterns: list[re.Pattern[str]] = []
        for word in words:
            flexible_word = r"\s+".join(re.escape(part) for part in word.split())
            self._patterns.append(
                re.compile(
                    rf"^\s*{flexible_word}" r"\s*[,،:;\-]?\s*(.*)$",
                    re.IGNORECASE,
                )
            )

    def extract(self, text: str) -> str | None:
        for pattern in self._patterns:
            match = pattern.match(text)
            if match:
                return match.group(1).strip()
        return None


class ActionExecutor:
    def __init__(
        self,
        effects: Effects,
        safety: SafetyPolicy,
        audit: AuditLogger,
        media_resolver: MediaResolver | None = None,
        feature_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self.effects = effects
        self.safety = safety
        self.audit = audit
        self.media_resolver = media_resolver or YouTubeMediaResolver.from_env()
        self.feature_checker = feature_checker

    def execute(
        self,
        action: Action,
        command: str,
        language: Language = Language.AR,
    ) -> ExecutionResult:
        required_feature = self._required_feature(action)
        if required_feature is not None and not self._feature_allowed(required_feature):
            self.audit.record(
                "action_blocked",
                command=command,
                action=action,
                detail=f"feature:{required_feature}",
            )
            return ExecutionResult(
                action,
                False,
                localize(MessageKey.PRO_FEATURE_REQUIRED, language),
                blocked=True,
            )
        decision = self.safety.evaluate(action)
        if not decision.allowed:
            self.audit.record(
                "action_blocked", command=command, action=action, detail=decision.reason
            )
            return ExecutionResult(
                action,
                False,
                localize(MessageKey.SAFETY_REFUSAL, language),
                blocked=True,
            )
        try:
            executable_action = self._resolve_media(action)
            resolved_decision = self.safety.evaluate(executable_action)
            if not resolved_decision.allowed:
                self.audit.record(
                    "action_blocked",
                    command=command,
                    action=executable_action,
                    detail=resolved_decision.reason,
                )
                return ExecutionResult(
                    executable_action,
                    False,
                    localize(MessageKey.SAFETY_REFUSAL, language),
                    blocked=True,
                )
            message = self._perform(executable_action, language)
        except Exception as exc:  # defensive boundary around injected operating-system effects
            self.audit.record(
                "action_failed", command=command, action=action, detail=type(exc).__name__
            )
            return ExecutionResult(
                action,
                False,
                localize(MessageKey.EXECUTION_ERROR, language),
                error=str(exc),
            )
        self.audit.record("action_executed", command=command, action=executable_action)
        return ExecutionResult(executable_action, True, message)

    @staticmethod
    def _required_feature(action: Action) -> str | None:
        if (
            action.kind is ActionKind.OPEN_URL
            and action.parameters.get("purpose") == "youtube_media"
        ):
            return "automation.pro"
        return None

    def _feature_allowed(self, feature: str) -> bool:
        if self.feature_checker is None:
            return True
        try:
            return bool(self.feature_checker(feature))
        except Exception:
            return False

    def _resolve_media(self, action: Action) -> Action:
        if action.kind is not ActionKind.OPEN_URL:
            return action
        if action.parameters.get("purpose") != "youtube_media":
            return action
        query = action.parameters.get("media_query")
        fallback_url = action.parameters.get("url")
        if not isinstance(query, str) or not isinstance(fallback_url, str):
            return action
        try:
            resolved_url = self.media_resolver.youtube_url(query, fallback_url)
        except Exception:  # Resolver boundary: a lookup outage must still open search results.
            resolved_url = fallback_url
        if not isinstance(resolved_url, str):
            resolved_url = fallback_url
        parameters = dict(action.parameters)
        parameters["url"] = resolved_url
        parameters.pop("media_query", None)
        return Action(ActionKind.OPEN_URL, parameters)

    def _perform(self, action: Action, language: Language) -> str:
        if action.kind is ActionKind.OPEN_URL:
            self.effects.open_url(str(action.parameters["url"]))
            purpose = action.parameters.get("purpose")
            if purpose in {"youtube_search", "youtube_media"}:
                return localize(MessageKey.OPENED_YOUTUBE, language)
            if purpose == "search":
                return localize(MessageKey.OPENED_SEARCH, language)
            return localize(MessageKey.OPENED_SITE, language)
        if action.kind is ActionKind.OPEN_APP:
            self.effects.open_app(str(action.parameters["app_id"]))
            return localize(MessageKey.OPENED_APP, language)
        if action.kind is ActionKind.REPORT_TIME:
            now = self.effects.current_time()
            return localize(MessageKey.TIME_NOW, language).format(time=f"{now:%H:%M}")
        if action.kind is ActionKind.CONTROL_VOLUME:
            operation = VolumeOperation(str(action.parameters["operation"]))
            self.effects.control_volume(operation, int(action.parameters["steps"]))
            messages = {
                VolumeOperation.UP: MessageKey.VOLUME_UP,
                VolumeOperation.DOWN: MessageKey.VOLUME_DOWN,
                VolumeOperation.TOGGLE_MUTE: MessageKey.VOLUME_MUTE,
            }
            return localize(messages[operation], language)
        raise RuntimeError("إجراء غير مدعوم.")


class AssistantRuntime:
    def __init__(
        self,
        config: AssistantConfig,
        planner: Planner,
        effects: Effects,
        audit: AuditLogger | None = None,
        media_resolver: MediaResolver | None = None,
        feature_checker: Callable[[str], bool] | None = None,
    ) -> None:
        self.config = config
        self.planner = planner
        self.audit = audit or NullAuditLogger()
        self.wake_words = WakeWordMatcher(config.wake_words)
        self.executor = ActionExecutor(
            effects,
            SafetyPolicy(config),
            self.audit,
            media_resolver,
            feature_checker,
        )

    def handle(self, text: str) -> RuntimeResult:
        text = text.strip()
        language = resolve_language(self.config.language, text=text)
        if not text:
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.EMPTY_INPUT, language),
            )

        command = text
        if self.config.require_wake_word:
            extracted = self.wake_words.extract(text)
            if extracted is None:
                return RuntimeResult(RuntimeStatus.SLEEPING)
            command = extracted
        if not command:
            self.audit.record("wake_word_detected", command=text)
            return RuntimeResult(RuntimeStatus.AWAKE, localize(MessageKey.AWAKE, language))

        self.audit.record("command_received", command=command)
        try:
            plan = self.planner.plan(command)
        except Exception as exc:  # defensive boundary around third-party planners
            self.audit.record("planning_failed", command=command, detail=type(exc).__name__)
            return RuntimeResult(
                RuntimeStatus.ERROR,
                localize(MessageKey.UNDERSTANDING_ERROR, language),
            )
        if plan is None:
            self.audit.record("command_unhandled", command=command)
            return RuntimeResult(
                RuntimeStatus.UNHANDLED,
                localize(MessageKey.UNHANDLED, language),
            )
        if not plan.actions:
            message = plan.reply or localize(MessageKey.UNHANDLED, language)
            return RuntimeResult(RuntimeStatus.COMPLETED, message, plan)

        executions = tuple(
            self.executor.execute(action, command, language) for action in plan.actions
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
        return RuntimeResult(status, message, plan, executions)


def build_runtime(
    config: AssistantConfig | None = None,
    *,
    effects: Effects | None = None,
    audit: AuditLogger | None = None,
    ollama_client=None,  # noqa: ANN001
    media_resolver: MediaResolver | None = None,
    feature_checker: Callable[[str], bool] | None = None,
) -> AssistantRuntime:
    config = config or AssistantConfig.from_env()
    actions = ActionFactory(config)
    deterministic = RouterPlanner(DeterministicRouter(actions))
    fallback = OllamaPlanner(ollama_client, actions) if ollama_client is not None else None
    fallback_enabled = (
        (lambda: bool(feature_checker("ai.local"))) if feature_checker is not None else None
    )
    planner = HybridPlanner(
        deterministic,
        fallback,
        fallback_enabled=fallback_enabled,
    )
    if audit is None:
        audit = (
            JsonlAuditLogger(Path(config.audit_path)) if config.audit_path else NullAuditLogger()
        )
    return AssistantRuntime(
        config,
        planner,
        effects or SystemEffects(),
        audit,
        media_resolver,
        feature_checker,
    )


def without_wake_word(config: AssistantConfig) -> AssistantConfig:
    return replace(config, require_wake_word=False)
