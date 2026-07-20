from __future__ import annotations

from pathlib import Path

import future_assistant.ui as ui_package
from future_assistant.config import AssistantConfig
from future_assistant.domain import Action, ActionKind, Plan
from future_assistant.product_settings import ProductSettingsStore
from future_assistant.runtime import DryRunEffects
from future_assistant.ui.memory_window import MemoryDesktopApi
from future_assistant.verified_runtime import build_verified_runtime
from future_assistant.verified_skills import HashChainedReceiptLedger


class FixedPlanner:
    def plan(self, command: str) -> Plan:
        return Plan(actions=(Action(ActionKind.REPORT_TIME),))


def test_trust_center_is_derived_from_composed_runtime_state(tmp_path) -> None:  # noqa: ANN001
    ledger = HashChainedReceiptLedger(tmp_path / "execution-receipts.jsonl")
    config = AssistantConfig(
        require_wake_word=False,
        audit_path=None,
        tasks_path=tmp_path / "tasks.sqlite3",
        reminders_path=tmp_path / "reminders.sqlite3",
        memory_path=tmp_path / "memory.sqlite3",
    )
    runtime = build_verified_runtime(
        config,
        effects=DryRunEffects(),
        planner=FixedPlanner(),
        receipt_ledger=ledger,
    )
    api = MemoryDesktopApi(
        runtime,
        settings_store=ProductSettingsStore(tmp_path / "settings.json"),
        judge_mode=True,
    )

    trust = api.get_trust_snapshot()
    verified = api.get_verified_snapshot()
    receipt_view = api.get_verified_receipts()

    assert trust["available"] is True
    assert trust["integrity_ok"] is True
    assert trust["active_count"] == trust["total_count"] == 6
    assert trust["registered_skill_count"] == 5
    assert trust["judge_mode"] is True
    assert trust["checkpoint_kind"] == "local_hmac_sha256"
    assert trust["authorization_order"] == "authorize_then_effect_then_outcome"
    assert all(trust["guarantees"].values())
    assert verified["trust"] == trust
    assert receipt_view["trust"] == trust
    assert "key" not in trust


def test_trust_center_assets_expose_bilingual_runtime_contract() -> None:
    ui_directory = Path(ui_package.__file__).resolve().parent
    script = (ui_directory / "trust_center.js").read_text(encoding="utf-8")
    stylesheet = (ui_directory / "trust_center.css").read_text(encoding="utf-8")
    bridge = (ui_directory / "verified_window.py").read_text(encoding="utf-8")

    assert "get_trust_snapshot" in script
    assert "Runtime trust contract" in script
    assert "عقد الثقة التشغيلي" in script
    assert "write_ahead_authorization" in script
    assert "authenticated_checkpoint" in script
    assert "rayluno-trust-grid" in stylesheet
    assert "trust_center.js" in bridge
    assert "trust_center.css" in bridge
