from __future__ import annotations

from future_assistant.actions import ActionFactory, normalize_text
from future_assistant.command_understanding import resolve_allowlisted_alias
from future_assistant.config import AssistantConfig
from future_assistant.domain import ActionKind


def test_normalization_handles_arabic_digits_and_common_voice_typos() -> None:
    assert normalize_text("دَكّرني بعد ١٠ دقايق") == "ذكرني بعد 10 دقائق"
    assert normalize_text("شغل يويتوب") == "شغل يوتيوب"


def test_site_alias_typo_resolves_only_inside_configured_allowlist() -> None:
    factory = ActionFactory(AssistantConfig())

    action = factory.open_site("جيت هوب")

    assert action is not None
    assert action.kind is ActionKind.OPEN_URL
    assert action.parameters["url"] == "https://github.com/"


def test_application_typo_resolves_to_registered_application() -> None:
    factory = ActionFactory(AssistantConfig())

    action = factory.open_app("المفكره")

    assert action is not None
    assert action.kind is ActionKind.OPEN_APP
    assert action.parameters["app_id"] == "notepad"


def test_unknown_or_ambiguous_alias_is_not_invented() -> None:
    assert resolve_allowlisted_alias({"alpha": "a", "alphi": "b"}, "alphx") is None
    assert ActionFactory(AssistantConfig()).open_site("موقع غير مسجل") is None
