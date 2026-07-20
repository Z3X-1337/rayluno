from future_assistant.config import AssistantConfig
from future_assistant.doctor import CheckStatus, check_environment, format_report
from future_assistant.voice import VoiceSettings


def test_doctor_report_runs_without_optional_dependencies_or_network() -> None:
    checks = check_environment(
        AssistantConfig(audit_path=None),
        VoiceSettings(),
        probe_ollama=False,
    )

    assert checks
    assert checks[0].status in {CheckStatus.PASS, CheckStatus.FAIL}
    report = format_report(checks)
    assert "فحص جاهزية" in report
    assert "Python" in report
