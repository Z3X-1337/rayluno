"""Configuration with conservative, zero-cost defaults."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .identity import (
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_WAKE_WORDS,
    environment_value,
)
from .localization import Language, normalize_language


def _default_sites() -> dict[str, str]:
    return {
        "يوتيوب": "https://www.youtube.com/",
        "youtube": "https://www.youtube.com/",
        "جوجل": "https://www.google.com/",
        "google": "https://www.google.com/",
        "جيت هب": "https://github.com/",
        "جيتهاب": "https://github.com/",
        "github": "https://github.com/",
        "ويكيبيديا": "https://ar.wikipedia.org/",
        "wikipedia": "https://en.wikipedia.org/",
        "اوبن اي اي": "https://openai.com/",
        "openai": "https://openai.com/",
    }


def _default_apps() -> dict[str, str]:
    return {
        "الحاسبة": "calculator",
        "حاسبة": "calculator",
        "آلة حاسبة": "calculator",
        "الة حاسبة": "calculator",
        "calculator": "calculator",
        "المفكرة": "notepad",
        "مفكرة": "notepad",
        "notepad": "notepad",
        "مستكشف الملفات": "file_manager",
        "مدير الملفات": "file_manager",
        "الملفات": "file_manager",
        "explorer": "file_manager",
        "الرسام": "paint",
        "رسام": "paint",
        "paint": "paint",
    }


def _env_bool(suffix: str, default: bool) -> bool:
    value = environment_value(suffix, "")
    if not value:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on", "نعم"}


@dataclass(frozen=True, slots=True)
class AssistantConfig:
    assistant_name: str = DEFAULT_ASSISTANT_NAME
    language: Language = Language.AUTO
    wake_words: tuple[str, ...] = DEFAULT_WAKE_WORDS
    require_wake_word: bool = True
    allowed_schemes: tuple[str, ...] = ("https", "http")
    allowed_domains: tuple[str, ...] = (
        "google.com",
        "youtube.com",
        "youtu.be",
        "github.com",
        "wikipedia.org",
        "openai.com",
    )
    sites: Mapping[str, str] = field(default_factory=_default_sites)
    apps: Mapping[str, str] = field(default_factory=_default_apps)
    allowed_app_ids: tuple[str, ...] = ("calculator", "notepad", "file_manager", "paint")
    search_url: str = "https://www.google.com/search"
    youtube_search_url: str = "https://www.youtube.com/results"
    max_query_length: int = 500
    max_url_length: int = 2048
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_seconds: float = 20.0
    audit_path: Path | None = field(
        default_factory=lambda: Path.home() / ".future_assistant" / "audit.jsonl"
    )

    @classmethod
    def from_env(cls) -> AssistantConfig:
        wake_words = tuple(
            item.strip()
            for item in environment_value("WAKE_WORDS", ",".join(DEFAULT_WAKE_WORDS)).split(",")
            if item.strip()
        )
        preferred_audit, legacy_audit = (
            "RAYLUNO_AUDIT_PATH",
            "FUTURE_ASSISTANT_AUDIT_PATH",
        )
        audit_is_set = preferred_audit in os.environ or legacy_audit in os.environ
        audit_value = environment_value("AUDIT_PATH")
        if not audit_is_set:
            audit_path = Path.home() / ".future_assistant" / "audit.jsonl"
        elif audit_value.strip():
            audit_path = Path(audit_value).expanduser()
        else:
            audit_path = None
        return cls(
            assistant_name=(
                environment_value("NAME", DEFAULT_ASSISTANT_NAME).strip()[:40]
                or DEFAULT_ASSISTANT_NAME
            ),
            language=normalize_language(environment_value("LANGUAGE", "auto")),
            wake_words=wake_words or cls().wake_words,
            require_wake_word=_env_bool("REQUIRE_WAKE_WORD", True),
            ollama_endpoint=environment_value("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"),
            ollama_model=environment_value("OLLAMA_MODEL", "qwen3.5:4b"),
            audit_path=audit_path,
        )
