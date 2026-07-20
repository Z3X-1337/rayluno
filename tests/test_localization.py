from __future__ import annotations

from types import MappingProxyType

import pytest

from future_assistant.localization import (
    DEFAULT_ASSISTANT_NAMES,
    DEFAULT_WAKE_PHRASES,
    MESSAGES,
    PRODUCT_MESSAGES,
    Language,
    MessageKey,
    default_assistant_name,
    default_wake_phrases,
    detect_language,
    localize,
    normalize_language,
    resolve_language,
)


def test_language_enum_exposes_short_values_and_readable_aliases() -> None:
    assert Language.AR.value == "ar"
    assert Language.EN.value == "en"
    assert Language.AUTO.value == "auto"
    assert Language.ARABIC is Language.AR
    assert Language.ENGLISH is Language.EN


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Language.EN, Language.EN),
        (" ar ", Language.AR),
        ("AR-JO", Language.AR),
        ("ar_SA", Language.AR),
        ("Arabic", Language.AR),
        ("العربية", Language.AR),
        ("EN-us", Language.EN),
        ("eng", Language.EN),
        ("English", Language.EN),
        ("AUTO", Language.AUTO),
        ("تلقائي", Language.AUTO),
    ],
)
def test_normalize_language_accepts_supported_forms(
    value: Language | str,
    expected: Language,
) -> None:
    assert normalize_language(value) is expected


def test_normalize_language_uses_controlled_fallbacks() -> None:
    assert normalize_language(None, fallback=Language.EN) is Language.EN
    assert normalize_language("unknown", fallback="en-GB") is Language.EN
    assert normalize_language("unknown", fallback="also-unknown") is Language.AR
    assert normalize_language(Language.AUTO, fallback=Language.EN, allow_auto=False) is Language.EN


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("افتح يوتيوب من فضلك", Language.AR),
        ("شغّل آهنگ جدید", Language.AR),
        ("Open YouTube, please", Language.EN),
        ("PLAY music 2026!", Language.EN),
        ("hello يا مساعد افتح يوتيوب", Language.AR),
        ("Please open موقع YouTube", Language.EN),
    ],
)
def test_detect_language_uses_dominant_arabic_or_latin_script(
    text: str,
    expected: Language,
) -> None:
    assert detect_language(text) is expected


@pytest.mark.parametrize("text", [None, "", "1234 !؟ 🎵", "中文 123"])
def test_detect_language_uses_fallback_without_supported_script(text: str | None) -> None:
    assert detect_language(text) is Language.AR
    assert detect_language(text, fallback=Language.EN) is Language.EN
    assert detect_language(text, fallback=Language.AUTO) is Language.AR


def test_detect_language_uses_fallback_on_exact_script_tie() -> None:
    assert detect_language("hello مرحبا", fallback=Language.EN) is Language.EN
    assert detect_language("hello مرحبا", fallback=Language.AR) is Language.AR


def test_resolve_language_only_detects_when_auto_is_selected() -> None:
    assert resolve_language(Language.AUTO, text="Open settings") is Language.EN
    assert resolve_language(Language.AUTO, text="افتح الإعدادات") is Language.AR
    assert resolve_language(Language.AR, text="Open settings") is Language.AR
    assert resolve_language("invalid", text="Open settings", fallback=Language.AR) is Language.AR


def test_every_product_message_has_a_nonempty_translation_in_both_languages() -> None:
    assert MESSAGES is PRODUCT_MESSAGES
    assert set(PRODUCT_MESSAGES) == {Language.AR, Language.EN}
    for language in (Language.AR, Language.EN):
        assert set(PRODUCT_MESSAGES[language]) == set(MessageKey)
        assert all(message.strip() for message in PRODUCT_MESSAGES[language].values())


def test_product_message_maps_are_immutable() -> None:
    assert isinstance(PRODUCT_MESSAGES, MappingProxyType)
    assert isinstance(PRODUCT_MESSAGES[Language.AR], MappingProxyType)
    with pytest.raises(TypeError):
        PRODUCT_MESSAGES[Language.AR][MessageKey.READY] = "changed"  # type: ignore[index]


def test_localize_supports_enum_string_and_auto_language() -> None:
    assert localize(MessageKey.READY, Language.AR) == "أنا جاهز لمساعدتك."
    assert localize("ready", "en-US") == "I'm ready to help."
    assert localize(MessageKey.LISTENING, Language.AUTO, text="Open YouTube") == "I'm listening..."
    assert localize(MessageKey.LISTENING, Language.AUTO, text="افتح يوتيوب").startswith("أنا")


def test_localize_rejects_unknown_message_key() -> None:
    with pytest.raises(KeyError, match="Unknown localization key"):
        localize("missing-key", Language.EN)


def test_bilingual_defaults_are_complete_immutable_and_resolvable() -> None:
    assert isinstance(DEFAULT_ASSISTANT_NAMES, MappingProxyType)
    assert isinstance(DEFAULT_WAKE_PHRASES, MappingProxyType)
    assert set(DEFAULT_ASSISTANT_NAMES) == {Language.AR, Language.EN}
    assert set(DEFAULT_WAKE_PHRASES) == {Language.AR, Language.EN}

    assert default_assistant_name(Language.AR) == "رايلونو"
    assert default_assistant_name(Language.EN) == "Rayluno"
    assert default_assistant_name(Language.AUTO, text="Hello") == "Rayluno"

    assert default_wake_phrases(Language.AR) == ("يا رايلونو", "رايلونو")
    assert default_wake_phrases(Language.EN) == ("Hey Rayluno", "Rayluno")
    assert default_wake_phrases(Language.AUTO, text="مرحبا") == ("يا رايلونو", "رايلونو")
