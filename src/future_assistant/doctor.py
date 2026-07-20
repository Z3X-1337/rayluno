"""Read-only environment checks for a non-technical first-run experience."""

from __future__ import annotations

import importlib.util
import json
import platform
import sys
from dataclasses import dataclass
from enum import StrEnum
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen

from .config import AssistantConfig
from .localization import Language
from .voice import VoiceSettings, probe_onecore_languages


class CheckStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: CheckStatus
    detail: str


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _ollama_check(config: AssistantConfig) -> DoctorCheck:
    parts = urlsplit(config.ollama_endpoint)
    if parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return DoctorCheck(
            "الذكاء المحلي",
            CheckStatus.FAIL,
            "عنوان Ollama يجب أن يكون محليًا حفاظًا على الأمان.",
        )
    path = f"{parts.path.rstrip('/')}/api/tags"
    url = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    try:
        with urlopen(url, timeout=1.5) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return DoctorCheck(
            "الذكاء المحلي",
            CheckStatus.WARN,
            "Ollama غير متصل؛ الأوامر المباشرة ستظل تعمل دون ذكاء حواري.",
        )
    names = {
        item.get("name")
        for item in payload.get("models", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if config.ollama_model not in names:
        return DoctorCheck(
            "الذكاء المحلي",
            CheckStatus.WARN,
            f"Ollama يعمل لكن النموذج غير مثبت. نفّذ: ollama pull {config.ollama_model}",
        )
    return DoctorCheck(
        "الذكاء المحلي",
        CheckStatus.PASS,
        f"Ollama والنموذج {config.ollama_model} جاهزان.",
    )


def _windows_tts_check() -> DoctorCheck:
    try:
        languages = probe_onecore_languages()
    except Exception:
        return DoctorCheck(
            "الصوت ثنائي اللغة",
            CheckStatus.WARN,
            "تعذر فحص أصوات Windows المثبتة.",
        )
    if {"ar", "en"}.issubset(languages):
        return DoctorCheck(
            "الصوت ثنائي اللغة",
            CheckStatus.PASS,
            "تم اختبار توليد الصوت العربي والإنجليزي بنجاح.",
        )
    missing = []
    if "ar" not in languages:
        missing.append("العربي")
    if "en" not in languages:
        missing.append("الإنجليزي")
    return DoctorCheck(
        "الصوت ثنائي اللغة",
        CheckStatus.WARN,
        f"الصوت غير الجاهز: {' و'.join(missing)}؛ أضفه من إعدادات اللغة والكلام في Windows.",
    )


def check_environment(
    config: AssistantConfig,
    voice: VoiceSettings,
    *,
    probe_ollama: bool = True,
) -> tuple[DoctorCheck, ...]:
    checks: list[DoctorCheck] = []
    python_ok = sys.version_info >= (3, 11)
    checks.append(
        DoctorCheck(
            "Python",
            CheckStatus.PASS if python_ok else CheckStatus.FAIL,
            platform.python_version() if python_ok else "يلزم Python 3.11 أو أحدث.",
        )
    )
    windows_ok = sys.platform == "win32"
    checks.append(
        DoctorCheck(
            "نظام التشغيل",
            CheckStatus.PASS if windows_ok else CheckStatus.WARN,
            "Windows مدعوم." if windows_ok else "هذه النسخة مستهدفة لـWindows أولًا.",
        )
    )
    checks.append(
        DoctorCheck(
            "واجهة سطح المكتب",
            CheckStatus.PASS if _module_available("webview") else CheckStatus.WARN,
            "pywebview جاهز."
            if _module_available("webview")
            else 'ثبّتها بالأمر: pip install -e ".[desktop]"',
        )
    )

    voice_modules = {
        "sounddevice": "الميكروفون",
        "vosk": "كلمة الاستيقاظ",
        "winrt.windows.media.speechsynthesis": "النطق ثنائي اللغة",
    }
    stt_module = "pywhispercpp" if voice.stt_backend == "whispercpp" else "faster_whisper"
    voice_modules[stt_module] = "تحويل الكلام إلى نص"
    missing = [label for module, label in voice_modules.items() if not _module_available(module)]
    checks.append(
        DoctorCheck(
            "حزم الصوت",
            CheckStatus.WARN if missing else CheckStatus.PASS,
            f'غير مثبت: {", ".join(missing)}. نفّذ: pip install -e ".[voice]"'
            if missing
            else "حزم الصوت المحلية جاهزة.",
        )
    )
    if sys.platform == "win32" and _module_available("winrt.windows.media.speechsynthesis"):
        checks.append(_windows_tts_check())
    wake_models = []
    if voice.language in {Language.AR, Language.AUTO}:
        wake_models.append(
            (
                "نموذج الاستيقاظ العربي",
                voice.vosk_model_path,
                "RAYLUNO_VOSK_MODEL_PATH",
            )
        )
    if voice.language in {Language.EN, Language.AUTO}:
        wake_models.append(
            (
                "نموذج الاستيقاظ الإنجليزي",
                voice.vosk_english_model_path,
                "RAYLUNO_VOSK_ENGLISH_MODEL_PATH",
            )
        )
    for label, path, environment_name in wake_models:
        if path and path.is_dir():
            checks.append(DoctorCheck(label, CheckStatus.PASS, f"موجود: {path}"))
        else:
            checks.append(
                DoctorCheck(
                    label,
                    CheckStatus.WARN,
                    f"اختر نموذج Vosk مرخصًا واضبط {environment_name}.",
                )
            )
    if probe_ollama:
        checks.append(_ollama_check(config))
    return tuple(checks)


def format_report(checks: tuple[DoctorCheck, ...]) -> str:
    icons = {
        CheckStatus.PASS: "[OK]",
        CheckStatus.WARN: "[!]",
        CheckStatus.FAIL: "[X]",
    }
    lines = ["فحص جاهزية Rayluno المحلية", ""]
    lines.extend(f"{icons[item.status]} {item.name}: {item.detail}" for item in checks)
    return "\n".join(lines)
