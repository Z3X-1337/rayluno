from __future__ import annotations

from common import read, replace_once, write


NEW_LEDGER = '''class HashChainedReceiptLedger:
    """Append-only JSONL journal authenticated by a local HMAC checkpoint."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._receipts: list[ExecutionReceipt] = []
        self._integrity_ok = True
        self._integrity_error: str | None = None
        self._key_path = self.path.with_name(f"{self.path.name}.key") if self.path else None
        self._anchor_path = (
            self.path.with_name(f"{self.path.name}.anchor.json") if self.path else None
        )
        key_preexisting = bool(self._key_path and self._key_path.exists())
        anchor_preexisting = bool(self._anchor_path and self._anchor_path.exists())
        journal_preexisting = bool(self.path and self.path.exists())
        try:
            self._integrity_key = (
                load_or_create_key(self._key_path)
                if self._key_path is not None
                else secrets.token_bytes(32)
            )
        except (OSError, ValueError) as exc:
            self._integrity_key = secrets.token_bytes(32)
            self._mark_invalid(f"integrity_key:{type(exc).__name__}")
            return
        self._load_initial_state(
            key_preexisting=key_preexisting,
            anchor_preexisting=anchor_preexisting,
            journal_preexisting=journal_preexisting,
        )

    @property
    def receipts(self) -> tuple[ExecutionReceipt, ...]:
        with self._lock:
            return tuple(self._receipts)

    @property
    def integrity_ok(self) -> bool:
        with self._lock:
            return self._integrity_ok

    @property
    def integrity_error(self) -> str | None:
        with self._lock:
            return self._integrity_error

    @property
    def chain_head(self) -> str:
        with self._lock:
            return self._head(self._receipts)

    @property
    def authenticated_checkpoint(self) -> bool:
        return self.path is not None and self._anchor_path is not None

    def verify_integrity(self, *, reload: bool = True) -> bool:
        with self._lock:
            try:
                if self.path is None:
                    candidate = list(self._receipts)
                else:
                    if not self.path.exists():
                        self._mark_invalid("receipt_journal_missing")
                        return False
                    if self._anchor_path is None or not self._anchor_path.exists():
                        self._mark_invalid("receipt_anchor_missing")
                        return False
                    candidate = self._read_file() if reload else list(self._receipts)
                if not self.verify(candidate):
                    self._mark_invalid("hash_chain_mismatch")
                    return False
                if self.path is not None:
                    anchor = self._read_anchor()
                    if anchor["receipt_count"] != len(candidate):
                        self._mark_invalid("receipt_count_rollback")
                        return False
                    if not secrets.compare_digest(str(anchor["chain_head"]), self._head(candidate)):
                        self._mark_invalid("receipt_head_rollback")
                        return False
            except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
                self._mark_invalid(type(exc).__name__)
                return False
            self._receipts = list(candidate)
            self._integrity_ok = True
            self._integrity_error = None
            return True

    def record(
        self,
        assessment: SkillAssessment,
        result: ExecutionResult,
        *,
        event: str = "execution",
        confirmation_state: str = "not_required",
        status_override: str | None = None,
    ) -> ExecutionReceipt:
        with self._lock:
            if not self.verify_integrity(reload=True):
                raise ReceiptIntegrityError("The receipt journal failed integrity verification.")
            timestamp = self._aware_utc(self.clock()).isoformat()
            status = status_override or (
                "completed" if result.ok else "blocked" if result.blocked else "failed"
            )
            arguments = dict(result.action.parameters)
            payload: dict[str, object] = {
                "schema": _RECEIPT_SCHEMA,
                "receipt_id": f"ryl-{secrets.token_hex(8)}",
                "timestamp": timestamp,
                "event": event,
                "skill_id": assessment.manifest.skill_id,
                "permission": assessment.manifest.permission,
                "risk": assessment.manifest.risk.value,
                "status": status,
                "confirmation_state": confirmation_state,
                "policy_reason": assessment.reason,
                "action": summarize_action(result.action),
                "argument_keys": sorted(str(key) for key in arguments),
                "argument_digest": keyed_digest(
                    self._integrity_key,
                    {"domain": "rayluno.receipt.arguments/v1", "arguments": arguments},
                ),
                "previous_hash": self.chain_head,
            }
            receipt_hash = self._seal(payload)
            receipt = ExecutionReceipt.from_dict({**payload, "receipt_hash": receipt_hash})
            self._receipts.append(receipt)
            try:
                self._append(receipt)
                self._write_anchor()
            except (OSError, TypeError, ValueError) as exc:
                self._mark_invalid(f"receipt_persistence:{type(exc).__name__}")
                raise ReceiptIntegrityError("The receipt could not be persisted safely.") from exc
            return receipt

    @classmethod
    def verify(cls, receipts: Sequence[ExecutionReceipt]) -> bool:
        previous_hash = _GENESIS_HASH
        for receipt in receipts:
            if receipt.schema != _RECEIPT_SCHEMA or receipt.previous_hash != previous_hash:
                return False
            expected_hash = cls._seal(receipt.unsigned_payload())
            if not secrets.compare_digest(receipt.receipt_hash, expected_hash):
                return False
            previous_hash = receipt.receipt_hash
        return True

    def _load_initial_state(
        self,
        *,
        key_preexisting: bool,
        anchor_preexisting: bool,
        journal_preexisting: bool,
    ) -> None:
        if self.path is None:
            return
        if anchor_preexisting and not key_preexisting:
            self._mark_invalid("receipt_integrity_key_missing")
            return
        if not journal_preexisting:
            if key_preexisting or anchor_preexisting:
                self._mark_invalid("receipt_journal_missing")
                return
            try:
                atomic_write_bytes(self.path, b"")
                self._write_anchor()
            except OSError as exc:
                self._mark_invalid(f"receipt_initialization:{type(exc).__name__}")
            return
        if key_preexisting and not anchor_preexisting:
            self._mark_invalid("receipt_anchor_missing")
            return
        if not anchor_preexisting:
            try:
                candidate = self._read_file()
                if not self.verify(candidate):
                    self._mark_invalid("legacy_hash_chain_mismatch")
                    return
                self._receipts = candidate
                self._write_anchor()
            except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
                self._mark_invalid(f"legacy_migration:{type(exc).__name__}")
            return
        self.verify_integrity(reload=True)

    def _read_file(self) -> list[ExecutionReceipt]:
        if self.path is None or not self.path.exists():
            raise FileNotFoundError("receipt journal is missing")
        receipts: list[ExecutionReceipt] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError("Receipt journal entries must be JSON objects.")
            receipts.append(ExecutionReceipt.from_dict(value))
        return receipts

    def _read_anchor(self) -> dict[str, object]:
        if self._anchor_path is None:
            raise ValueError("receipt anchor is unavailable")
        raw = self._anchor_path.read_bytes()
        if not raw or len(raw) > 4096:
            raise ValueError("receipt anchor size is invalid")
        value = json.loads(raw)
        expected_fields = {"schema", "receipt_count", "chain_head", "mac"}
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ValueError("receipt anchor fields are invalid")
        count = value["receipt_count"]
        head = value["chain_head"]
        mac = value["mac"]
        if type(count) is not int or count < 0:
            raise ValueError("receipt anchor count is invalid")
        if not isinstance(head, str) or len(head) != 64:
            raise ValueError("receipt anchor head is invalid")
        if not isinstance(mac, str) or len(mac) != 64:
            raise ValueError("receipt anchor MAC is invalid")
        payload = {"schema": value["schema"], "receipt_count": count, "chain_head": head}
        if payload["schema"] != _ANCHOR_SCHEMA:
            raise ValueError("receipt anchor schema is invalid")
        expected_mac = keyed_digest(self._integrity_key, payload)
        if not secrets.compare_digest(mac, expected_mac):
            raise ValueError("receipt anchor authentication failed")
        return value

    def _write_anchor(self) -> None:
        if self._anchor_path is None:
            return
        payload: dict[str, object] = {
            "schema": _ANCHOR_SCHEMA,
            "receipt_count": len(self._receipts),
            "chain_head": self._head(self._receipts),
        }
        document = {**payload, "mac": keyed_digest(self._integrity_key, payload)}
        contents = (
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\\n"
        ).encode("utf-8")
        atomic_write_bytes(self._anchor_path, contents)

    def _append(self, receipt: ExecutionReceipt) -> None:
        if self.path is None:
            return
        secure_directory(self.path.parent)
        line = json.dumps(asdict(receipt), ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\\n") as stream:
            stream.write(f"{line}\\n")
            stream.flush()
            os.fsync(stream.fileno())
        secure_file(self.path)

    def _mark_invalid(self, error: str) -> None:
        self._integrity_ok = False
        self._integrity_error = error

    @staticmethod
    def _head(receipts: Sequence[ExecutionReceipt]) -> str:
        return receipts[-1].receipt_hash if receipts else _GENESIS_HASH

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _canonical(value: Mapping[str, object]) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _seal(cls, payload: Mapping[str, object]) -> str:
        return hashlib.sha256(cls._canonical(payload).encode("utf-8")).hexdigest()
'''


def main() -> None:
    path = "src/future_assistant/verified_skills.py"
    replace_once(
        path,
        "import json\nimport secrets\nimport threading\n",
        "import json\nimport os\nimport secrets\nimport threading\n",
        marker="import os",
    )
    replace_once(
        path,
        "from .domain import Action, ActionKind, ExecutionResult, PlanSource\n",
        "from .domain import Action, ActionKind, ExecutionResult, PlanSource\n"
        "from .local_security import (\n"
        "    atomic_write_bytes,\n"
        "    keyed_digest,\n"
        "    load_or_create_key,\n"
        "    secure_directory,\n"
        "    secure_file,\n"
        ")\n",
        marker="from .local_security import (",
    )
    replace_once(
        path,
        '_GENESIS_HASH = "0" * 64\n',
        '_GENESIS_HASH = "0" * 64\n_ANCHOR_SCHEMA = "rayluno.receipt-anchor/v1"\n',
        marker="_ANCHOR_SCHEMA",
    )
    text = read(path)
    start = text.index("class HashChainedReceiptLedger:")
    end = text.index("\n\n__all__ = [", start)
    if "authenticated_checkpoint" not in text[start:end]:
        write(path, text[:start] + NEW_LEDGER + text[end:])


if __name__ == "__main__":
    main()
