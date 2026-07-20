import hashlib
import json
from datetime import UTC, datetime

import pytest

from future_assistant.audit import JsonlAuditLogger, MemoryAuditLogger
from future_assistant.config import AssistantConfig
from future_assistant.domain import Action, ActionKind, Plan, PlanSource, RuntimeStatus
from future_assistant.memory import InMemoryMemoryStore, MemoryService, SensitiveMemoryError
from future_assistant.runtime import AssistantRuntime
from future_assistant.ui.window import DesktopApi
from future_assistant.verified_runtime import VerifiedAssistantRuntime
from future_assistant.verified_skills import HashChainedReceiptLedger, ReceiptIntegrityError


class FixedPlanner:
    def __init__(self, plan: Plan) -> None:
        self.plan_value = plan

    def plan(self, command: str) -> Plan:
        return self.plan_value


class LedgerAwareEffects:
    def __init__(self, ledger: HashChainedReceiptLedger) -> None:
        self.ledger = ledger
        self.operations: list[tuple[str, str]] = []

    def open_url(self, url: str) -> None:
        assert self.ledger.receipts[-1].event == "execution_authorized"
        self.operations.append(("open_url", url))

    def open_app(self, app_id: str) -> None:
        assert self.ledger.receipts[-1].event == "execution_authorized"
        self.operations.append(("open_app", app_id))

    def current_time(self) -> datetime:
        assert self.ledger.receipts[-1].event == "execution_authorized"
        return datetime(2026, 7, 20, 12, 0, tzinfo=UTC)

    def control_volume(self, operation, steps: int) -> None:  # noqa: ANN001
        assert self.ledger.receipts[-1].event == "execution_authorized"


class RejectingLedger(HashChainedReceiptLedger):
    def record(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if kwargs.get("event") == "execution_authorized":
            raise ReceiptIntegrityError("simulated authorization persistence failure")
        return super().record(*args, **kwargs)


def _verified(plan: Plan, ledger: HashChainedReceiptLedger):  # noqa: ANN201
    effects = LedgerAwareEffects(ledger)
    base = AssistantRuntime(
        AssistantConfig(require_wake_word=False, audit_path=None),
        FixedPlanner(plan),
        effects,
        MemoryAuditLogger(),
    )
    return VerifiedAssistantRuntime(base, receipt_ledger=ledger), effects


def test_effect_is_preceded_by_persisted_authorization_receipt(tmp_path) -> None:  # noqa: ANN001
    ledger = HashChainedReceiptLedger(tmp_path / "receipts.jsonl")
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.DETERMINISTIC,
    )
    runtime, effects = _verified(plan, ledger)

    result = runtime.handle("open calculator")

    assert result.status is RuntimeStatus.COMPLETED
    assert effects.operations == [("open_app", "calculator")]
    assert [item.event for item in ledger.receipts] == ["execution_authorized", "execution"]


def test_authorization_persistence_failure_prevents_side_effect() -> None:
    ledger = RejectingLedger()
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.DETERMINISTIC,
    )
    runtime, effects = _verified(plan, ledger)

    result = runtime.handle("open calculator")

    assert result.status is RuntimeStatus.BLOCKED
    assert effects.operations == []


@pytest.mark.parametrize("mutation", ["delete", "truncate"])
def test_receipt_journal_deletion_or_truncation_fails_closed(tmp_path, mutation: str) -> None:  # noqa: ANN001
    path = tmp_path / "receipts.jsonl"
    ledger = HashChainedReceiptLedger(path)
    plan = Plan(actions=(Action(ActionKind.REPORT_TIME),))
    runtime, _ = _verified(plan, ledger)
    assert runtime.handle("time").status is RuntimeStatus.COMPLETED

    if mutation == "delete":
        path.unlink()
    else:
        path.write_bytes(b"")

    reopened = HashChainedReceiptLedger(path)
    assert not reopened.integrity_ok
    blocked_runtime, blocked_effects = _verified(plan, reopened)
    assert blocked_runtime.handle("time").status is RuntimeStatus.BLOCKED
    assert blocked_effects.operations == []


def test_receipt_anchor_tampering_fails_closed(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "receipts.jsonl"
    HashChainedReceiptLedger(path)
    anchor = path.with_name(f"{path.name}.anchor.json")
    document = json.loads(anchor.read_text(encoding="utf-8"))
    document["receipt_count"] = 99
    anchor.write_text(json.dumps(document), encoding="utf-8")

    reopened = HashChainedReceiptLedger(path)
    assert not reopened.integrity_ok


def test_confirmation_handle_never_enters_audit_records() -> None:
    plan = Plan(
        actions=(Action(ActionKind.OPEN_APP, {"app_id": "calculator"}),),
        source=PlanSource.OLLAMA,
    )
    audit = MemoryAuditLogger()
    ledger = HashChainedReceiptLedger()
    base = AssistantRuntime(
        AssistantConfig(require_wake_word=False, audit_path=None),
        FixedPlanner(plan),
        LedgerAwareEffects(ledger),
        audit,
    )
    runtime = VerifiedAssistantRuntime(base, receipt_ledger=ledger)

    runtime.handle("choose a calculator")
    pending = runtime.pending_public()

    assert pending is not None
    plain = hashlib.sha256(
        json.dumps(
            {"0:app_id": "calculator"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert pending["argument_digest"] != plain
    assert str(pending["confirmation_id"]) not in repr(audit.records)


def test_persisted_audit_fingerprint_is_keyed_and_stable(tmp_path) -> None:  # noqa: ANN001
    path = tmp_path / "audit.jsonl"
    command = "open calculator"
    JsonlAuditLogger(path).record("command_received", command=command)
    JsonlAuditLogger(path).record("command_received", command=command)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert records[0]["command_hash"] == records[1]["command_hash"]
    assert records[0]["command_hash"] != hashlib.sha256(command.encode()).hexdigest()
    assert command not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123",
        "-----BEGIN PRIVATE KEY----- ABCDEF",
        "4111 1111 1111 1111",
    ],
)
def test_structured_secrets_are_rejected_without_keyword_labels(secret: str) -> None:
    service = MemoryService(InMemoryMemoryStore())
    with pytest.raises(SensitiveMemoryError):
        service.remember(secret)


def test_benign_long_number_is_not_rejected_as_payment_card() -> None:
    service = MemoryService(InMemoryMemoryStore())
    saved = service.remember("Build number 1234567890123")
    assert saved.created


class NoEntitlements:
    def has_feature(self, feature: str) -> bool:
        return False


def test_judge_mode_unlocks_only_bounded_demo_capabilities() -> None:
    runtime = object()
    normal = DesktopApi(runtime, entitlement_service=NoEntitlements())
    judge = DesktopApi(runtime, entitlement_service=NoEntitlements(), judge_mode=True)

    assert not normal._has_feature("voice.local")
    assert judge._has_feature("voice.local")
    assert judge._has_feature("ai.local")
    assert judge._has_feature("automation.pro")
    assert not judge._has_feature("unknown.feature")
