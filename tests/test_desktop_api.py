from datetime import datetime
from pathlib import Path

from future_assistant.activation import ActivationConfig, ActivationGrant, StoredActivation
from future_assistant.config import AssistantConfig
from future_assistant.domain import Plan, PlanSource, RuntimeResult, RuntimeStatus
from future_assistant.product_settings import ProductSettingsStore
from future_assistant.product_updates import ProductUpdateService
from future_assistant.runtime import DryRunEffects, build_runtime, without_wake_word
from future_assistant.ui.window import PRODUCT_AI_REPORT_URL, PRODUCT_PURCHASE_URL, DesktopApi


def _api(settings_path: Path | None = None) -> DesktopApi:
    config = without_wake_word(AssistantConfig(audit_path=None))
    effects = DryRunEffects(clock=lambda: datetime(2026, 7, 11, 9, 30))
    return DesktopApi(
        build_runtime(config, effects=effects),
        assistant_name="المساعد",
        settings_store=ProductSettingsStore(settings_path) if settings_path else None,
    )


def test_execute_command_returns_json_safe_result_and_volatile_history() -> None:
    api = _api()

    result = api.execute_command("كم الساعة الآن")

    assert result["ok"] is True
    assert result["action"] == "report_time"
    assert result["command"] == "كم الساعة الآن"
    snapshot = api.get_snapshot()
    assert snapshot["history"] == [result]


def test_empty_and_oversized_commands_are_rejected_before_runtime() -> None:
    api = _api()

    assert api.execute_command("  ")["ok"] is False
    assert api.execute_command("س" * 2_001)["action"] == "blocked"
    assert api.get_snapshot()["history"] == []


def test_clear_history_does_not_require_desktop_dependency() -> None:
    api = _api()
    api.execute_command("افتح الحاسبة")

    assert api.clear_history() == {"ok": True}
    assert api.get_snapshot()["history"] == []


def test_voice_toggle_without_controller_has_clear_setup_message() -> None:
    api = _api()

    result = api.toggle_voice()

    assert result["ok"] is False
    assert "غير مهيأة" in str(result["message"])


def test_product_settings_api_round_trip_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    api = _api(path)

    initial = api.get_product_settings()
    assert initial["first_run"] is True
    saved = api.save_product_settings(
        {
            "name": "Nova",
            "language": "en",
            "wake_phrase": "يا نوفا",
            "english_wake_phrase": "Hey Nova",
        }
    )

    assert saved["ok"] is True
    assert saved["restart_required"] is True
    assert api.get_product_settings()["settings"]["name"] == "Nova"
    assert path.is_file()

    reset = api.reset_product_settings()
    assert reset["ok"] is True
    assert reset["settings"]["name"] == "رايلونو"
    assert not path.exists()


def test_product_settings_api_rejects_unknown_fields(tmp_path: Path) -> None:
    api = _api(tmp_path / "settings.json")

    result = api.save_product_settings({"api_key": "must-not-be-saved"})

    assert result["ok"] is False


class FakeEntitlementSnapshot:
    def __init__(self, features: set[str]) -> None:
        self.features = features

    def to_public_dict(self) -> dict[str, object]:
        return {
            "state": "active",
            "edition": "pro",
            "features": sorted(self.features),
            "expires_at": 2_000_000_000,
            "pro_active": True,
        }


class FakeEntitlements:
    def __init__(self, features: set[str] | None = None) -> None:
        self.installed: str | None = None
        self.features = (
            features
            if features is not None
            else {
                "ai.local",
                "automation.pro",
                "updates.pro",
                "voice.local",
            }
        )

    def status(self) -> FakeEntitlementSnapshot:
        return FakeEntitlementSnapshot(self.features)

    def install(self, token: str) -> FakeEntitlementSnapshot:
        self.installed = token
        return FakeEntitlementSnapshot(self.features)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def remove(self) -> bool:
        self.installed = None
        return True


class FakeUpdateStatus:
    def __init__(self, *, available: bool, staged: bool = False) -> None:
        self.available = available
        self.staged = staged

    def to_public_dict(self) -> dict[str, object]:
        return {
            "configured": True,
            "checked": True,
            "available": self.available,
            "current_version": "0.1.0",
            "version": "0.2.0",
            "size": 1_234,
            "staged": self.staged,
        }


class FakeUpdates:
    configured = True

    def current_status(self) -> FakeUpdateStatus:
        return FakeUpdateStatus(available=False)

    def check(self) -> FakeUpdateStatus:
        return FakeUpdateStatus(available=True)

    def stage(self) -> FakeUpdateStatus:
        return FakeUpdateStatus(available=True, staged=True)


class FakeVoiceController:
    def __init__(self) -> None:
        self.enabled = False
        self.stopped = False

    def toggle(self) -> dict[str, object]:
        self.enabled = not self.enabled
        return {"ok": True, "enabled": self.enabled, "message": "toggled"}

    def stop(self) -> None:
        self.enabled = False
        self.stopped = True


class FakeActivationClient:
    config = ActivationConfig(endpoint="https://activate.example.com/api/license/activate")

    def __init__(self) -> None:
        self.activated: str | None = None
        self.refreshed: str | None = None
        self.deactivated: str | None = None

    def activate(
        self,
        purchase_key: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> ActivationGrant:
        del installation_id, app_version
        self.activated = purchase_key
        return ActivationGrant("x" * 40, "r" * 43, "instance-12345678")

    def refresh(
        self,
        refresh_token: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> ActivationGrant:
        del installation_id, app_version
        self.refreshed = refresh_token
        return ActivationGrant("y" * 40, "s" * 43, "instance-12345678")

    def deactivate(
        self,
        refresh_token: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> None:
        del installation_id, app_version
        self.deactivated = refresh_token


class FakeInstallationStore:
    def load_or_create(self) -> str:
        return "4f30eb03-f1db-4b4c-8eb5-29c98240f706"


class FakeActivationStateStore:
    def __init__(self) -> None:
        self.state: StoredActivation | None = None

    def save(self, state: StoredActivation) -> None:
        self.state = state

    def load(self) -> StoredActivation | None:
        return self.state

    def remove(self) -> bool:
        removed = self.state is not None
        self.state = None
        return removed


def test_license_api_exposes_no_customer_data_and_installs_token() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    entitlements = FakeEntitlements()
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=entitlements,  # type: ignore[arg-type]
    )

    activated = api.install_license("x" * 40)

    assert activated["ok"] is True
    assert entitlements.installed == "x" * 40
    assert api.get_license_status()["edition"] == "pro"
    assert "customer" not in repr(activated)
    assert "license_id" not in repr(activated)

    removed = api.remove_license()
    assert removed["ok"] is True


def test_license_api_rejects_non_encodable_or_short_tokens() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=FakeEntitlements(),  # type: ignore[arg-type]
    )

    assert api.install_license("short")["ok"] is False
    assert api.install_license("\ud800" * 40)["ok"] is False


def test_purchase_key_activation_and_refresh_keep_secrets_out_of_ui() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    entitlements = FakeEntitlements()
    client = FakeActivationClient()
    state_store = FakeActivationStateStore()
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=entitlements,  # type: ignore[arg-type]
        activation_client=client,  # type: ignore[arg-type]
        installation_store=FakeInstallationStore(),  # type: ignore[arg-type]
        activation_state_store=state_store,  # type: ignore[arg-type]
    )
    purchase_key = "38b1460a-5104-4067-a91d-77b872934d51"

    activated = api.activate_purchase_key(purchase_key)

    assert activated["ok"] is True
    assert client.activated == purchase_key
    assert state_store.state is not None
    assert activated["license"]["activation_configured"] is True
    assert activated["license"]["refresh_available"] is True
    assert purchase_key not in repr(activated)
    assert state_store.state.refresh_token not in repr(activated)

    refreshed = api.refresh_purchase_license()

    assert refreshed["ok"] is True
    assert client.refreshed == "r" * 43
    assert state_store.state is not None
    assert state_store.state.refresh_token == "s" * 43

    removed = api.remove_license()

    assert removed["ok"] is True
    assert state_store.state is None
    assert client.deactivated == "s" * 43


def test_update_api_reports_checks_and_verified_staging() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=FakeEntitlements(),  # type: ignore[arg-type]
        update_service=FakeUpdates(),  # type: ignore[arg-type]
    )

    snapshot = api.get_snapshot()
    assert snapshot["updates"]["checked"] is True

    checked = api.check_for_updates()
    assert checked["ok"] is True
    assert checked["updates"]["available"] is True

    staged = api.stage_update()
    assert staged["ok"] is True
    assert staged["updates"]["staged"] is True
    assert "موافقتك" in str(staged["message"])


def test_store_managed_updates_are_informational_and_not_pro_gated() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=FakeEntitlements(set()),  # type: ignore[arg-type]
        update_service=ProductUpdateService(None, managed_by_store=True),
    )

    snapshot = api.get_snapshot()
    assert snapshot["updates"]["managed_by_store"] is True
    assert api.check_for_updates()["ok"] is True
    staged = api.stage_update()
    assert staged["ok"] is True
    assert "Microsoft Store" in str(staged["message"])


def test_free_mode_blocks_paid_features_but_keeps_security_updates_available() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    voice = FakeVoiceController()
    opened: list[str] = []
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=FakeEntitlements(set()),  # type: ignore[arg-type]
        update_service=FakeUpdates(),  # type: ignore[arg-type]
        voice_controller=voice,
        purchase_page_opener=lambda url: not opened.append(url),
    )

    assert api.toggle_voice()["ok"] is False
    assert voice.enabled is False
    assert api.check_for_updates()["ok"] is True
    assert api.stage_update()["ok"] is True
    assert api.open_purchase_page()["ok"] is True
    assert opened == [PRODUCT_PURCHASE_URL]


def test_ai_report_opens_only_fixed_page_and_marks_generated_replies() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    opened: list[str] = []
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        ai_report_page_opener=lambda url: not opened.append(url),
    )
    generated = RuntimeResult(
        status=RuntimeStatus.COMPLETED,
        message="Generated answer",
        plan=Plan(reply="Generated answer", source=PlanSource.OLLAMA),
    )

    payload = api._result_payload(generated, "question")
    opened_result = api.open_ai_report_page()

    assert payload["ai_generated"] is True
    assert opened_result["ok"] is True
    assert opened == [PRODUCT_AI_REPORT_URL]


def test_pro_voice_starts_and_license_removal_stops_it() -> None:
    config = without_wake_word(AssistantConfig(audit_path=None))
    voice = FakeVoiceController()
    api = DesktopApi(
        build_runtime(config, effects=DryRunEffects()),
        entitlement_service=FakeEntitlements({"voice.local"}),  # type: ignore[arg-type]
        voice_controller=voice,
    )

    assert api.toggle_voice()["ok"] is True
    assert voice.enabled is True
    assert api.remove_license()["ok"] is True
    assert voice.stopped is True
