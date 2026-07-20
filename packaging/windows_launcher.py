"""Shared frozen entry point for the desktop and console executables."""

from __future__ import annotations

import gc
import hashlib
import importlib
import os
import sys
from importlib.resources import files
from pathlib import Path

from future_assistant.cli import main as cli_main

_WHISPER_BASE_SHA256 = "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"


def _windows_short_path(path: Path) -> Path:
    """Return an ASCII-safe 8.3 path for native libraries with narrow APIs."""

    if sys.platform != "win32" or str(path).isascii():
        return path
    import ctypes

    get_short_path = ctypes.windll.kernel32.GetShortPathNameW
    required = get_short_path(str(path), None, 0)
    if required <= 0:
        return path
    buffer = ctypes.create_unicode_buffer(required)
    written = get_short_path(str(path), buffer, required)
    if written <= 0 or written >= required or not buffer.value.isascii():
        return path
    return Path(buffer.value)


def _bundled_models_root() -> Path:
    frozen_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return _windows_short_path(frozen_root / "models")


def _configure_bundled_voice_models() -> None:
    """Point voice code at packaged models before persisted settings are read."""

    models_root = _bundled_models_root()
    arabic_model = models_root / "vosk-model-ar-mgb2-0.4"
    english_model = models_root / "vosk-model-small-en-us-0.15"
    whisper_model = models_root / "whisper" / "ggml-base.bin"
    if arabic_model.is_dir():
        os.environ.setdefault("FUTURE_ASSISTANT_VOSK_MODEL_PATH", str(arabic_model))
    if english_model.is_dir():
        os.environ.setdefault("FUTURE_ASSISTANT_VOSK_ENGLISH_MODEL_PATH", str(english_model))
    if whisper_model.is_file():
        os.environ.setdefault("FUTURE_ASSISTANT_WHISPER_MODEL", str(whisper_model))


def _assert_release_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Required {label} is missing: {path}")
    return path


def _assert_vosk_model(path: Path, label: str) -> Path:
    required = (
        path / "am" / "final.mdl",
        path / "conf" / "mfcc.conf",
        path / "conf" / "model.conf",
    )
    missing = [str(item) for item in required if not item.is_file()]
    if missing:
        raise RuntimeError(f"Required {label} files are missing: {', '.join(missing)}")
    return path


def _release_self_test(*, include_voice: bool) -> int:
    """Exercise native commercial dependencies inside the frozen runtime."""

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    for key_name in ("license-public.pem", "updates-public.pem"):
        key_data = files("future_assistant").joinpath(f"assets/{key_name}").read_bytes()
        public_key = serialization.load_pem_public_key(key_data)
        if not isinstance(public_key, Ed25519PublicKey):
            raise RuntimeError(f"{key_name} is not an Ed25519 public key")

    if not include_voice:
        print("[OK] Commercial release self-test")
        return 0

    for module_name in (
        "_pywhispercpp",
        "sounddevice",
        "vosk",
        "win32com.client",
        "winrt.windows.foundation",
        "winrt.windows.foundation.collections",
        "winrt.windows.media.speechsynthesis",
        "winrt.windows.storage.streams",
    ):
        importlib.import_module(module_name)

    models_root = _bundled_models_root()
    arabic_model = _assert_vosk_model(models_root / "vosk-model-ar-mgb2-0.4", "Arabic Vosk model")
    english_model = _assert_vosk_model(
        models_root / "vosk-model-small-en-us-0.15", "English Vosk model"
    )
    whisper_model = _assert_release_file(
        models_root / "whisper" / "ggml-base.bin", "Whisper ggml-base model"
    )
    digest = hashlib.sha256()
    with whisper_model.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != _WHISPER_BASE_SHA256:
        raise RuntimeError("Whisper ggml-base checksum does not match the pinned release")

    # Loading each native model catches missing DLLs and truncated model trees;
    # they are released sequentially to keep the self-test viable on 8 GB PCs.
    from vosk import Model as VoskModel

    for model_path in (arabic_model, english_model):
        model = VoskModel(str(model_path))
        del model
        gc.collect()

    from pywhispercpp.model import Model as WhisperModel

    model = WhisperModel(str(whisper_model))
    del model
    gc.collect()

    from future_assistant.voice import VoiceSettings

    VoiceSettings.from_env().validate()

    # Instantiate, but do not speak through, the SAPI fallback. This exercises
    # the minimal frozen win32com client without causing audio during builds.
    from win32com.client import Dispatch

    sapi_voice = Dispatch("SAPI.SpVoice")
    if sapi_voice is None:
        raise RuntimeError("Windows SAPI voice could not be initialized")
    del sapi_voice
    print("[OK] Full local voice release self-test")
    return 0


def main() -> int:
    """Launch the desktop UI by default, while preserving all CLI switches."""

    arguments = sys.argv[1:]
    _configure_bundled_voice_models()
    if arguments == ["--release-self-test"]:
        return _release_self_test(include_voice=False)
    if arguments == ["--release-self-test-voice"]:
        return _release_self_test(include_voice=True)
    executable_name = Path(sys.executable).stem.casefold()
    if not arguments and executable_name in {"rayluno", "futureassistant"}:
        # The GUI always prepares the local-AI fallback.  CLI licensing keeps it
        # disabled in Free mode and enables it dynamically for a verified Pro user.
        arguments = ["--ui", "--ollama"]
    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
