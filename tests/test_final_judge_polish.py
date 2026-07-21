from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "future_assistant" / "ui"


def test_judge_polish_assets_are_explicitly_limited_to_judge_mode() -> None:
    source = (UI / "verified_window.py").read_text(encoding="utf-8")

    assert "judge_polish.css" in source
    assert "judge_polish.js" in source
    assert "if self._judge_mode" in source
    assert 'else ""' in source
    assert "data-rayluno-judge-polish" in source


def test_judge_polish_uses_accessible_dom_apis_and_reduced_motion() -> None:
    script = (UI / "judge_polish.js").read_text(encoding="utf-8")
    stylesheet = (UI / "judge_polish.css").read_text(encoding="utf-8")

    assert "innerHTML" not in script
    assert "textContent" in script
    assert 'setAttribute("role", "note")' in script
    assert 'setAttribute("role", "list")' in script
    assert "assistantlanguagechange" in script
    assert "prefers-reduced-motion" in stylesheet


def test_documented_judge_launcher_uses_the_stable_bounded_voice_path() -> None:
    launcher = (ROOT / "scripts" / "start-judge-demo.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required_launcher_tokens = (
        'RAYLUNO_LANGUAGE = "ar"',
        'RAYLUNO_STT_BACKEND = "vosk"',
        'RAYLUNO_TTS_ENABLED = if ($EnableTts)',
        "future_assistant.safe_voice_cli",
        '"--judge-demo"',
        "--doctor",
    )
    assert all(token in launcher for token in required_launcher_tokens)
    assert "--no-audit" not in launcher
    assert ".\\scripts\\start-judge-demo.ps1 -CheckOnly" in readme
    assert "explicit evaluation entitlement override" in readme
    assert "Temporary activation hosting" in readme
