import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from future_assistant.audit import JsonlAuditLogger
from future_assistant.cli import main
from future_assistant.domain import Action, ActionKind


def test_jsonl_audit_redacts_command_and_query_values(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "audit" / "events.jsonl"
    clock = lambda: datetime(2026, 7, 11, tzinfo=UTC)  # noqa: E731
    logger = JsonlAuditLogger(path, clock)
    secret = "وصفة عائلية سرية"
    url = f"https://www.google.com/search?{urlencode({'q': secret})}"

    logger.record(
        "action_executed",
        command=f"ابحث عن {secret}",
        action=Action(ActionKind.OPEN_URL, {"url": url}),
    )

    raw = path.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert secret not in raw
    assert record["action"] == {
        "kind": "open_url",
        "host": "www.google.com",
        "path": "/search",
        "query_keys": ["q"],
    }
    assert len(record["command_hash"]) == 64


def test_cli_can_run_one_command_without_side_effects(capsys, monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("FUTURE_ASSISTANT_AUDIT_PATH", raising=False)

    exit_code = main(["--once", "رايلونو كم الساعة", "--dry-run", "--no-audit"])

    assert exit_code == 0
    assert "الوقت الآن" in capsys.readouterr().out


def test_cli_paid_ai_fails_closed_without_license(capsys, monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    exit_code = main(["--ollama", "--once", "a flexible request", "--dry-run", "--no-audit"])

    assert exit_code == 3
    assert "Pro" in capsys.readouterr().err
