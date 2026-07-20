from datetime import datetime

from future_assistant.audit import MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import (
    Action,
    ActionKind,
    Plan,
    RuntimeStatus,
    VolumeOperation,
)
from future_assistant.media import YouTubeMediaResolver
from future_assistant.runtime import AssistantRuntime, SystemEffects, build_runtime


class FakeEffects:
    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []
        self.now = datetime(2026, 7, 11, 9, 5)
        self.fail = False

    def open_url(self, url: str) -> None:
        if self.fail:
            raise RuntimeError("browser unavailable")
        self.operations.append(("open_url", url))

    def open_app(self, app_id: str) -> None:
        self.operations.append(("open_app", app_id))

    def current_time(self) -> datetime:
        self.operations.append(("current_time",))
        return self.now

    def control_volume(self, operation: VolumeOperation, steps: int) -> None:
        self.operations.append(("control_volume", operation.value, steps))


class FixedPlanner:
    def __init__(self, plan: Plan | None) -> None:
        self.result = plan

    def plan(self, command: str) -> Plan | None:
        return self.result


def _runtime(
    effects: FakeEffects,
    audit: MemoryAuditLogger | None = None,
    media_resolver=None,  # noqa: ANN001
) -> AssistantRuntime:
    config = AssistantConfig(audit_path=None)
    return build_runtime(
        config,
        effects=effects,
        audit=audit or MemoryAuditLogger(),
        media_resolver=media_resolver,
    )


def test_ignores_commands_without_wake_word() -> None:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    runtime = _runtime(effects, audit)

    result = runtime.handle("افتح يوتيوب")

    assert result.status is RuntimeStatus.SLEEPING
    assert result.message == ""
    assert effects.operations == []
    assert audit.records == []


def test_wake_word_alone_acknowledges_without_action() -> None:
    runtime = _runtime(FakeEffects())

    result = runtime.handle("يا رايلونو،")

    assert result.status is RuntimeStatus.AWAKE
    assert result.message == "نعم، أنا معك."


def test_executes_arabic_search_and_audits_hash_only() -> None:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    runtime = _runtime(effects, audit)

    result = runtime.handle("رايلونو، ابحث عن وصفة سرية جدا")

    assert result.status is RuntimeStatus.COMPLETED
    assert result.message == "فتحت نتائج البحث."
    assert effects.operations[0][0] == "open_url"
    assert [record.event for record in audit.records] == ["command_received", "action_executed"]
    assert all(record.command_hash for record in audit.records)
    assert all("وصفة" not in repr(record) for record in audit.records)


def test_reports_injected_time() -> None:
    effects = FakeEffects()
    runtime = _runtime(effects)

    result = runtime.handle("يا رايلونو كم الساعة")

    assert result.status is RuntimeStatus.COMPLETED
    assert result.message == "الوقت الآن 09:05."
    assert effects.operations == [("current_time",)]


def test_safety_rechecks_planner_output_before_effect() -> None:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    malicious = Plan(actions=(Action(ActionKind.OPEN_URL, {"url": "file:///secret"}),))
    runtime = AssistantRuntime(
        AssistantConfig(audit_path=None),
        FixedPlanner(malicious),
        effects,
        audit,
    )

    result = runtime.handle("رايلونو نفذ الخطة")

    assert result.status is RuntimeStatus.BLOCKED
    assert effects.operations == []
    assert audit.records[-1].event == "action_blocked"


def test_effect_failure_becomes_runtime_error() -> None:
    effects = FakeEffects()
    effects.fail = True
    runtime = _runtime(effects)

    result = runtime.handle("رايلونو افتح يوتيوب")

    assert result.status is RuntimeStatus.ERROR
    assert result.message == "تعذر تنفيذ الأمر."


def test_wake_word_can_be_disabled_for_integrations() -> None:
    effects = FakeEffects()
    config = AssistantConfig(require_wake_word=False, audit_path=None)
    runtime = build_runtime(config, effects=effects, audit=MemoryAuditLogger())

    result = runtime.handle("ارفع الصوت")

    assert result.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("control_volume", "up", 2)]


def test_system_effects_uses_fixed_command_without_shell() -> None:
    calls: list[tuple[object, ...]] = []

    def launcher(command, **kwargs):  # noqa: ANN001, ANN003
        calls.append((command, kwargs))
        return object()

    effects = SystemEffects(
        process_launcher=launcher,
        app_commands={"calculator": ("safe-calculator", "--new")},
    )

    effects.open_app("calculator")

    command, kwargs = calls[0]
    assert command == ["safe-calculator", "--new"]
    assert kwargs["shell"] is False


def test_executes_english_command_and_replies_in_english() -> None:
    effects = FakeEffects()
    runtime = _runtime(effects)

    result = runtime.handle("Hey Rayluno, open calculator")

    assert result.status is RuntimeStatus.COMPLETED
    assert result.message == "I opened the app."
    assert effects.operations == [("open_app", "calculator")]


def test_reports_time_in_english() -> None:
    effects = FakeEffects()
    runtime = _runtime(effects)

    result = runtime.handle("Rayluno, what time is it?")

    assert result.status is RuntimeStatus.COMPLETED
    assert result.message == "The time is 09:05."


class StubYouTubeTransport:
    def __init__(self, video_id: str | None) -> None:
        self.video_id = video_id
        self.keys: list[str] = []

    def first_video_id(self, query: str, api_key: str, timeout: float) -> str | None:
        self.keys.append(api_key)
        return self.video_id


def test_media_command_opens_first_official_api_result_without_key_leak() -> None:
    effects = FakeEffects()
    audit = MemoryAuditLogger()
    transport = StubYouTubeTransport("dQw4w9WgXcQ")
    resolver = YouTubeMediaResolver("secret-byok-key", transport=transport)
    runtime = _runtime(effects, audit, resolver)

    result = runtime.handle("Hey Rayluno, play a song Never Gonna Give You Up")

    assert result.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("open_url", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")]
    assert transport.keys == ["secret-byok-key"]
    assert "secret-byok-key" not in repr(result)
    assert "secret-byok-key" not in repr(audit.records)


def test_direct_media_playback_requires_pro_when_commercial_gate_is_present() -> None:
    effects = FakeEffects()
    config = AssistantConfig(audit_path=None)
    runtime = build_runtime(
        config,
        effects=effects,
        audit=MemoryAuditLogger(),
        feature_checker=lambda feature: feature != "automation.pro",
    )

    result = runtime.handle("Hey Rayluno, play a song Bohemian Rhapsody")

    assert result.status is RuntimeStatus.BLOCKED
    assert result.message == "This feature requires an active Pro license."
    assert effects.operations == []


class UnsafeMediaResolver:
    def youtube_url(self, query: str, fallback_url: str) -> str:
        return "https://attacker.example/video"


def test_media_resolution_is_rechecked_by_domain_allowlist() -> None:
    effects = FakeEffects()
    runtime = _runtime(effects, media_resolver=UnsafeMediaResolver())

    result = runtime.handle("يا رايلونو شغل أغنية نسم علينا الهوى")

    assert result.status is RuntimeStatus.BLOCKED
    assert effects.operations == []
