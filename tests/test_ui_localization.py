from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

UI_DIR = Path(__file__).parents[1] / "src" / "future_assistant" / "ui"
HTML = (UI_DIR / "index.html").read_text(encoding="utf-8")
JAVASCRIPT = (UI_DIR / "app.js").read_text(encoding="utf-8")
TODAY_JAVASCRIPT = (UI_DIR / "today.js").read_text(encoding="utf-8")
CSS = (UI_DIR / "styles.css").read_text(encoding="utf-8")


def _catalogs() -> dict[str, dict[str, str]]:
    pattern = re.compile(
        r"^\s+(?P<language>ar|en): Object\.freeze\(\{\n"
        r"(?P<body>.*?)"
        r"^\s+\}\),$",
        re.MULTILINE | re.DOTALL,
    )
    entry_pattern = re.compile(
        r'^\s+(?P<key>[A-Za-z]\w*): "(?P<value>.*)",$',
        re.MULTILINE,
    )
    catalogs: dict[str, dict[str, str]] = {"ar": {}, "en": {}}
    for source in (JAVASCRIPT, TODAY_JAVASCRIPT):
        for match in pattern.finditer(source):
            catalogs[match.group("language")].update(
                {
                    entry.group("key"): entry.group("value")
                    for entry in entry_pattern.finditer(match.group("body"))
                }
            )
    return catalogs


class _VisibleTextAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.unlocalized: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        localized = any(name == "data-i18n" for name, _value in attrs)
        self.stack.append((tag, localized))

    def handle_startendtag(self, _tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or not any(character.isalpha() for character in text):
            return
        if any(tag in {"script", "style", "svg"} for tag, _localized in self.stack):
            return
        if not any(localized for _tag, localized in self.stack):
            self.unlocalized.append(text)


def test_arabic_and_english_catalogs_have_identical_complete_keys() -> None:
    catalogs = _catalogs()

    assert set(catalogs) == {"ar", "en"}
    assert catalogs["ar"].keys() == catalogs["en"].keys()
    assert all(value.strip() for catalog in catalogs.values() for value in catalog.values())

    required = {
        "modeIdle",
        "modeListening",
        "modeThinking",
        "modeError",
        "orbIdle",
        "orbListening",
        "orbThinking",
        "orbError",
        "startListeningLabel",
        "stopListeningLabel",
        "readyForCommand",
        "requestLabel",
        "doneLabel",
        "alertLabel",
        "quickYoutubeCommand",
        "quickCalculatorCommand",
        "quickTimeCommand",
        "quickSearchCommand",
        "privacyNotice",
    }
    assert required <= catalogs["ar"].keys()
    assert catalogs["ar"]["readyForCommand"] == "جاهز لأمرك"
    assert catalogs["en"]["readyForCommand"] == "Ready for your command"


def test_every_html_translation_and_command_key_exists_in_both_catalogs() -> None:
    catalogs = _catalogs()
    html_keys = set(
        re.findall(
            r'data-i18n(?:-(?:aria-label|placeholder|title))?="([A-Za-z]\w*)"',
            HTML,
        )
    )
    html_keys.update(re.findall(r'data-command-key="([A-Za-z]\w*)"', HTML))

    assert html_keys
    assert html_keys <= catalogs["ar"].keys()
    assert html_keys <= catalogs["en"].keys()


def test_all_human_readable_static_html_text_is_localizable() -> None:
    audit = _VisibleTextAudit()
    audit.feed(HTML)

    assert audit.unlocalized == []


def test_language_picker_is_accessible_and_offers_arabic_auto_and_english() -> None:
    assert 'role="group"' in HTML
    assert 'data-i18n-aria-label="languagePickerLabel"' in HTML
    assert re.findall(r'data-language="(ar|auto|en)"', HTML) == ["ar", "auto", "en"]
    assert HTML.count('aria-pressed="') >= 4
    assert 'role="status"' in HTML
    assert 'aria-live="polite"' in HTML


def test_localized_attributes_keep_explicit_fallbacks_for_first_paint() -> None:
    for tag in re.findall(r"<[^>]+>", HTML):
        if "placeholder=" in tag:
            assert "data-i18n-placeholder=" in tag
        if "aria-label=" in tag:
            assert "data-i18n-aria-label=" in tag
        if " title=" in tag:
            assert "data-i18n-title=" in tag


def test_language_preference_is_persisted_and_updates_document_direction() -> None:
    assert 'const LANGUAGE_STORAGE_KEY = "future-assistant.ui-language"' in JAVASCRIPT
    assert "window.localStorage.getItem(LANGUAGE_STORAGE_KEY)" in JAVASCRIPT
    assert "window.localStorage.setItem(LANGUAGE_STORAGE_KEY, preference)" in JAVASCRIPT
    assert "root.lang = state.language" in JAVASCRIPT
    assert 'root.dir = state.language === "ar" ? "rtl" : "ltr"' in JAVASCRIPT
    assert "root.dataset.languagePreference = normalized" in JAVASCRIPT
    assert 'window.addEventListener("languagechange"' in JAVASCRIPT


def test_quick_action_commands_follow_the_active_interface_language() -> None:
    assert "button.dataset.command = t(button.dataset.commandKey)" in JAVASCRIPT
    assert 'submitCommand(button.dataset.command || "")' in JAVASCRIPT


def test_today_extension_owns_personal_commands_and_refreshes_local_data() -> None:
    assert 'id="quick-agenda"' in HTML
    assert 'id="quick-reminder"' in HTML
    assert "get_personal_snapshot" in TODAY_JAVASCRIPT
    assert "poll_due_reminders" in TODAY_JAVASCRIPT
    assert "submitCommandWithToday" in TODAY_JAVASCRIPT
    assert "assistantlanguagechange" in TODAY_JAVASCRIPT


def test_styles_mirror_direction_and_preserve_keyboard_and_motion_accessibility() -> None:
    assert 'html[dir="rtl"] .command-bar svg' in CSS
    assert 'html[dir="ltr"] .command-bar svg' in CSS
    assert "margin-inline" in CSS
    assert ".language-button:focus-visible" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS


def test_settings_dialog_is_real_bilingual_product_configuration() -> None:
    assert '<dialog\n      class="settings-dialog"' in HTML
    assert 'id="settings-form"' in HTML
    fields = set(re.findall(r'name="([a-z_]+)"', HTML))
    assert {
        "name",
        "language",
        "wake_phrase",
        "english_wake_phrase",
        "tts_voice",
        "stt_backend",
        "stt_model",
        "ollama_model",
    } <= fields
    assert "get_product_settings" in JAVASCRIPT
    assert "save_product_settings" in JAVASCRIPT
    assert "reset_product_settings" in JAVASCRIPT
    assert "settingsComing" not in JAVASCRIPT


def test_rayluno_brand_and_bilingual_wake_defaults_are_visible() -> None:
    assert "Rayluno" in HTML
    assert "رايلونو" in HTML
    assert 'wake_phrase: "يا رايلونو"' in JAVASCRIPT
    assert 'english_wake_phrase: "Hey Rayluno"' in JAVASCRIPT


def test_first_run_onboarding_is_local_and_explicit() -> None:
    assert 'id="first-run-card" hidden' in HTML
    assert "snapshot.first_run" in JAVASCRIPT
    assert "openSettings({ firstRun: true })" in JAVASCRIPT
    assert "this data stays on your device" in JAVASCRIPT


def test_license_and_secure_update_controls_are_bilingual_and_wired() -> None:
    for element_id in (
        "license-status",
        "license-token",
        "license-activate",
        "license-remove",
        "update-status",
        "update-check",
        "update-download",
    ):
        assert f'id="{element_id}"' in HTML
    assert HTML.count('role="status"') >= 3
    assert "install_license" in JAVASCRIPT
    assert "remove_license" in JAVASCRIPT
    assert "check_for_updates" in JAVASCRIPT
    assert "stage_update" in JAVASCRIPT
    assert "updates.checked || state.updatesChecked" in JAVASCRIPT
    assert "updates.managed_by_store === true" in JAVASCRIPT
    assert "elements.updateCheck.hidden = storeManaged" in JAVASCRIPT


def test_generated_ai_responses_offer_private_bilingual_reporting() -> None:
    catalogs = _catalogs()

    assert catalogs["ar"]["reportAiResponse"] == "إبلاغ عن هذا الرد"
    assert catalogs["en"]["reportAiResponse"] == "Report this response"
    assert "entry.ai_generated === true" in JAVASCRIPT
    assert "navigator.clipboard.writeText(reportText)" in JAVASCRIPT
    assert "open_ai_report_page" in JAVASCRIPT
    assert ".activity-report:focus-visible" in CSS
