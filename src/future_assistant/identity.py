"""Product brand and deliberately stable compatibility identifiers.

``Rayluno`` is the customer-facing identity.  A few older technical identifiers
must remain stable so existing settings, activations, licenses, and signed update
manifests continue to work after the rebrand.  Keeping both groups here makes an
accidental compatibility-breaking rename much harder.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

# Customer-facing identity.
PRODUCT_NAME: Final = "Rayluno"
PRODUCT_NAME_AR: Final = "رايلونو"
PRODUCT_DISPLAY_NAME: Final = "Rayluno Assistant"
PRODUCT_DISPLAY_NAME_AR: Final = "مساعد رايلونو"
DEFAULT_ASSISTANT_NAME: Final = PRODUCT_NAME_AR
DEFAULT_ASSISTANT_NAME_EN: Final = PRODUCT_NAME
DEFAULT_WAKE_PHRASE_AR: Final = "يا رايلونو"
DEFAULT_WAKE_WORD_AR: Final = PRODUCT_NAME_AR
DEFAULT_WAKE_PHRASE_EN: Final = "Hey Rayluno"
DEFAULT_WAKE_WORD_EN: Final = PRODUCT_NAME
DEFAULT_WAKE_WORDS: Final = (
    DEFAULT_WAKE_PHRASE_AR,
    DEFAULT_WAKE_WORD_AR,
    DEFAULT_WAKE_PHRASE_EN,
    DEFAULT_WAKE_WORD_EN,
)

# Public configuration uses the new prefix while accepting the old prefix as a
# compatibility alias.  New values always win when both are present.
ENV_PREFIX: Final = "RAYLUNO"
LEGACY_ENV_PREFIX: Final = "FUTURE_ASSISTANT"

# Do not rename these without an explicit data/protocol migration.
COMPATIBILITY_DATA_DIRECTORY: Final = "FutureAssistant"
COMPATIBILITY_UPDATE_PRODUCT: Final = "future-assistant"
COMPATIBILITY_DISTRIBUTION_MARKER: Final = ".future-assistant-distribution"


def environment_names(suffix: str) -> tuple[str, str]:
    """Return the preferred and legacy environment names for ``suffix``."""

    normalized = suffix.strip().upper()
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError("environment suffix must contain letters, digits, or underscores")
    return f"{ENV_PREFIX}_{normalized}", f"{LEGACY_ENV_PREFIX}_{normalized}"


def environment_has(
    suffix: str,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether either supported environment variable is explicitly set."""

    values = os.environ if environment is None else environment
    preferred, legacy = environment_names(suffix)
    return preferred in values or legacy in values


def environment_value(
    suffix: str,
    default: str = "",
    environment: Mapping[str, str] | None = None,
) -> str:
    """Read a Rayluno value, falling back to the pre-rebrand variable name."""

    values = os.environ if environment is None else environment
    preferred, legacy = environment_names(suffix)
    if preferred in values:
        return values[preferred]
    if legacy in values:
        return values[legacy]
    return default
