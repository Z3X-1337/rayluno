"""Small, dependency-free localization primitives for the product.

The module intentionally has no knowledge of the UI, voice loop, or runtime.  Those
layers can therefore share the same language selection and product wording without
creating import cycles.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

from .identity import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_ASSISTANT_NAME_EN,
    DEFAULT_WAKE_PHRASE_AR,
    DEFAULT_WAKE_PHRASE_EN,
    DEFAULT_WAKE_WORD_AR,
    DEFAULT_WAKE_WORD_EN,
)


class Language(StrEnum):
    """Languages supported by the product and automatic text detection."""

    AR = "ar"
    EN = "en"
    AUTO = "auto"

    # Readable aliases for callers that prefer long member names.
    ARABIC = AR
    ENGLISH = EN


class MessageKey(StrEnum):
    """Stable identifiers for wording shared by voice and visual interfaces."""

    LISTENING = "listening"
    THINKING = "thinking"
    SUCCESS = "success"
    ERROR = "error"
    CONFIRMATION_REQUIRED = "confirmation_required"
    SAFETY_REFUSAL = "safety_refusal"
    READY = "ready"
    EMPTY_INPUT = "empty_input"
    AWAKE = "awake"
    UNDERSTANDING_ERROR = "understanding_error"
    UNHANDLED = "unhandled"
    EXECUTION_ERROR = "execution_error"
    PRO_FEATURE_REQUIRED = "pro_feature_required"
    OPENED_YOUTUBE = "opened_youtube"
    OPENED_SEARCH = "opened_search"
    OPENED_SITE = "opened_site"
    OPENED_APP = "opened_app"
    TIME_NOW = "time_now"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"


DEFAULT_LANGUAGE = Language.AR

_ARABIC_MESSAGES: Mapping[MessageKey, str] = MappingProxyType(
    {
        MessageKey.LISTENING: "أنا أستمع...",
        MessageKey.THINKING: "لحظة، أفكّر في طلبك...",
        MessageKey.SUCCESS: "تم تنفيذ طلبك بنجاح.",
        MessageKey.ERROR: "تعذّر إكمال الطلب. حاول مرة أخرى.",
        MessageKey.CONFIRMATION_REQUIRED: "هذا الإجراء يحتاج إلى تأكيدك قبل التنفيذ.",
        MessageKey.SAFETY_REFUSAL: "لن أنفّذ هذا الإجراء لأنه قد يكون غير آمن.",
        MessageKey.READY: "أنا جاهز لمساعدتك.",
        MessageKey.EMPTY_INPUT: "لم أسمع أمرًا.",
        MessageKey.AWAKE: "نعم، أنا معك.",
        MessageKey.UNDERSTANDING_ERROR: "تعذّر فهم الأمر الآن.",
        MessageKey.UNHANDLED: "لم أفهم هذا الأمر بعد.",
        MessageKey.EXECUTION_ERROR: "تعذر تنفيذ الأمر.",
        MessageKey.PRO_FEATURE_REQUIRED: "هذه الميزة تتطلب ترخيص Pro نشطًا.",
        MessageKey.OPENED_YOUTUBE: "فتحت نتائج البحث في يوتيوب.",
        MessageKey.OPENED_SEARCH: "فتحت نتائج البحث.",
        MessageKey.OPENED_SITE: "فتحت الموقع.",
        MessageKey.OPENED_APP: "فتحت التطبيق.",
        MessageKey.TIME_NOW: "الوقت الآن {time}.",
        MessageKey.VOLUME_UP: "رفعت مستوى الصوت.",
        MessageKey.VOLUME_DOWN: "خفضت مستوى الصوت.",
        MessageKey.VOLUME_MUTE: "بدّلت حالة كتم الصوت.",
    }
)

_ENGLISH_MESSAGES: Mapping[MessageKey, str] = MappingProxyType(
    {
        MessageKey.LISTENING: "I'm listening...",
        MessageKey.THINKING: "One moment, I'm working on your request...",
        MessageKey.SUCCESS: "Your request was completed successfully.",
        MessageKey.ERROR: "I couldn't complete that request. Please try again.",
        MessageKey.CONFIRMATION_REQUIRED: "This action needs your confirmation before it runs.",
        MessageKey.SAFETY_REFUSAL: "I won't run this action because it may be unsafe.",
        MessageKey.READY: "I'm ready to help.",
        MessageKey.EMPTY_INPUT: "I didn't hear a command.",
        MessageKey.AWAKE: "Yes, I'm listening.",
        MessageKey.UNDERSTANDING_ERROR: "I couldn't understand that command right now.",
        MessageKey.UNHANDLED: "I don't understand that command yet.",
        MessageKey.EXECUTION_ERROR: "I couldn't run that command.",
        MessageKey.PRO_FEATURE_REQUIRED: "This feature requires an active Pro license.",
        MessageKey.OPENED_YOUTUBE: "I opened the YouTube search results.",
        MessageKey.OPENED_SEARCH: "I opened the search results.",
        MessageKey.OPENED_SITE: "I opened the website.",
        MessageKey.OPENED_APP: "I opened the app.",
        MessageKey.TIME_NOW: "The time is {time}.",
        MessageKey.VOLUME_UP: "I raised the volume.",
        MessageKey.VOLUME_DOWN: "I lowered the volume.",
        MessageKey.VOLUME_MUTE: "I toggled mute.",
    }
)

PRODUCT_MESSAGES: Mapping[Language, Mapping[MessageKey, str]] = MappingProxyType(
    {
        Language.AR: _ARABIC_MESSAGES,
        Language.EN: _ENGLISH_MESSAGES,
    }
)

# A short alias is convenient for interface code while PRODUCT_MESSAGES remains the
# descriptive public name for documentation and integrations.
MESSAGES = PRODUCT_MESSAGES

DEFAULT_ASSISTANT_NAMES: Mapping[Language, str] = MappingProxyType(
    {
        Language.AR: DEFAULT_ASSISTANT_NAME,
        Language.EN: DEFAULT_ASSISTANT_NAME_EN,
    }
)

DEFAULT_WAKE_PHRASES: Mapping[Language, tuple[str, ...]] = MappingProxyType(
    {
        Language.AR: (DEFAULT_WAKE_PHRASE_AR, DEFAULT_WAKE_WORD_AR),
        Language.EN: (DEFAULT_WAKE_PHRASE_EN, DEFAULT_WAKE_WORD_EN),
    }
)

_LANGUAGE_ALIASES: Mapping[str, Language] = MappingProxyType(
    {
        "ar": Language.AR,
        "ara": Language.AR,
        "arabic": Language.AR,
        "العربية": Language.AR,
        "عربي": Language.AR,
        "en": Language.EN,
        "eng": Language.EN,
        "english": Language.EN,
        "الإنجليزية": Language.EN,
        "انجليزي": Language.EN,
        "auto": Language.AUTO,
        "automatic": Language.AUTO,
        "تلقائي": Language.AUTO,
    }
)


def _normalized_language_token(value: object) -> str:
    return str(value).strip().lower().replace("_", "-")


def _known_language(value: Language | str | None, *, allow_auto: bool) -> Language | None:
    if isinstance(value, Language):
        language = value
    elif value is None:
        return None
    else:
        token = _normalized_language_token(value)
        language = _LANGUAGE_ALIASES.get(token)

        # Locale tags such as ar-JO and en-US inherit their base language.  Unknown
        # tags are not guessed, so callers retain control through their fallback.
        if language is None and "-" in token:
            language = _LANGUAGE_ALIASES.get(token.partition("-")[0])

    if language is Language.AUTO and not allow_auto:
        return None
    return language


def normalize_language(
    value: Language | str | None,
    *,
    fallback: Language | str = DEFAULT_LANGUAGE,
    allow_auto: bool = True,
) -> Language:
    """Normalize a language value, returning a controlled fallback when unknown.

    Common locale tags (``ar-JO``, ``en_US``) and human-readable language names are
    accepted.  Set ``allow_auto=False`` for layers that must resolve to a concrete
    language.
    """

    language = _known_language(value, allow_auto=allow_auto)
    if language is not None:
        return language

    normalized_fallback = _known_language(fallback, allow_auto=allow_auto)
    if normalized_fallback is not None:
        return normalized_fallback

    # A bad fallback must not make behavior depend on the invalid input.  Arabic is
    # the product's current default and is always concrete.
    return DEFAULT_LANGUAGE


def _script_letter_counts(text: str) -> tuple[int, int]:
    arabic = 0
    latin = 0
    for character in text:
        if not unicodedata.category(character).startswith("L"):
            continue
        unicode_name = unicodedata.name(character, "")
        if "ARABIC" in unicode_name:
            arabic += 1
        elif "LATIN" in unicode_name:
            latin += 1
    return arabic, latin


def detect_language(
    text: str | None,
    *,
    fallback: Language | str = DEFAULT_LANGUAGE,
) -> Language:
    """Detect Arabic or English from the dominant writing script in ``text``.

    Digits, punctuation, emoji, and letters from unrelated scripts are ignored.  A
    tie or text without Arabic/Latin letters resolves through ``fallback`` instead
    of making an unstable guess.
    """

    concrete_fallback = normalize_language(fallback, allow_auto=False)
    arabic, latin = _script_letter_counts(text or "")
    if arabic > latin:
        return Language.AR
    if latin > arabic:
        return Language.EN
    return concrete_fallback


def resolve_language(
    language: Language | str | None,
    *,
    text: str | None = None,
    fallback: Language | str = DEFAULT_LANGUAGE,
) -> Language:
    """Return a concrete language, detecting from ``text`` when set to auto."""

    normalized = normalize_language(language, fallback=fallback)
    if normalized is Language.AUTO:
        return detect_language(text, fallback=fallback)
    return normalized


def localize(
    key: MessageKey | str,
    language: Language | str | None = DEFAULT_LANGUAGE,
    *,
    text: str | None = None,
    fallback: Language | str = DEFAULT_LANGUAGE,
) -> str:
    """Return a product message in a concrete or automatically detected language.

    ``text`` is only inspected when ``language`` resolves to :attr:`Language.AUTO`.
    Unknown message identifiers raise ``KeyError`` so missing translations are
    caught during development rather than silently leaking internal identifiers.
    """

    try:
        message_key = key if isinstance(key, MessageKey) else MessageKey(key)
    except (TypeError, ValueError) as error:
        raise KeyError(f"Unknown localization key: {key!r}") from error

    resolved = resolve_language(language, text=text, fallback=fallback)
    return PRODUCT_MESSAGES[resolved][message_key]


_T = TypeVar("_T")


def _localized_default(
    values: Mapping[Language, _T],
    language: Language | str | None,
    *,
    text: str | None,
    fallback: Language | str,
) -> _T:
    resolved = resolve_language(language, text=text, fallback=fallback)
    return values[resolved]


def default_assistant_name(
    language: Language | str | None = DEFAULT_LANGUAGE,
    *,
    text: str | None = None,
    fallback: Language | str = DEFAULT_LANGUAGE,
) -> str:
    """Return the neutral default assistant name for a language."""

    return _localized_default(
        DEFAULT_ASSISTANT_NAMES,
        language,
        text=text,
        fallback=fallback,
    )


def default_wake_phrases(
    language: Language | str | None = DEFAULT_LANGUAGE,
    *,
    text: str | None = None,
    fallback: Language | str = DEFAULT_LANGUAGE,
) -> tuple[str, ...]:
    """Return immutable default wake phrases for a language."""

    return _localized_default(
        DEFAULT_WAKE_PHRASES,
        language,
        text=text,
        fallback=fallback,
    )
