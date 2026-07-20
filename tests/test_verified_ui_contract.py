from __future__ import annotations

from pathlib import Path


UI_ROOT = Path("src/future_assistant/ui")


def test_today_ui_loads_verified_interface_once() -> None:
    source = (UI_ROOT / "today.js").read_text(encoding="utf-8")

    assert 'script.src = "verified.js"' in source
    assert 'script[data-rayluno-verified="true"]' in source


def test_verified_interface_exposes_confirmation_and_receipt_surfaces() -> None:
    source = (UI_ROOT / "verified.js").read_text(encoding="utf-8")

    required_ids = {
        "verified-status-button",
        "verified-confirmation-dialog",
        "verified-skill-value",
        "verified-risk-value",
        "verified-permission-value",
        "verified-expiry-value",
        "verified-digest-value",
        "verified-approve",
        "verified-reject",
        "verified-receipt-dialog",
        "verified-integrity-card",
        "verified-receipt-list",
    }
    for element_id in required_ids:
        assert element_id in source

    assert "approve_skill" in source
    assert "reject_skill" in source
    assert "get_verified_receipts" in source
    assert "get_verified_status" in source


def test_verified_ui_does_not_render_raw_argument_values() -> None:
    source = (UI_ROOT / "verified.js").read_text(encoding="utf-8")

    assert "argument_digest" in source
    assert "argument_keys" not in source
    assert "pending.arguments" not in source
    assert "receipt.arguments" not in source
    assert "receipt.command" not in source


def test_verified_ui_wraps_existing_event_handler_instead_of_replacing_behavior() -> None:
    source = (UI_ROOT / "verified.js").read_text(encoding="utf-8")

    assert "const previousAssistantEvent = window.assistantEvent" in source
    assert 'typeof previousAssistantEvent === "function"' in source
    assert "previousAssistantEvent(event)" in source


def test_verified_styles_include_focus_and_responsive_states() -> None:
    source = (UI_ROOT / "verified.css").read_text(encoding="utf-8")

    assert ".verified-trigger:focus-visible" in source
    assert ".verified-dialog::backdrop" in source
    assert ".verified-integrity-card.failed" in source
    assert "@media (max-width: 720px)" in source
