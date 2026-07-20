from __future__ import annotations

import ast
import asyncio
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from future_assistant.automation import (
    APP_LAUNCH_MANIFEST,
    BROWSER_SEARCH_MANIFEST,
    AppLaunchExecutor,
    AutomationConfigurationError,
    AutomationEngine,
    BrowserSearchExecutor,
    CancellationToken,
    ConfirmationAuthority,
    ConfirmationIssueError,
    ConfirmationNotRequiredError,
    ExecutionStatus,
    ExecutorRegistry,
    Permission,
    ResultCode,
    SkillInvocation,
)


class FakeBrowserEffects:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.error: Exception | None = None

    async def open_url(self, url: str) -> None:
        if self.error is not None:
            raise self.error
        self.urls.append(url)


class BlockingBrowserEffects(FakeBrowserEffects):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.effect_cancelled = False

    async def open_url(self, url: str) -> None:
        self.urls.append(url)
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.effect_cancelled = True


class FakeAppEffects:
    def __init__(self) -> None:
        self.app_ids: list[str] = []

    async def launch_app(self, app_id: str) -> None:
        self.app_ids.append(app_id)


def _browser_engine(
    effects: FakeBrowserEffects,
    *,
    manifest=BROWSER_SEARCH_MANIFEST,  # noqa: ANN001
    allowed_permissions: set[Permission] | None = None,
) -> AutomationEngine:
    registry = ExecutorRegistry({BROWSER_SEARCH_MANIFEST.executor_id})
    registry.register(BrowserSearchExecutor(effects))
    return AutomationEngine(
        [manifest],
        registry,
        ConfirmationAuthority(),
        allowed_permissions=(
            {Permission.BROWSER_OPEN_URL} if allowed_permissions is None else allowed_permissions
        ),
    )


def _app_engine(effects: FakeAppEffects) -> AutomationEngine:
    registry = ExecutorRegistry({APP_LAUNCH_MANIFEST.executor_id})
    registry.register(AppLaunchExecutor(effects, allowed_app_ids={"calculator", "notepad"}))
    return AutomationEngine(
        [APP_LAUNCH_MANIFEST],
        registry,
        ConfirmationAuthority(),
        allowed_permissions={Permission.APP_LAUNCH},
    )


def test_browser_search_uses_encoded_fixed_https_effect() -> None:
    effects = FakeBrowserEffects()
    engine = _browser_engine(effects)
    invocation = SkillInvocation("browser.search", {"query": "  مساعد عربي & آمن  "})

    result = asyncio.run(engine.execute(invocation))

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.code is ResultCode.OK
    assert result.data == {"opened": True, "provider": "www.google.com"}
    parsed = urlsplit(effects.urls[0])
    assert parsed.scheme == "https"
    assert parsed.hostname == "www.google.com"
    assert parse_qs(parsed.query) == {"q": ["مساعد عربي & آمن"]}


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"query": ""},
        {"query": 12},
        {"query": "safe", "url": "https://evil.example"},
        {"query": "unsafe\x00query"},
    ],
)
def test_browser_search_blocks_invalid_or_hidden_arguments(arguments: dict[str, object]) -> None:
    effects = FakeBrowserEffects()
    engine = _browser_engine(effects)

    result = asyncio.run(engine.execute(SkillInvocation("browser.search", arguments)))

    assert result.status is ExecutionStatus.BLOCKED
    assert result.code is ResultCode.INVALID_ARGUMENTS
    assert effects.urls == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://www.google.com/search",
        "https://evil.example/search",
        "https://www.google.com@evil.example/search",
        "https://user:secret@www.google.com/search",
        "https://www.google.com:444/search",
        "https://www.google.com/search?next=evil",
    ],
)
def test_browser_executor_rejects_unsafe_provider_configuration(endpoint: str) -> None:
    with pytest.raises(AutomationConfigurationError):
        BrowserSearchExecutor(FakeBrowserEffects(), search_endpoint=endpoint)


def test_global_permission_policy_blocks_effect_even_when_manifest_is_registered() -> None:
    effects = FakeBrowserEffects()
    engine = _browser_engine(effects, allowed_permissions=set())

    result = asyncio.run(engine.execute(SkillInvocation("browser.search", {"query": "blocked"})))

    assert result.status is ExecutionStatus.BLOCKED
    assert result.code is ResultCode.PERMISSION_DENIED
    assert effects.urls == []


def test_unknown_skill_is_blocked_without_effect() -> None:
    effects = FakeBrowserEffects()
    engine = _browser_engine(effects)

    result = asyncio.run(engine.execute(SkillInvocation("missing.skill", {"query": "anything"})))

    assert result.code is ResultCode.UNKNOWN_SKILL
    assert effects.urls == []


def test_high_risk_app_launch_needs_exact_one_time_confirmation() -> None:
    effects = FakeAppEffects()
    engine = _app_engine(effects)
    invocation = SkillInvocation(
        "app.launch",
        {"app_id": "calculator"},
        actor_id="desktop-user",
        request_id="launch-1",
    )

    required = asyncio.run(engine.execute(invocation))
    grant = engine.request_confirmation(invocation, ttl_seconds=5)
    accepted = asyncio.run(engine.execute(invocation, confirmation_token=grant.token))
    replayed = asyncio.run(engine.execute(invocation, confirmation_token=grant.token))

    assert required.status is ExecutionStatus.CONFIRMATION_REQUIRED
    assert required.code is ResultCode.CONFIRMATION_REQUIRED
    assert accepted.status is ExecutionStatus.SUCCEEDED
    assert replayed.code is ResultCode.CONFIRMATION_INVALID
    assert effects.app_ids == ["calculator"]


def test_confirmation_for_one_app_cannot_authorize_another() -> None:
    effects = FakeAppEffects()
    engine = _app_engine(effects)
    calculator = SkillInvocation("app.launch", {"app_id": "calculator"}, request_id="same-request")
    notepad = SkillInvocation("app.launch", {"app_id": "notepad"}, request_id="same-request")
    grant = engine.request_confirmation(calculator)

    result = asyncio.run(engine.execute(notepad, confirmation_token=grant.token))

    assert result.code is ResultCode.CONFIRMATION_MISMATCH
    assert effects.app_ids == []


def test_disallowed_app_is_rejected_before_confirmation_can_be_issued() -> None:
    effects = FakeAppEffects()
    engine = _app_engine(effects)
    invocation = SkillInvocation("app.launch", {"app_id": "powershell"})

    result = asyncio.run(engine.execute(invocation))

    assert result.code is ResultCode.INVALID_ARGUMENTS
    with pytest.raises(ConfirmationIssueError, match="invalid_arguments"):
        engine.request_confirmation(invocation)
    assert effects.app_ids == []


def test_low_risk_skill_does_not_mint_unnecessary_confirmation() -> None:
    engine = _browser_engine(FakeBrowserEffects())

    with pytest.raises(ConfirmationNotRequiredError):
        engine.request_confirmation(SkillInvocation("browser.search", {"query": "safe"}))


def test_pre_cancelled_execution_never_reaches_effect() -> None:
    effects = FakeBrowserEffects()
    engine = _browser_engine(effects)
    cancellation = CancellationToken()
    cancellation.cancel()

    result = asyncio.run(
        engine.execute(
            SkillInvocation("browser.search", {"query": "cancelled"}),
            cancellation=cancellation,
        )
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert effects.urls == []


def test_running_execution_can_be_cancelled_cooperatively() -> None:
    async def scenario() -> tuple[object, BlockingBrowserEffects]:
        effects = BlockingBrowserEffects()
        engine = _browser_engine(effects)
        cancellation = CancellationToken()
        task = asyncio.create_task(
            engine.execute(
                SkillInvocation("browser.search", {"query": "cancel me"}),
                cancellation=cancellation,
            )
        )
        await effects.started.wait()
        cancellation.cancel()
        return await task, effects

    result, effects = asyncio.run(scenario())

    assert result.status is ExecutionStatus.CANCELLED
    assert effects.effect_cancelled


def test_manifest_timeout_cancels_executor_and_returns_bounded_result() -> None:
    effects = BlockingBrowserEffects()
    manifest = replace(BROWSER_SEARCH_MANIFEST, timeout_seconds=0.02)
    engine = _browser_engine(effects, manifest=manifest)

    result = asyncio.run(engine.execute(SkillInvocation("browser.search", {"query": "wait"})))

    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.code is ResultCode.TIMED_OUT
    assert effects.effect_cancelled


def test_executor_exception_is_sanitized_at_engine_boundary() -> None:
    effects = FakeBrowserEffects()
    effects.error = RuntimeError("secret internal browser failure")
    engine = _browser_engine(effects)

    result = asyncio.run(engine.execute(SkillInvocation("browser.search", {"query": "test"})))

    assert result.status is ExecutionStatus.FAILED
    assert result.code is ResultCode.EXECUTOR_FAILED
    assert "secret" not in result.detail


def test_automation_package_contains_no_raw_shell_execution_primitive() -> None:
    package = Path(__file__).parents[1] / "src" / "future_assistant" / "automation"
    banned_imports = {"subprocess", "os", "shlex"}
    banned_names = {"eval", "exec", "compile"}
    banned_attributes = {"system", "popen"}

    for source_file in package.glob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not ({alias.name.split(".")[0] for alias in node.names} & banned_imports)
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned_imports
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id.casefold() not in banned_names
                elif isinstance(node.func, ast.Attribute):
                    assert node.func.attr.casefold() not in banned_attributes
