import pytest

from future_assistant.config import AssistantConfig
from future_assistant.domain import Action, ActionKind
from future_assistant.safety import SafetyPolicy


@pytest.fixture
def policy() -> SafetyPolicy:
    return SafetyPolicy(AssistantConfig(audit_path=None))


@pytest.mark.parametrize(
    "url",
    [
        "https://google.com/search?q=test",
        "https://www.youtube.com/results?search_query=test",
        "http://github.com/",
        "https://ar.wikipedia.org/wiki/Python",
    ],
)
def test_allows_http_urls_on_allowlisted_domains(policy: SafetyPolicy, url: str) -> None:
    action = Action(ActionKind.OPEN_URL, {"url": url})

    assert policy.evaluate(action).allowed


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://google.com.evil.example/",
        "https://evil.example/?next=https://google.com",
        "https://google.com@evil.example/",
        "https://user:secret@google.com/",
        "https://google.com:444/",
        "https://google.com\\@evil.example/",
        "https://exa mple.com/",
    ],
)
def test_blocks_unsafe_urls(policy: SafetyPolicy, url: str) -> None:
    action = Action(ActionKind.OPEN_URL, {"url": url})

    assert not policy.evaluate(action).allowed


def test_configuration_cannot_enable_non_http_scheme() -> None:
    config = AssistantConfig(allowed_schemes=("file", "https"), audit_path=None)
    policy = SafetyPolicy(config)

    decision = policy.evaluate(Action(ActionKind.OPEN_URL, {"url": "file:///tmp/data"}))

    assert not decision.allowed


def test_app_id_must_be_allowlisted(policy: SafetyPolicy) -> None:
    allowed = Action(ActionKind.OPEN_APP, {"app_id": "calculator"})
    arbitrary = Action(ActionKind.OPEN_APP, {"app_id": "powershell -enc payload"})

    assert policy.evaluate(allowed).allowed
    assert not policy.evaluate(arbitrary).allowed


@pytest.mark.parametrize("steps", [0, 11, -1, True, "2"])
def test_volume_steps_are_bounded(policy: SafetyPolicy, steps: object) -> None:
    action = Action(
        ActionKind.CONTROL_VOLUME,
        {"operation": "up", "steps": steps},
    )

    assert not policy.evaluate(action).allowed


def test_time_action_rejects_hidden_parameters(policy: SafetyPolicy) -> None:
    assert policy.evaluate(Action(ActionKind.REPORT_TIME)).allowed
    assert not policy.evaluate(Action(ActionKind.REPORT_TIME, {"command": "whoami"})).allowed
