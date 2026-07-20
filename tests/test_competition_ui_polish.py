from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from future_assistant.safe_voice_cli import (
    _COMPETITION_UI_BOOTSTRAP,
    _bind_window_with_competition_ui,
)


class FakeLoadedEvent:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def __iadd__(self, callback: object) -> FakeLoadedEvent:
        self.callbacks.append(callback)
        return self


class FakeWindow:
    def __init__(self) -> None:
        self.events = SimpleNamespace(loaded=FakeLoadedEvent())
        self.scripts: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)


def _asset(name: str) -> str:
    path = Path(__file__).parents[1] / "src" / "future_assistant" / "ui" / name
    return path.read_text(encoding="utf-8")


def test_safe_voice_window_loads_reversible_competition_assets() -> None:
    api = SimpleNamespace()
    window = FakeWindow()

    _bind_window_with_competition_ui(api, window)

    assert api._window is window
    assert len(window.events.loaded.callbacks) == 1
    callback = window.events.loaded.callbacks[0]
    assert callable(callback)
    callback()
    assert window.scripts == [_COMPETITION_UI_BOOTSTRAP]
    assert "competition-polish.css" in window.scripts[0]
    assert "competition-polish.js" in window.scripts[0]
    assert "data-rayluno-competition-polish" in window.scripts[0]


def test_competition_javascript_uses_safe_dom_construction_and_live_events() -> None:
    script = _asset("competition-polish.js")

    assert "window.assistantEvent" in script
    assert "MutationObserver" in script
    assert '"capture"' in script
    assert '"understand"' in script
    assert '"policy"' in script
    assert '"execute"' in script
    assert '"prove"' in script
    assert "textContent" in script
    assert "innerHTML" not in script
    assert "eval(" not in script


def test_competition_css_has_semantic_states_and_reduced_motion() -> None:
    stylesheet = _asset("competition-polish.css")

    assert '.proof-step.is-active' in stylesheet
    assert '.proof-step.is-complete' in stylesheet
    assert '.proof-step.is-blocked' in stylesheet
    assert 'body[data-proof-state="complete"]' in stylesheet
    assert 'body[data-proof-state="blocked"]' in stylesheet
    assert "prefers-reduced-motion" in stylesheet
