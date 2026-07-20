"""Native desktop window and a deliberately small JavaScript bridge."""

from __future__ import annotations

import json
import time
import webbrowser
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Protocol

from future_assistant import __version__
from future_assistant.activation import (
    ActivationClient,
    ActivationConfig,
    ActivationError,
    ActivationRejectedError,
    ActivationStateStore,
    InstallationIdentityStore,
    StoredActivation,
)
from future_assistant.config import AssistantConfig
from future_assistant.domain import PlanSource, RuntimeResult, RuntimeStatus
from future_assistant.entitlements import EntitlementService, build_default_entitlement_service
from future_assistant.identity import DEFAULT_ASSISTANT_NAME
from future_assistant.licensing import LicensingError
from future_assistant.product_settings import (
    ProductSettings,
    ProductSettingsStore,
    SettingsValidationError,
)
from future_assistant.product_updates import (
    ProductUpdateService,
    build_default_update_service,
    safe_update_error,
)
from future_assistant.runtime import AssistantRuntime
from future_assistant.updates import UpdateError
from future_assistant.voice import VoiceLoop, VoiceSettings, build_voice_loop

PRODUCT_PURCHASE_URL = "https://future-assistant-local.zaid-hj2003.chatgpt.site/#pricing"
PRODUCT_AI_REPORT_URL = "https://future-assistant-local.zaid-hj2003.chatgpt.site/report"


class VoiceController(Protocol):
    @property
    def enabled(self) -> bool: ...

    def toggle(self) -> dict[str, object]: ...

    def stop(self) -> None: ...


class DesktopApi:
    """Only the methods in this class are exposed to the local web UI."""

    def __init__(
        self,
        runtime: AssistantRuntime,
        *,
        assistant_name: str = DEFAULT_ASSISTANT_NAME,
        voice_controller: VoiceController | None = None,
        settings_store: ProductSettingsStore | None = None,
        entitlement_service: EntitlementService | None = None,
        update_service: ProductUpdateService | None = None,
        activation_client: ActivationClient | None = None,
        installation_store: InstallationIdentityStore | None = None,
        activation_state_store: ActivationStateStore | None = None,
        purchase_page_opener: Callable[[str], bool] | None = None,
        ai_report_page_opener: Callable[[str], bool] | None = None,
    ) -> None:
        self.runtime = runtime
        self.assistant_name = assistant_name
        self._voice_controller = voice_controller
        self._settings_store = settings_store or ProductSettingsStore()
        self._entitlements = entitlement_service
        self._updates = update_service
        self._activation_client = activation_client
        self._installation_store = installation_store
        self._activation_state_store = activation_state_store
        self._purchase_page_opener = purchase_page_opener or webbrowser.open_new_tab
        self._ai_report_page_opener = ai_report_page_opener or webbrowser.open_new_tab
        self._window: Any | None = None
        self._history: list[dict[str, object]] = []
        self._history_lock = Lock()
        self._execution_lock = Lock()
        self._settings_lock = Lock()
        self._license_lock = Lock()

    def bind_window(self, window: Any) -> None:
        self._window = window

    def set_voice_controller(self, controller: VoiceController) -> None:
        self._voice_controller = controller

    def execute_command(self, command: str) -> dict[str, object]:
        """Execute a typed or transcribed command and return JSON-safe data."""

        cleaned = command.strip() if isinstance(command, str) else ""
        if not cleaned:
            return {"ok": False, "message": "اكتب أمرًا أولًا.", "action": "none"}
        if len(cleaned) > 2_000:
            return {
                "ok": False,
                "message": "الأمر أطول من الحد المسموح.",
                "action": "blocked",
            }
        with self._execution_lock:
            result = self.runtime.handle(cleaned)
        payload = self._result_payload(result, cleaned)
        with self._history_lock:
            self._history.insert(0, payload)
            del self._history[20:]
        return dict(payload)

    def get_snapshot(self) -> dict[str, object]:
        controller = self._voice_controller
        with self._history_lock:
            history = [dict(item) for item in self._history]
        return {
            "name": self.assistant_name,
            "version": __version__,
            "engine": "الاستماع المحلي نشط"
            if controller and controller.enabled
            else "الأوامر المحلية جاهزة",
            "mode": "listening" if controller and controller.enabled else "idle",
            "history": history,
            "first_run": not self._settings_store.path.is_file(),
            "settings": self._settings_store.load().to_dict(),
            "license": self.get_license_status(),
            "updates": self.get_update_status(),
        }

    def get_update_status(self) -> dict[str, object]:
        if self._updates is None:
            return {
                "configured": False,
                "managed_by_store": False,
                "checked": False,
                "available": False,
                "current_version": __version__,
                "version": None,
                "size": None,
                "staged": False,
            }
        return self._updates.current_status().to_public_dict()

    def check_for_updates(self) -> dict[str, object]:
        if self._updates is not None and getattr(self._updates, "managed_by_store", False):
            return {
                "ok": True,
                "message": "يدير Microsoft Store التحديثات تلقائيًا.",
                "updates": self._updates.current_status().to_public_dict(),
            }
        if self._updates is None or not self._updates.configured:
            return {"ok": False, "message": "قناة التحديث غير مهيأة بعد."}
        try:
            status = self._updates.check().to_public_dict()
        except Exception as exc:
            return {"ok": False, "message": safe_update_error(exc)}
        message = "يتوفر تحديث جديد." if status["available"] else "لديك أحدث إصدار."
        return {"ok": True, "message": message, "updates": status}

    def stage_update(self) -> dict[str, object]:
        if self._updates is not None and getattr(self._updates, "managed_by_store", False):
            return {
                "ok": True,
                "message": "يدير Microsoft Store التحديثات تلقائيًا.",
                "updates": self._updates.current_status().to_public_dict(),
            }
        if self._updates is None:
            return {"ok": False, "message": "قناة التحديث غير مهيأة بعد."}
        try:
            status = self._updates.stage().to_public_dict()
        except Exception as exc:
            return {"ok": False, "message": safe_update_error(exc)}
        return {
            "ok": True,
            "message": "تم تنزيل التحديث والتحقق منه. لن يُشغّل دون موافقتك.",
            "updates": status,
        }

    def get_license_status(self) -> dict[str, object]:
        if self._entitlements is None:
            status: dict[str, object] = {
                "state": "unavailable",
                "edition": "free",
                "features": ["commands.basic", "privacy.local"],
                "expires_at": None,
                "pro_active": False,
            }
        else:
            status = self._entitlements.status().to_public_dict()
        status["activation_configured"] = self._online_activation_available
        status["refresh_available"] = self._refresh_state_available
        return status

    def _has_feature(self, feature: str) -> bool:
        """Fail closed when a commercial capability cannot be verified."""

        if self._entitlements is None:
            return False
        try:
            return self._entitlements.has_feature(feature)
        except LicensingError:
            return False

    @property
    def _online_activation_available(self) -> bool:
        return bool(
            self._activation_client
            and self._activation_client.config.configured
            and self._installation_store
            and self._activation_state_store
        )

    @property
    def _refresh_state_available(self) -> bool:
        if self._activation_state_store is None:
            return False
        try:
            return self._activation_state_store.load() is not None
        except ActivationError:
            return False

    def activate_purchase_key(self, purchase_key: object) -> dict[str, object]:
        """Exchange a short store key for a verified offline Pro lease."""

        if not self._online_activation_available or self._entitlements is None:
            return {"ok": False, "message": "خدمة التفعيل عبر الإنترنت غير مهيأة بعد."}
        if not isinstance(purchase_key, str) or not 12 <= len(purchase_key.strip()) <= 256:
            return {"ok": False, "message": "مفتاح الشراء غير صالح."}
        assert self._activation_client is not None
        assert self._installation_store is not None
        assert self._activation_state_store is not None
        with self._license_lock:
            try:
                installation_id = self._installation_store.load_or_create()
                grant = self._activation_client.activate(
                    purchase_key.strip(),
                    installation_id,
                    app_version=__version__,
                )
                status = self._entitlements.install(grant.license_token)
                try:
                    self._activation_state_store.save(
                        StoredActivation(
                            installation_id=installation_id,
                            refresh_token=grant.refresh_token,
                            instance_id=grant.instance_id,
                        )
                    )
                except ActivationError:
                    self._entitlements.remove()
                    raise
            except ActivationRejectedError as exc:
                message = (
                    "انتهت صلاحية مفتاح الشراء أو تم تعطيله."
                    if exc.code in {"license_expired", "license_disabled"}
                    else "مفتاح الشراء غير صالح أو لا يخص هذا المنتج."
                )
                return {"ok": False, "message": message}
            except ActivationError:
                return {"ok": False, "message": "تعذّر الاتصال بخدمة التفعيل بأمان."}
            except LicensingError:
                return {"ok": False, "message": "تعذّر التحقق من الترخيص المستلم."}
        public_status = status.to_public_dict()
        public_status["activation_configured"] = True
        public_status["refresh_available"] = True
        return {
            "ok": True,
            "message": "تم تفعيل Pro وربطه بهذا التثبيت بنجاح.",
            "license": public_status,
        }

    def refresh_purchase_license(self) -> dict[str, object]:
        """Renew the short signed lease without exposing its opaque refresh token."""

        if not self._online_activation_available or self._entitlements is None:
            return {"ok": False, "message": "خدمة تجديد الترخيص غير مهيأة بعد."}
        assert self._activation_client is not None
        assert self._activation_state_store is not None
        with self._license_lock:
            try:
                stored = self._activation_state_store.load()
                if stored is None:
                    return {"ok": False, "message": "لا توجد بيانات تفعيل محفوظة للتجديد."}
                grant = self._activation_client.refresh(
                    stored.refresh_token,
                    stored.installation_id,
                    app_version=__version__,
                )
                status = self._entitlements.install(grant.license_token)
                self._activation_state_store.save(
                    StoredActivation(
                        installation_id=stored.installation_id,
                        refresh_token=grant.refresh_token,
                        instance_id=grant.instance_id,
                    )
                )
            except ActivationRejectedError as exc:
                message = (
                    "انتهت صلاحية الترخيص أو تم تعطيله."
                    if exc.code in {"license_expired", "license_disabled"}
                    else "تعذّر تجديد الترخيص من بيانات التفعيل الحالية."
                )
                return {"ok": False, "message": message}
            except ActivationError:
                return {"ok": False, "message": "تعذّر الاتصال بخدمة التجديد بأمان."}
            except LicensingError:
                return {"ok": False, "message": "تعذّر التحقق من الترخيص المجدد."}
        public_status = status.to_public_dict()
        public_status["activation_configured"] = True
        public_status["refresh_available"] = True
        return {
            "ok": True,
            "message": "تم تجديد ترخيص Pro والتحقق منه.",
            "license": public_status,
        }

    def start_background_license_refresh(self) -> None:
        """Refresh an expired or nearly-expired lease without delaying the window."""

        if not self._online_activation_available or not self._refresh_state_available:
            return
        status = self.get_license_status()
        expires_at = status.get("expires_at")
        due = status.get("state") == "expired" or (
            isinstance(expires_at, int) and expires_at <= int(time.time()) + 7 * 86_400
        )
        if due:
            Thread(
                target=self.refresh_purchase_license,
                name="future-assistant-license-refresh",
                daemon=True,
            ).start()

    def install_license(self, token: object) -> dict[str, object]:
        """Verify and install a signed license without exposing failure internals."""

        if self._entitlements is None:
            return {"ok": False, "message": "التحقق من الترخيص غير متاح في هذه النسخة."}
        if not isinstance(token, str):
            return {"ok": False, "message": "رمز الترخيص غير صالح."}
        try:
            token_size = len(token.encode("utf-8"))
        except UnicodeEncodeError:
            return {"ok": False, "message": "رمز الترخيص غير صالح."}
        if not 20 <= token_size <= 131_072:
            return {"ok": False, "message": "رمز الترخيص غير صالح."}
        try:
            status = self._entitlements.install(token).to_public_dict()
        except LicensingError:
            return {"ok": False, "message": "تعذّر التحقق من رمز الترخيص."}
        return {
            "ok": True,
            "message": "تم تفعيل الترخيص بنجاح.",
            "license": {**status, **self._activation_public_flags()},
        }

    def _activation_public_flags(self) -> dict[str, bool]:
        return {
            "activation_configured": self._online_activation_available,
            "refresh_available": self._refresh_state_available,
        }

    def remove_license(self) -> dict[str, object]:
        if self._entitlements is None:
            return {"ok": False, "message": "التحقق من الترخيص غير متاح في هذه النسخة."}
        try:
            with self._license_lock:
                if self._activation_state_store is not None:
                    stored = self._activation_state_store.load()
                    if (
                        stored is not None
                        and self._activation_client is not None
                        and self._activation_client.config.configured
                    ):
                        try:
                            self._activation_client.deactivate(
                                stored.refresh_token,
                                stored.installation_id,
                                app_version=__version__,
                            )
                        except ActivationRejectedError as exc:
                            # A missing/expired server record means there is no
                            # active slot left to preserve; local cleanup is safe.
                            if exc.code not in {"invalid_refresh_token", "license_expired"}:
                                raise
                    self._activation_state_store.remove()
                removed = self._entitlements.remove()
        except (ActivationError, LicensingError):
            return {"ok": False, "message": "تعذّر إزالة الترخيص."}
        if removed and self._voice_controller is not None:
            self._voice_controller.stop()
        return {
            "ok": True,
            "message": "تمت إزالة الترخيص المدفوع." if removed else "لا يوجد ترخيص مدفوع.",
            "license": self.get_license_status(),
        }

    def get_product_settings(self) -> dict[str, object]:
        """Return the non-secret, allowlisted settings document for the UI."""

        with self._settings_lock:
            first_run = not self._settings_store.path.is_file()
            settings = self._settings_store.load()
        return {
            "ok": True,
            "first_run": first_run,
            "settings": settings.to_dict(),
        }

    def save_product_settings(self, values: object) -> dict[str, object]:
        """Validate and atomically persist settings supplied by JavaScript."""

        if not isinstance(values, Mapping):
            return {"ok": False, "message": "إعدادات غير صالحة."}
        with self._settings_lock:
            current = self._settings_store.load().to_dict()
            candidate = {**current, **dict(values)}
            if candidate.get("tts_voice") == "":
                candidate["tts_voice"] = None
            try:
                settings = ProductSettings.from_mapping(candidate)
                self._settings_store.save(settings)
            except (SettingsValidationError, TypeError, ValueError):
                return {"ok": False, "message": "إعدادات غير صالحة."}
        self.assistant_name = settings.name
        return {
            "ok": True,
            "message": "حُفظت الإعدادات. أعد تشغيل التطبيق لتطبيق إعدادات الصوت والذكاء.",
            "restart_required": True,
            "settings": settings.to_dict(),
        }

    def reset_product_settings(self) -> dict[str, object]:
        """Reset preferences without touching audit, models, or licensing data."""

        with self._settings_lock:
            self._settings_store.delete()
            settings = ProductSettings()
        self.assistant_name = settings.name
        return {
            "ok": True,
            "message": "أُعيدت الإعدادات الافتراضية.",
            "settings": settings.to_dict(),
        }

    def clear_history(self) -> dict[str, object]:
        """Clear volatile UI history; the privacy-preserving audit remains intact."""

        with self._history_lock:
            self._history.clear()
        return {"ok": True}

    def toggle_voice(self) -> dict[str, object]:
        if self._voice_controller is None:
            return {
                "ok": False,
                "enabled": False,
                "message": "طبقة الصوت غير مهيأة بعد. شغّل فحص الجاهزية لمعرفة المطلوب.",
            }
        if not self._has_feature("voice.local"):
            return {
                "ok": False,
                "enabled": False,
                "message": "يتطلب الصوت المحلي الكامل ترخيص Pro نشطًا.",
            }
        return self._voice_controller.toggle()

    def open_purchase_page(self) -> dict[str, object]:
        """Open the immutable product page without accepting a URL from JavaScript."""

        try:
            opened = bool(self._purchase_page_opener(PRODUCT_PURCHASE_URL))
        except Exception:
            opened = False
        return {
            "ok": opened,
            "message": "فُتحت صفحة Pro في المتصفح." if opened else "تعذّر فتح صفحة Pro في المتصفح.",
        }

    def open_ai_report_page(self) -> dict[str, object]:
        """Open the fixed abuse-report form without accepting a JavaScript URL."""

        try:
            opened = bool(self._ai_report_page_opener(PRODUCT_AI_REPORT_URL))
        except Exception:
            opened = False
        return {
            "ok": opened,
            "message": (
                "فُتح نموذج الإبلاغ في المتصفح." if opened else "تعذّر فتح نموذج الإبلاغ في المتصفح."
            ),
        }

    def emit(self, event: dict[str, object]) -> None:
        window = self._window
        if window is None:
            return
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with suppress(Exception):
            window.evaluate_js(f"window.assistantEvent({payload})")

    def shutdown(self, *_: object) -> None:
        if self._voice_controller is not None:
            self._voice_controller.stop()

    @staticmethod
    def _result_payload(result: RuntimeResult, command: str) -> dict[str, object]:
        ok_statuses = {
            RuntimeStatus.AWAKE,
            RuntimeStatus.COMPLETED,
            RuntimeStatus.PARTIAL,
        }
        action = "none"
        if result.plan and result.plan.actions:
            action = result.plan.actions[0].kind.value
        message = result.message or "لم أفهم الأمر بعد."
        return {
            "ok": result.status in ok_statuses,
            "message": message,
            "action": action,
            "command": command,
            "status": result.status.value,
            "ai_generated": bool(
                result.plan and result.plan.source is PlanSource.OLLAMA and result.plan.reply
            ),
        }


class DesktopVoiceController:
    """Own a single background voice loop and forward its state to the UI."""

    def __init__(
        self,
        api: DesktopApi,
        settings: VoiceSettings,
    ) -> None:
        self.api = api
        self.settings = settings
        self._lock = Lock()
        self._loop: VoiceLoop | None = None
        self._thread: Thread | None = None
        self._failed = False

    @property
    def enabled(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def toggle(self) -> dict[str, object]:
        if self.enabled:
            self.stop()
            self.api.emit({"mode": "idle", "detail": "توقف الاستماع"})
            return {"ok": True, "enabled": False, "message": "تم إيقاف الميكروفون."}

        with self._lock:
            if self.enabled:
                return {"ok": True, "enabled": True, "message": "الاستماع نشط بالفعل."}
            try:
                self._loop = build_voice_loop(
                    self.settings,
                    on_command=self._on_command,
                    on_wake=self._on_wake,
                    on_error=self._on_error,
                )
            except (ValueError, RuntimeError) as exc:
                return {"ok": False, "enabled": False, "message": str(exc)}
            self._failed = False
            self._thread = Thread(
                target=self._run,
                name="future-assistant-voice",
                daemon=True,
            )
            self._thread.start()
        self.api.emit({"mode": "listening", "detail": "بانتظار كلمة الاستيقاظ"})
        return {
            "ok": True,
            "enabled": True,
            "message": f"الاستماع نشط. قل: {self.settings.wake_phrase}",
        }

    def stop(self) -> None:
        with self._lock:
            loop = self._loop
        if loop is not None:
            loop.stop()

    def _run(self) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            loop.run()
        finally:
            with self._lock:
                self._loop = None
            if not self._failed:
                self.api.emit({"mode": "idle", "detail": "توقف الاستماع"})

    def _on_wake(self) -> None:
        self.api.emit(
            {
                "mode": "listening",
                "detail": "تحدث الآن",
                "label": "تم الاستيقاظ",
                "transcript": "أنا أستمع إليك…",
            }
        )

    def _on_command(self, command: str) -> str | None:
        self.api.emit(
            {
                "mode": "thinking",
                "label": "سمعتك تقول",
                "transcript": command,
            }
        )
        result = self.api.execute_command(command)
        self.api.emit(
            {
                "mode": "listening",
                "detail": "بانتظار كلمة الاستيقاظ",
                "label": "النتيجة",
                "transcript": str(result["message"]),
                "result": result,
            }
        )
        return str(result["message"])

    def _on_error(self, error: Exception) -> None:
        self._failed = True
        self.api.emit(
            {
                "mode": "error",
                "label": "تعذر تشغيل الصوت",
                "transcript": str(error),
            }
        )


def start_desktop(
    runtime: AssistantRuntime,
    config: AssistantConfig,
    *,
    voice_settings: VoiceSettings | None = None,
    entitlement_service: EntitlementService | None = None,
    debug: bool = False,
) -> None:
    """Start the lightweight native WebView window on the main thread."""

    try:
        import webview
    except ImportError as exc:
        raise RuntimeError('واجهة سطح المكتب غير مثبتة. نفّذ: pip install -e ".[desktop]"') from exc

    entitlements = entitlement_service
    if entitlements is None:
        try:
            entitlements = build_default_entitlement_service()
        except LicensingError:
            entitlements = None
    try:
        updates = build_default_update_service()
    except UpdateError:
        updates = ProductUpdateService(None)
    activation_client: ActivationClient | None = None
    installation_store: InstallationIdentityStore | None = None
    activation_state_store: ActivationStateStore | None = None
    try:
        activation_config = ActivationConfig.from_env()
        if activation_config.configured:
            activation_client = ActivationClient(activation_config)
            installation_store = InstallationIdentityStore()
            activation_state_store = ActivationStateStore()
    except ActivationError:
        pass
    api = DesktopApi(
        runtime,
        assistant_name=config.assistant_name,
        entitlement_service=entitlements,
        update_service=updates,
        activation_client=activation_client,
        installation_store=installation_store,
        activation_state_store=activation_state_store,
    )
    controller = DesktopVoiceController(api, voice_settings or VoiceSettings.from_env())
    api.set_voice_controller(controller)
    index_path = Path(__file__).with_name("index.html").resolve()
    window = webview.create_window(
        config.assistant_name,
        url=str(index_path),
        js_api=api,
        width=1_280,
        height=760,
        min_size=(860, 620),
        resizable=True,
        background_color="#060910",
        text_select=False,
        zoomable=False,
    )
    api.bind_window(window)
    api.start_background_license_refresh()
    window.events.closed += api.shutdown
    webview.start(debug=debug, http_server=True, private_mode=True)
