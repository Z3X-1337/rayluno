from pathlib import Path

UI_ROOT = Path("src/future_assistant/ui")


def test_today_ui_loads_memory_vault_once() -> None:
    source = (UI_ROOT / "today.js").read_text(encoding="utf-8")

    assert 'script.src = "memory.js"' in source
    assert 'script[data-rayluno-memory="true"]' in source


def test_memory_vault_exposes_review_and_individual_delete_surfaces() -> None:
    source = (UI_ROOT / "memory.js").read_text(encoding="utf-8")

    required_ids = {
        "memory-vault-button",
        "memory-vault-dialog",
        "memory-consent-title",
        "memory-consent-note",
        "memory-list-count",
        "memory-vault-list",
        "memory-vault-close",
    }
    for element_id in required_ids:
        assert element_id in source

    assert "get_memory_snapshot" in source
    assert "forget_memory" in source
    assert "clear_memories" not in source


def test_memory_statements_are_rendered_as_text_not_html() -> None:
    source = (UI_ROOT / "memory.js").read_text(encoding="utf-8")

    assert "statement.textContent" in source
    assert "fact.statement" in source
    assert "statement.innerHTML" not in source
    assert "insertAdjacentHTML" not in source


def test_memory_ui_wraps_existing_command_snapshot_and_event_handlers() -> None:
    source = (UI_ROOT / "memory.js").read_text(encoding="utf-8")

    assert "const previousAssistantEvent = window.assistantEvent" in source
    assert "previousAssistantEvent(event)" in source
    assert "const baseApplySnapshot = applySnapshot" in source
    assert "const baseSubmitCommand = submitCommand" in source


def test_memory_styles_include_focus_unavailable_and_responsive_states() -> None:
    source = (UI_ROOT / "memory.css").read_text(encoding="utf-8")

    assert ".memory-trigger:focus-visible" in source
    assert ".memory-trigger.unavailable" in source
    assert ".memory-dialog::backdrop" in source
    assert "@media (max-width: 720px)" in source


def test_memory_desktop_api_is_the_public_composition_root() -> None:
    source = (UI_ROOT / "__init__.py").read_text(encoding="utf-8")

    assert "MemoryDesktopApi" in source
    assert "DesktopApi = MemoryDesktopApi" in source
