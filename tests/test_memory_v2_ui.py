from pathlib import Path

UI_DIR = Path(__file__).parents[1] / "src" / "future_assistant" / "ui"
JAVASCRIPT = (UI_DIR / "memory_v2.js").read_text(encoding="utf-8")
CSS = (UI_DIR / "memory_v2.css").read_text(encoding="utf-8")
WINDOW = (UI_DIR / "memory_window.py").read_text(encoding="utf-8")
INIT = (UI_DIR / "__init__.py").read_text(encoding="utf-8")


def test_memory_vault_is_bilingual_and_explicit_consent_only() -> None:
    for contract in (
        'eyebrow: "موافقة صريحة فقط"',
        'eyebrow: "Explicit consent only"',
        'localNote: "لا تُحفظ أي معلومة إلا عندما تطلب ذلك صراحة.',
        'localNote: "Nothing is saved unless you explicitly ask.',
        'secretPolicy: "الأسرار مرفوضة"',
        'secretPolicy: "Secrets are rejected"',
    ):
        assert contract in JAVASCRIPT


def test_memory_vault_uses_specific_server_clear_handle() -> None:
    for contract in (
        "request_memory_clear()",
        "confirm_memory_clear(confirmationId)",
        "cancel_memory_clear(confirmationId)",
        "state.clear?.confirmation_id",
        "expires_at",
    ):
        assert contract in JAVASCRIPT
    assert 'submitCommand("confirm")' not in JAVASCRIPT
    assert 'submitCommand("تأكيد")' not in JAVASCRIPT


def test_memory_vault_requires_two_clicks_for_individual_deletion() -> None:
    assert "state.armedDelete !== id" in JAVASCRIPT
    assert 'tr("confirmDelete")' in JAVASCRIPT
    assert "5_000" in JAVASCRIPT


def test_memory_vault_composes_after_verified_execution_v2() -> None:
    assert "class MemoryDesktopApi(VerifiedDesktopApi)" in WINDOW
    assert "super().bind_window(window)" in WINDOW
    assert "memory_v2.css" in WINDOW
    assert "memory_v2.js" in WINDOW
    assert "from .memory_window import" in INIT


def test_memory_vault_has_distinct_local_consent_and_destructive_surfaces() -> None:
    for selector in (
        ".memory-v2-consent",
        ".memory-v2-secret-card",
        ".memory-v2-clear-gate",
        ".memory-v2-fact.category-preference::before",
        ".memory-v2-trigger.unavailable",
    ):
        assert selector in CSS
