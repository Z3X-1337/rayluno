from pathlib import Path

UI_DIR = Path(__file__).parents[1] / "src" / "future_assistant" / "ui"
JAVASCRIPT = (UI_DIR / "verified_v2.js").read_text(encoding="utf-8")
CSS = (UI_DIR / "verified_v2.css").read_text(encoding="utf-8")
WINDOW = (UI_DIR / "verified_window.py").read_text(encoding="utf-8")
INIT = (UI_DIR / "__init__.py").read_text(encoding="utf-8")


def test_verified_v2_uses_specific_confirmation_handles_not_text_commands() -> None:
    for contract in (
        "pending.confirmation_id",
        "approve_skill(confirmationId)",
        "reject_skill(confirmationId)",
        "argument_digest",
        "expires_at",
    ):
        assert contract in JAVASCRIPT
    assert 'submitCommand("confirm")' not in JAVASCRIPT
    assert 'submitCommand("تأكيد")' not in JAVASCRIPT


def test_verified_v2_exposes_bilingual_gate_and_receipt_inspector() -> None:
    for contract in (
        'gateTitle: "يتطلب هذا الإجراء موافقتك"',
        'gateTitle: "This action needs your approval"',
        'chainVerified: "CHAIN VERIFIED"',
        'chainFailed: "INTEGRITY FAILED"',
        "get_verified_snapshot",
        "get_verified_receipts",
        "verified-v2-gate",
        "verified-v2-inspector",
    ):
        assert contract in JAVASCRIPT


def test_verified_v2_visually_distinguishes_integrity_failure_and_risk() -> None:
    for selector in (
        ".verified-v2-trigger.failed",
        ".verified-v2-integrity.failed",
        '#verified-v2-risk[data-risk="medium"]',
        ".verified-integrity-failed .verified-execution",
        "@keyframes verified-v2-alert",
    ):
        assert selector in CSS


def test_desktop_composition_injects_v2_assets_after_webview_load() -> None:
    assert "class VerifiedDesktopApi(TodayDesktopApi)" in WINDOW
    assert "window.events.loaded += inject_verified_assets" in WINDOW
    assert "verified_v2.css" in WINDOW
    assert "verified_v2.js" in WINDOW
    assert "from .verified_window import" in INIT
