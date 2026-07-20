"""Safe, local persistence for user-facing product settings.

The settings document deliberately has a small allowlisted schema.  Credentials,
tokens, command history, and other sensitive values do not belong in this store.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from .identity import (
    COMPATIBILITY_DATA_DIRECTORY,
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_WAKE_PHRASE_AR,
    DEFAULT_WAKE_PHRASE_EN,
)

SCHEMA_VERSION: Final = 3
# Stable on purpose: reusing the data root preserves existing settings, models,
# activation state, and offline licenses after the customer-facing rebrand.
APP_DIRECTORY_NAME: Final = COMPATIBILITY_DATA_DIRECTORY
SETTINGS_FILE_NAME: Final = "settings.json"
ALLOWED_SETTING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "language",
        "wake_phrase",
        "english_wake_phrase",
        "stt_backend",
        "stt_model",
        "ollama_model",
        "tts_voice",
        "telemetry_opt_in",
    }
)
SUPPORTED_STT_BACKENDS: Final[frozenset[str]] = frozenset({"faster-whisper", "whispercpp"})
SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"ar", "auto", "en"})
_SCHEMA_V1_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "wake_phrase",
        "stt_backend",
        "stt_model",
        "ollama_model",
        "tts_voice",
        "telemetry_opt_in",
    }
)
_LEGACY_DEFAULT_NAME: Final = "المساعد"
_LEGACY_DEFAULT_WAKE_PHRASE: Final = "يا مساعد"
_LEGACY_DEFAULT_ENGLISH_WAKE_PHRASE: Final = "hey assistant"


class SettingsValidationError(ValueError):
    """Raised when settings do not conform to the public product schema."""


def default_settings_path() -> Path:
    """Return the per-user settings path, preferring Windows ``LOCALAPPDATA``."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_directory = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base_directory = Path.home() / "AppData" / "Local"
    else:
        # This fallback keeps development and tests usable outside Windows while
        # preserving the required LOCALAPPDATA location on the target platform.
        base_directory = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_directory / APP_DIRECTORY_NAME / SETTINGS_FILE_NAME


def _clean_text(value: object, *, field_name: str, maximum_length: int) -> str:
    if not isinstance(value, str):
        raise SettingsValidationError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise SettingsValidationError(f"{field_name} must not be empty")
    if len(cleaned) > maximum_length:
        raise SettingsValidationError(f"{field_name} must not exceed {maximum_length} characters")
    if any(ord(character) < 32 for character in cleaned):
        raise SettingsValidationError(f"{field_name} must not contain control characters")
    return cleaned


@dataclass(frozen=True, slots=True)
class ProductSettings:
    """The complete, intentionally small set of settings persisted by the product."""

    name: str = DEFAULT_ASSISTANT_NAME
    language: str = "auto"
    wake_phrase: str = DEFAULT_WAKE_PHRASE_AR
    english_wake_phrase: str = DEFAULT_WAKE_PHRASE_EN
    stt_backend: str = "whispercpp"
    stt_model: str = "base"
    ollama_model: str = "qwen3.5:4b"
    tts_voice: str | None = None
    telemetry_opt_in: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _clean_text(self.name, field_name="name", maximum_length=80),
        )
        if not isinstance(self.language, str):
            raise SettingsValidationError("language must be a string")
        language = self.language.strip().casefold()
        if language not in SUPPORTED_LANGUAGES:
            supported_languages = ", ".join(sorted(SUPPORTED_LANGUAGES))
            raise SettingsValidationError(f"language must be one of: {supported_languages}")
        object.__setattr__(self, "language", language)
        object.__setattr__(
            self,
            "wake_phrase",
            _clean_text(self.wake_phrase, field_name="wake_phrase", maximum_length=120),
        )
        object.__setattr__(
            self,
            "english_wake_phrase",
            _clean_text(
                self.english_wake_phrase,
                field_name="english_wake_phrase",
                maximum_length=120,
            ),
        )
        backend = _clean_text(
            self.stt_backend,
            field_name="stt_backend",
            maximum_length=40,
        ).casefold()
        if backend not in SUPPORTED_STT_BACKENDS:
            supported = ", ".join(sorted(SUPPORTED_STT_BACKENDS))
            raise SettingsValidationError(f"stt_backend must be one of: {supported}")
        object.__setattr__(self, "stt_backend", backend)
        object.__setattr__(
            self,
            "stt_model",
            _clean_text(self.stt_model, field_name="stt_model", maximum_length=200),
        )
        object.__setattr__(
            self,
            "ollama_model",
            _clean_text(self.ollama_model, field_name="ollama_model", maximum_length=200),
        )
        if self.tts_voice is not None:
            object.__setattr__(
                self,
                "tts_voice",
                _clean_text(self.tts_voice, field_name="tts_voice", maximum_length=200),
            )
        if not isinstance(self.telemetry_opt_in, bool):
            raise SettingsValidationError("telemetry_opt_in must be a boolean")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible dictionary containing allowlisted keys only."""

        values: dict[str, object] = asdict(self)
        # Keep this assertion close to serialization so a future field cannot be
        # persisted accidentally without an explicit schema decision.
        if values.keys() != ALLOWED_SETTING_KEYS:
            raise RuntimeError("ProductSettings and ALLOWED_SETTING_KEYS are out of sync")
        return values

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> ProductSettings:
        """Validate and construct settings from an untrusted mapping."""

        unknown_keys = set(values) - ALLOWED_SETTING_KEYS
        if unknown_keys:
            names = ", ".join(sorted(str(key) for key in unknown_keys))
            raise SettingsValidationError(f"unknown setting keys: {names}")
        return cls(**dict(values))


def _settings_document(settings: ProductSettings) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "settings": settings.to_dict(),
    }


def _migrate_legacy_brand_defaults(values: Mapping[str, object]) -> dict[str, object]:
    """Move only exact beta defaults to Rayluno while preserving custom values."""

    migrated = dict(values)
    if migrated.get("name") == _LEGACY_DEFAULT_NAME:
        migrated["name"] = DEFAULT_ASSISTANT_NAME
    if migrated.get("wake_phrase") == _LEGACY_DEFAULT_WAKE_PHRASE:
        migrated["wake_phrase"] = DEFAULT_WAKE_PHRASE_AR
    english_wake = migrated.get("english_wake_phrase")
    if (
        isinstance(english_wake, str)
        and english_wake.strip().casefold() == _LEGACY_DEFAULT_ENGLISH_WAKE_PHRASE
    ):
        migrated["english_wake_phrase"] = DEFAULT_WAKE_PHRASE_EN
    return migrated


def _atomic_write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, raw_temporary_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(raw_temporary_path)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
            with suppress(OSError):
                # Windows ACLs, rather than POSIX mode bits, govern access.
                path.chmod(0o600)
        except BaseException:
            # ``fdopen`` owns the descriptor after it succeeds.  If it fails,
            # close the descriptor here before cleaning up the temporary file.
            with suppress(OSError):
                os.close(descriptor)
            raise
    finally:
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                temporary_path.unlink()


class ProductSettingsStore:
    """Load and atomically persist settings in a single per-user JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else default_settings_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> ProductSettings:
        """Load validated settings, returning safe defaults for any unreadable document."""

        try:
            with self._path.open(encoding="utf-8") as stream:
                document = json.load(stream)
            if not isinstance(document, dict):
                raise SettingsValidationError("settings document must be an object")
            if set(document) != {"schema_version", "settings"}:
                raise SettingsValidationError("settings document has unknown or missing keys")
            schema_version = document["schema_version"]
            if schema_version not in {1, 2, SCHEMA_VERSION}:
                raise SettingsValidationError("unsupported settings schema version")
            values = document["settings"]
            if not isinstance(values, dict):
                raise SettingsValidationError("settings must be an object")
            if schema_version == 1:
                if set(values) - _SCHEMA_V1_KEYS:
                    raise SettingsValidationError("version 1 settings contain unknown keys")
                values = {
                    **values,
                    "language": "auto",
                    "english_wake_phrase": _LEGACY_DEFAULT_ENGLISH_WAKE_PHRASE,
                }
            if schema_version < SCHEMA_VERSION:
                values = _migrate_legacy_brand_defaults(values)
            return ProductSettings.from_mapping(values)
        except (
            json.JSONDecodeError,
            OSError,
            TypeError,
            UnicodeError,
            SettingsValidationError,
        ):
            return ProductSettings()

    def save(self, settings: ProductSettings) -> Path:
        """Atomically replace the stored settings and return their path."""

        if not isinstance(settings, ProductSettings):
            raise TypeError("settings must be a ProductSettings instance")
        _atomic_write_json(self._path, _settings_document(settings))
        return self._path

    def export(self, destination: Path) -> Path:
        """Export a validated, secret-free snapshot without changing the primary store."""

        destination = Path(destination)
        _atomic_write_json(destination, _settings_document(self.load()))
        return destination

    def delete(self) -> bool:
        """Delete persisted settings, returning whether a file was removed."""

        try:
            self._path.unlink()
        except FileNotFoundError:
            return False
        return True


def load_settings(path: Path | None = None) -> ProductSettings:
    """Convenience wrapper around :class:`ProductSettingsStore`."""

    return ProductSettingsStore(path).load()


def save_settings(settings: ProductSettings, path: Path | None = None) -> Path:
    """Convenience wrapper around :class:`ProductSettingsStore`."""

    return ProductSettingsStore(path).save(settings)


def export_settings(destination: Path, source: Path | None = None) -> Path:
    """Export validated settings from ``source`` to ``destination``."""

    return ProductSettingsStore(source).export(destination)


def delete_settings(path: Path | None = None) -> bool:
    """Delete the settings document at ``path`` or the default location."""

    return ProductSettingsStore(path).delete()
