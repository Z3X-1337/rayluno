from pathlib import Path

UI_DIR = Path(__file__).parents[1] / "src" / "future_assistant" / "ui"
TODAY_JAVASCRIPT = (UI_DIR / "today.js").read_text(encoding="utf-8")
TODAY_CSS = (UI_DIR / "today.css").read_text(encoding="utf-8")


def test_verified_surface_is_bilingual_and_wired_to_desktop_bridge() -> None:
    for value in (
        'verifiedConfirm: "تأكيد"',
        'verifiedConfirm: "Confirm"',
        'verifiedCancel: "إلغاء"',
        'verifiedCancel: "Cancel"',
        "get_verified_snapshot",
        'submitCommand(tr("verifiedConfirmCommand"))',
        'submitCommand(tr("verifiedCancelCommand"))',
    ):
        assert value in TODAY_JAVASCRIPT


def test_verified_surface_shows_permission_risk_receipt_and_hash_chain() -> None:
    for element_id in (
        "verified-skill",
        "verified-detail",
        "verified-actions",
        "verified-receipt-id",
        "verified-chain",
    ):
        assert element_id in TODAY_JAVASCRIPT
    assert "verified.pending.permission" in TODAY_JAVASCRIPT
    assert "verified.pending.risk" in TODAY_JAVASCRIPT
    assert "latest?.receipt_id" in TODAY_JAVASCRIPT
    assert "verified.chain_head.slice(0, 10)" in TODAY_JAVASCRIPT
    assert ".verified-execution.pending" in TODAY_CSS
    assert "@keyframes verified-pulse" in TODAY_CSS
