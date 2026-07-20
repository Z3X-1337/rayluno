"""Dependency-free command-line interface for development and desktop integration."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .audit import NullAuditLogger
from .bootstrap import apply_product_settings
from .config import AssistantConfig
from .doctor import CheckStatus, check_environment, format_report
from .domain import RuntimeStatus
from .entitlements import EntitlementService, build_default_entitlement_service
from .identity import PRODUCT_NAME
from .licensing import LicensingError
from .ollama import OllamaClient
from .product_settings import load_settings
from .runtime import DryRunEffects, build_runtime, without_wake_word
from .voice import VoiceSettings, build_voice_loop


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rayluno",
        description=f"{PRODUCT_NAME} — مساعد عربي وإنجليزي محلي وآمن",
    )
    parser.add_argument("--once", metavar="TEXT", help="نفّذ أمرا واحدا ثم اخرج")
    parser.add_argument("--no-wake-word", action="store_true", help="عطّل شرط كلمة الاستيقاظ")
    parser.add_argument("--ollama", action="store_true", help="استخدم Ollama محليا كخطة احتياطية")
    parser.add_argument("--model", help="اسم نموذج Ollama")
    parser.add_argument("--dry-run", action="store_true", help="خطط ونفّذ وهميا دون آثار خارجية")
    parser.add_argument("--no-audit", action="store_true", help="عطّل سجل التدقيق المحلي")
    parser.add_argument("--ui", action="store_true", help="افتح واجهة سطح المكتب")
    parser.add_argument("--voice", action="store_true", help="شغّل الاستماع الصوتي في الطرفية")
    parser.add_argument("--doctor", action="store_true", help="افحص جاهزية الجهاز دون تغيير شيء")
    parser.add_argument("--debug-ui", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = AssistantConfig.from_env()
    product_settings = load_settings()
    voice_settings = None
    if args.doctor or args.ui or args.voice:
        try:
            voice_settings = VoiceSettings.from_env()
        except ValueError as exc:
            print(f"إعداد صوت غير صالح: {exc}", file=sys.stderr)
            return 2
        config, voice_settings = apply_product_settings(
            config,
            voice_settings,
            product_settings,
        )
    else:
        config, _ = apply_product_settings(
            config,
            VoiceSettings(),
            product_settings,
        )
    if args.doctor:
        assert voice_settings is not None
        checks = check_environment(config, voice_settings)
        print(format_report(checks))
        return 2 if any(item.status is CheckStatus.FAIL for item in checks) else 0
    if args.no_wake_word:
        config = without_wake_word(config)

    entitlements: EntitlementService | None
    try:
        entitlements = build_default_entitlement_service()
    except LicensingError:
        entitlements = None

    def has_feature(feature: str) -> bool:
        return bool(entitlements and entitlements.has_feature(feature))

    if args.voice and not has_feature("voice.local"):
        print(
            "يتطلب الصوت المحلي الكامل ترخيص Pro نشطًا. "
            "Full local voice requires an active Pro license.",
            file=sys.stderr,
        )
        return 3

    effects = DryRunEffects() if args.dry_run else None
    audit = NullAuditLogger() if args.no_audit else None
    client = None
    if args.ollama and has_feature("ai.local"):
        client = OllamaClient(
            endpoint=config.ollama_endpoint,
            model=args.model or config.ollama_model,
            timeout=config.ollama_timeout_seconds,
        )
    elif args.ollama and not args.ui:
        print(
            "يتطلب الذكاء المحلي ترخيص Pro نشطًا. Local AI requires an active Pro license.",
            file=sys.stderr,
        )
        return 3
    runtime = build_runtime(
        config,
        effects=effects,
        audit=audit,
        ollama_client=client,
        feature_checker=has_feature,
    )

    if args.ui:
        from .ui import start_desktop

        assert voice_settings is not None
        ui_config = without_wake_word(config)
        ui_runtime = build_runtime(
            ui_config,
            effects=effects,
            audit=audit,
            ollama_client=client,
            feature_checker=has_feature,
        )
        try:
            start_desktop(
                ui_runtime,
                ui_config,
                voice_settings=voice_settings,
                entitlement_service=entitlements,
                debug=args.debug_ui,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    if args.voice:
        assert voice_settings is not None
        voice_runtime = build_runtime(
            without_wake_word(config),
            effects=effects,
            audit=audit,
            ollama_client=client,
            feature_checker=has_feature,
        )

        def on_command(command: str) -> str | None:
            result = voice_runtime.handle(command)
            if result.message:
                print(f"{config.assistant_name}: {result.message}")
            return result.message or None

        def on_error(error: Exception) -> None:
            print(f"تعذر تشغيل الصوت: {error}", file=sys.stderr)

        try:
            loop = build_voice_loop(
                voice_settings,
                on_command=on_command,
                on_wake=lambda: print("تم الاستيقاظ؛ تحدث الآن…"),
                on_error=on_error,
            )
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"الاستماع نشط. قل: {voice_settings.wake_phrase} — Ctrl+C للإيقاف")
        try:
            loop.run()
        except KeyboardInterrupt:
            loop.stop()
        return 0

    if args.once is not None:
        result = runtime.handle(args.once)
        if result.message:
            print(result.message)
        return 1 if result.status is RuntimeStatus.ERROR else 0

    print(f"{config.assistant_name} جاهز. اكتب 'خروج' للإنهاء.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.casefold() in {"خروج", "انهاء", "exit", "quit"}:
            break
        result = runtime.handle(text)
        if result.message:
            print(result.message)
    return 0
